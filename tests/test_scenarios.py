"""Run every YAML scenario under scenarios/ as a pytest test.

Default target: a TestClient-backed in-process WebSocket so the suite is
hermetic and runs offline (no Railway, no real LLM/Twilio).

Override via env to hit a live server:
    SCENARIO_WS_URL=wss://ai-voice-production-eb9e.up.railway.app/ws/conversationrelay \
    SCENARIO_HTTP_URL=https://ai-voice-production-eb9e.up.railway.app \
    pytest tests/test_scenarios.py -v
"""

from __future__ import annotations

import json
import os
import threading
import urllib.parse
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def _scenario_files() -> list[Path]:
    if not SCENARIOS_DIR.exists():
        return []
    return sorted(SCENARIOS_DIR.glob("*.yaml"))


@contextmanager
def _live_or_local_runner():
    """Yield (ws_factory, http_factory) for either a live URL or in-process app."""
    ws_url = os.environ.get("SCENARIO_WS_URL")
    http_url = os.environ.get("SCENARIO_HTTP_URL")
    if ws_url and http_url:
        from websockets.sync.client import connect as ws_connect

        def ws_factory():
            return ws_connect(ws_url, open_timeout=10, close_timeout=4)

        def http_get(call_sid: str) -> dict | None:
            import urllib.request

            url = f"{http_url.rstrip('/')}/analytics/calls/{urllib.parse.quote(call_sid)}"
            try:
                with urllib.request.urlopen(url, timeout=8) as r:
                    return json.loads(r.read().decode())
            except Exception:
                return None

        yield ws_factory, http_get
        return

    # In-process FastAPI TestClient.
    client = TestClient(create_app())

    def ws_factory():
        return client.websocket_connect("/ws/conversationrelay")

    def http_get(call_sid: str) -> dict | None:
        r = client.get(f"/analytics/calls/{urllib.parse.quote(call_sid)}")
        if r.status_code != 200:
            return None
        return r.json()

    with client:
        yield ws_factory, http_get


def _drain_text_messages_starlette(ws, *, timeout: float = 8.0) -> tuple[list[dict], str | None]:
    """TestClient WebSocket recv has no timeout — wrap in a thread."""
    frames: list[dict] = []
    lang_switch: str | None = None
    saw_last = False

    def reader(box: list) -> None:
        try:
            box.append(ws.receive_text())
        except WebSocketDisconnect:
            box.append(None)
        except Exception:
            box.append(None)

    while not saw_last:
        result: list = []
        t = threading.Thread(target=reader, args=(result,), daemon=True)
        t.start()
        t.join(timeout=timeout)
        if not result:
            break
        raw = result[0]
        if raw is None:
            break
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            continue
        frames.append(msg)
        if msg.get("type") == "language":
            lang_switch = msg.get("ttsLanguage") or msg.get("transcriptionLanguage")
            continue
        if msg.get("type") == "text" and msg.get("last") is True:
            saw_last = True
    return frames, lang_switch


def _drain_text_messages_websockets(ws, *, timeout: float = 25.0) -> tuple[list[dict], str | None]:
    frames: list[dict] = []
    lang_switch: str | None = None
    saw_last = False
    while not saw_last:
        try:
            raw = ws.recv(timeout=timeout)
        except TimeoutError:
            break
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            continue
        frames.append(msg)
        if msg.get("type") == "language":
            lang_switch = msg.get("ttsLanguage") or msg.get("transcriptionLanguage")
            continue
        if msg.get("type") == "text" and msg.get("last") is True:
            saw_last = True
    return frames, lang_switch


def _stitch_text(frames: list[dict]) -> str:
    return "".join(str(f.get("token", "")) for f in frames if f.get("type") == "text").strip()


def _send(ws, payload: dict) -> None:
    if hasattr(ws, "send_text"):
        ws.send_text(json.dumps(payload))
    else:
        ws.send(json.dumps(payload))


def _drain(ws) -> tuple[list[dict], str | None]:
    if hasattr(ws, "receive_text"):
        return _drain_text_messages_starlette(ws)
    return _drain_text_messages_websockets(ws)


@pytest.mark.parametrize("scenario_path", _scenario_files(), ids=lambda p: p.stem)
def test_scenario(scenario_path: Path) -> None:
    raw = yaml.safe_load(scenario_path.read_text())
    steps = raw.get("steps", [])
    call_sid = f"CA{uuid.uuid4().hex[:30]}"

    with _live_or_local_runner() as (ws_factory, http_get):
        with ws_factory() as ws:
            _send(ws, {"type": "setup", "callSid": call_sid, "from": "+15555550100"})
            for i, step in enumerate(steps):
                _send(
                    ws,
                    {
                        "type": "prompt",
                        "voicePrompt": step["say"],
                        "lang": step.get("lang", "en-US"),
                        "last": True,
                    },
                )
                frames, lang_switch = _drain(ws)
                reply = _stitch_text(frames)

                for needle in step.get("expect_contains", []):
                    assert needle.lower() in reply.lower(), (
                        f"step {i}: reply missing {needle!r}\n  said: {step['say']!r}\n  reply: {reply!r}"
                    )
                if step.get("expect_language_switch"):
                    assert lang_switch == step["expect_language_switch"], (
                        f"step {i}: expected lang switch to {step['expect_language_switch']}, "
                        f"got {lang_switch!r}"
                    )

        detail = http_get(call_sid)

    if any(
        k in raw
        for k in (
            "expect_intent",
            "expect_party_size",
            "expect_party_size_is_none",
            "expect_guest_name",
            "expect_reservation_datetime_contains",
            "expect_qualified",
            "expect_qualification_label",
            "expect_status",
        )
    ):
        assert detail is not None, "could not fetch /analytics/calls — assertion impossible"

    if detail is None:
        return

    if "expect_intent" in raw:
        assert detail.get("intent") == raw["expect_intent"], (
            f"intent: expected {raw['expect_intent']!r}, got {detail.get('intent')!r}"
        )
    if "expect_party_size" in raw:
        assert detail.get("party_size") == raw["expect_party_size"], (
            f"party_size: expected {raw['expect_party_size']!r}, got {detail.get('party_size')!r}"
        )
    if raw.get("expect_party_size_is_none"):
        assert detail.get("party_size") is None, (
            f"party_size: expected None, got {detail.get('party_size')!r}"
        )
    if "expect_guest_name" in raw:
        assert detail.get("guest_name") == raw["expect_guest_name"], (
            f"guest_name: expected {raw['expect_guest_name']!r}, got {detail.get('guest_name')!r}"
        )
    if "expect_reservation_datetime_contains" in raw:
        value = (detail.get("reservation_datetime") or "").lower()
        needle = raw["expect_reservation_datetime_contains"].lower()
        assert needle in value, (
            f"reservation_datetime: expected to contain {needle!r}, got {value!r}"
        )
    if "expect_qualified" in raw:
        actually = detail.get("status") == "qualified"
        assert actually == raw["expect_qualified"], (
            f"qualified: expected {raw['expect_qualified']}, status={detail.get('status')!r}"
        )
    if "expect_qualification_label" in raw:
        lead = detail.get("lead") or {}
        assert lead.get("qualification_label") == raw["expect_qualification_label"], (
            f"qualification_label: expected {raw['expect_qualification_label']!r}, "
            f"got {lead.get('qualification_label')!r}"
        )
    if "expect_status" in raw:
        assert detail.get("status") == raw["expect_status"], (
            f"status: expected {raw['expect_status']!r}, got {detail.get('status')!r}"
        )
