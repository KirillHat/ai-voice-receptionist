"""Run every scenario, capture the full agent transcript and produce a report.

This is a non-failing variant of tests/test_scenarios.py — the harness collects
everything and writes a Markdown summary instead of stopping on the first
assertion miss. Useful for human review and for the user-facing report.

Default target: in-process FastAPI TestClient (no Railway, no real Twilio
signature). Override via env to run against a live server:
    SCENARIO_WS_URL=wss://... SCENARIO_HTTP_URL=https://... \
        python scripts/scenario_report.py
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from starlette.websockets import WebSocketDisconnect

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCENARIOS_DIR = ROOT / "scenarios"
REPORT_PATH = ROOT / "scenarios_report.md"


@dataclass
class StepRecord:
    say: str
    lang: str
    reply: str = ""
    saw_lang_switch: str | None = None
    expectations_failed: list[str] = field(default_factory=list)


@dataclass
class ScenarioRecord:
    name: str
    file: str
    steps: list[StepRecord]
    detail: dict | None
    final_failures: list[str]
    elapsed_s: float

    @property
    def ok(self) -> bool:
        return not self.final_failures and not any(s.expectations_failed for s in self.steps)


def _live_runner_factories():
    ws_url = os.environ.get("SCENARIO_WS_URL")
    http_url = os.environ.get("SCENARIO_HTTP_URL")
    if not (ws_url and http_url):
        return None
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

    return ws_factory, http_get


def _local_runner_factories():
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    client.__enter__()  # keep app lifespan up while we run

    def ws_factory():
        return client.websocket_connect("/ws/conversationrelay")

    def http_get(call_sid: str) -> dict | None:
        r = client.get(f"/analytics/calls/{urllib.parse.quote(call_sid)}")
        if r.status_code != 200:
            return None
        return r.json()

    return ws_factory, http_get, client


def _send(ws, payload: dict) -> None:
    if hasattr(ws, "send_text"):
        ws.send_text(json.dumps(payload))
    else:
        ws.send(json.dumps(payload))


def _drain_starlette(ws, timeout: float = 12.0) -> tuple[list[dict], str | None]:
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


def _drain_websockets(ws, timeout: float = 25.0) -> tuple[list[dict], str | None]:
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


def _drain(ws) -> tuple[list[dict], str | None]:
    if hasattr(ws, "receive_text"):
        return _drain_starlette(ws)
    return _drain_websockets(ws)


def _stitch(frames: list[dict]) -> str:
    return "".join(str(f.get("token", "")) for f in frames if f.get("type") == "text").strip()


def run_one(raw: dict, *, ws_factory, http_get) -> ScenarioRecord:
    name = raw.get("name", "unnamed")
    steps_in = raw.get("steps", [])
    call_sid = f"CA{uuid.uuid4().hex[:30]}"
    started = time.monotonic()
    step_records: list[StepRecord] = []

    # Use a unique phone per scenario so the returning-caller branch only
    # fires inside scenarios that explicitly script multiple visits.
    phone = f"+1555{uuid.uuid4().hex[:7]}"
    with ws_factory() as ws:
        _send(ws, {"type": "setup", "callSid": call_sid, "from": phone})
        for s in steps_in:
            _send(
                ws,
                {
                    "type": "prompt",
                    "voicePrompt": s["say"],
                    "lang": s.get("lang", "en-US"),
                    "last": True,
                },
            )
            frames, lang_switch = _drain(ws)
            reply = _stitch(frames)
            failed: list[str] = []
            for needle in s.get("expect_contains", []) or []:
                if needle.lower() not in reply.lower():
                    failed.append(f"reply missing {needle!r}")
            if s.get("expect_language_switch") and lang_switch != s["expect_language_switch"]:
                failed.append(
                    f"expected lang switch to {s['expect_language_switch']}, got {lang_switch!r}"
                )
            step_records.append(
                StepRecord(
                    say=s["say"],
                    lang=s.get("lang", "en-US"),
                    reply=reply,
                    saw_lang_switch=lang_switch,
                    expectations_failed=failed,
                )
            )

    detail = http_get(call_sid)
    final_failures: list[str] = []
    if detail is None:
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
            final_failures.append("could not fetch /analytics/calls — assertions skipped")
    else:
        if "expect_intent" in raw and detail.get("intent") != raw["expect_intent"]:
            final_failures.append(
                f"intent: expected {raw['expect_intent']!r}, got {detail.get('intent')!r}"
            )
        if "expect_party_size" in raw and detail.get("party_size") != raw["expect_party_size"]:
            final_failures.append(
                f"party_size: expected {raw['expect_party_size']!r}, got {detail.get('party_size')!r}"
            )
        if raw.get("expect_party_size_is_none") and detail.get("party_size") is not None:
            final_failures.append(f"party_size: expected None, got {detail.get('party_size')!r}")
        if "expect_guest_name" in raw and detail.get("guest_name") != raw["expect_guest_name"]:
            final_failures.append(
                f"guest_name: expected {raw['expect_guest_name']!r}, got {detail.get('guest_name')!r}"
            )
        if "expect_reservation_datetime_contains" in raw:
            v = (detail.get("reservation_datetime") or "").lower()
            needle = raw["expect_reservation_datetime_contains"].lower()
            if needle not in v:
                final_failures.append(
                    f"reservation_datetime: expected to contain {needle!r}, got {v!r}"
                )
        if "expect_qualified" in raw:
            actually = detail.get("status") == "qualified"
            if actually != raw["expect_qualified"]:
                final_failures.append(
                    f"qualified: expected {raw['expect_qualified']}, status={detail.get('status')!r}"
                )
        if "expect_qualification_label" in raw:
            lead = detail.get("lead") or {}
            if lead.get("qualification_label") != raw["expect_qualification_label"]:
                final_failures.append(
                    f"qualification_label: expected {raw['expect_qualification_label']!r}, "
                    f"got {lead.get('qualification_label')!r}"
                )
        if "expect_status" in raw and detail.get("status") != raw["expect_status"]:
            final_failures.append(
                f"status: expected {raw['expect_status']!r}, got {detail.get('status')!r}"
            )

    elapsed = time.monotonic() - started
    return ScenarioRecord(
        name=name,
        file=str(raw.get("__file__", "")),
        steps=step_records,
        detail=detail,
        final_failures=final_failures,
        elapsed_s=elapsed,
    )


def _format_markdown(records: list[ScenarioRecord], *, target_label: str) -> str:
    total = len(records)
    passed = sum(1 for r in records if r.ok)
    failed = total - passed
    avg_ms = (sum(r.elapsed_s for r in records) / total * 1000) if total else 0.0

    lines: list[str] = []
    lines.append("# Scenario report\n")
    lines.append(f"- target: **{target_label}**")
    lines.append(f"- scenarios: **{total}**, passed: **{passed}**, failed: **{failed}**")
    lines.append(f"- average latency per scenario: **{avg_ms:.0f} ms**\n")

    lines.append("## Summary\n")
    lines.append("| # | scenario | result | turns | intent | name | party | datetime | label |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(records, 1):
        d = r.detail or {}
        lead = d.get("lead") or {}
        result = "✅" if r.ok else "❌"
        lines.append(
            f"| {i} | `{r.name}` | {result} | {len(r.steps)} | "
            f"{d.get('intent') or '—'} | {d.get('guest_name') or '—'} | "
            f"{d.get('party_size') or '—'} | "
            f"{d.get('reservation_datetime') or '—'} | "
            f"{lead.get('qualification_label') or '—'} |"
        )
    lines.append("")

    lines.append("## Transcripts\n")
    for i, r in enumerate(records, 1):
        status = "✅ PASS" if r.ok else "❌ FAIL"
        lines.append(f"### {i}. `{r.name}` — {status}")
        if r.final_failures:
            lines.append("")
            for f in r.final_failures:
                lines.append(f"- ❌ {f}")
        lines.append("")
        for step in r.steps:
            ls = f" [→ {step.saw_lang_switch}]" if step.saw_lang_switch else ""
            lines.append(f"- 👤 _{step.lang}_{ls}: {step.say}")
            reply = step.reply or "(silence)"
            lines.append(f"  - 🤖 {reply}")
            for f in step.expectations_failed:
                lines.append(f"  - ❌ {f}")
        d = r.detail
        if d:
            lead = d.get("lead") or {}
            lines.append("")
            lines.append(
                f"  _captured_: intent=`{d.get('intent')}` "
                f"name=`{d.get('guest_name')}` "
                f"party=`{d.get('party_size')}` "
                f"datetime=`{d.get('reservation_datetime')}` "
                f"status=`{d.get('status')}` "
                f"label=`{lead.get('qualification_label')}`"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    yaml_files = sorted(SCENARIOS_DIR.glob("*.yaml"))
    if not yaml_files:
        print(f"no YAML files in {SCENARIOS_DIR}")
        return 1

    live = _live_runner_factories()
    client_handle = None
    if live is not None:
        ws_factory, http_get = live
        target_label = os.environ.get("SCENARIO_HTTP_URL", "live")
    else:
        ws_factory, http_get, client_handle = _local_runner_factories()
        target_label = "in-process TestClient"

    records: list[ScenarioRecord] = []
    try:
        for f in yaml_files:
            raw = yaml.safe_load(f.read_text())
            raw["__file__"] = f.name
            print(f"running {f.name} ...", end="", flush=True)
            try:
                rec = run_one(raw, ws_factory=ws_factory, http_get=http_get)
            except Exception as exc:
                rec = ScenarioRecord(
                    name=raw.get("name", f.stem),
                    file=f.name,
                    steps=[],
                    detail=None,
                    final_failures=[f"runtime error: {exc!r}"],
                    elapsed_s=0.0,
                )
            mark = "✅" if rec.ok else "❌"
            print(f" {mark} ({rec.elapsed_s:.1f}s)")
            records.append(rec)
    finally:
        if client_handle is not None:
            with contextlib.suppress(Exception):
                client_handle.__exit__(None, None, None)

    md = _format_markdown(records, target_label=target_label)
    REPORT_PATH.write_text(md)
    print(f"\nreport: {REPORT_PATH}")

    failed = sum(1 for r in records if not r.ok)
    if failed:
        print(f"{failed}/{len(records)} scenario(s) failed")
        return 1
    print(f"all {len(records)} scenarios passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
