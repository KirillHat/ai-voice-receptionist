"""Verify the WS silence-timeout flow: nudge then graceful end."""

from __future__ import annotations

import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_SILENCE_NUDGE_SEC", "1")
    monkeypatch.setenv("VOICE_SILENCE_ENDCALL_SEC", "2")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def _drain(ws, max_messages: int = 6) -> list[str]:
    out: list[str] = []
    for _ in range(max_messages):
        try:
            d = json.loads(ws.receive_text())
        except Exception:
            break
        if d.get("type") == "text" and d.get("token"):
            out.append(d["token"])
    return out


def test_silence_nudge_then_end(client: TestClient) -> None:
    sid = f"CA{uuid.uuid4().hex[:30]}"
    phone = f"+1555{uuid.uuid4().hex[:7]}"
    with client.websocket_connect("/ws/conversationrelay") as ws:
        ws.send_text(json.dumps({"type": "setup", "callSid": sid, "from": phone}))
        # Just go silent — never send a 'prompt'. With nudge=1s, end=2s,
        # we should see a nudge tokenfollowed by the give-up message
        # within ~3.5 seconds total.
        tokens = _drain(ws)

    joined = " ".join(tokens).lower()
    print(f"COLLECTED TOKENS: {tokens!r}")
    assert "still there" in joined or "back shortly" in joined or "перезвонит" in joined or "moment" in joined
