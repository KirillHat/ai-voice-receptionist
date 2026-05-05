"""Core webhook tests for the Twilio Voice flow."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_request_id_is_echoed(client: TestClient) -> None:
    r = client.get("/healthz", headers={"X-Request-ID": "voice-rid-1"})
    assert r.status_code == 200
    assert r.headers["X-Request-ID"] == "voice-rid-1"


def test_incoming_returns_gather_twiml(client: TestClient) -> None:
    with patch("app.webhooks.voice._start_call_recording"):
        r = client.post(
            "/webhooks/voice/incoming",
            data={"CallSid": "CA111", "From": "+13105550101", "To": "+13105559999"},
        )

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert "<Gather" in r.text


def test_incoming_returns_conversationrelay_twiml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_MODE", "conversationrelay")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as app_client, patch("app.webhooks.voice._start_call_recording"):
            r = app_client.post(
                "/webhooks/voice/incoming",
                data={"CallSid": "CA119", "From": "+13105550109", "To": "+13105559999"},
            )
        assert r.status_code == 200
        assert "<ConversationRelay" in r.text
    finally:
        get_settings.cache_clear()


def test_collect_completes_and_fans_out(client: TestClient) -> None:
    with patch("app.webhooks.voice._fanout_lead", new=AsyncMock()) as fanout:
        with patch("app.webhooks.voice._start_call_recording"):
            client.post(
                "/webhooks/voice/incoming",
                data={"CallSid": "CA222", "From": "+13105550102", "To": "+13105559999"},
            )

        client.post(
            "/webhooks/voice/collect",
            data={"CallSid": "CA222", "From": "+13105550102", "SpeechResult": "reservation"},
        )
        client.post(
            "/webhooks/voice/collect",
            data={"CallSid": "CA222", "From": "+13105550102", "SpeechResult": "my name is alex"},
        )
        client.post(
            "/webhooks/voice/collect",
            data={"CallSid": "CA222", "From": "+13105550102", "SpeechResult": "for 4"},
        )
        r = client.post(
            "/webhooks/voice/collect",
            data={
                "CallSid": "CA222",
                "From": "+13105550102",
                "SpeechResult": "tomorrow at 8 pm",
            },
        )

    assert r.status_code == 200
    assert "Goodbye" in r.text
    fanout.assert_awaited_once()


def test_analytics_summary_endpoint(client: TestClient) -> None:
    r = client.get("/analytics/summary")
    assert r.status_code == 200
    assert "total_calls" in r.json()


def test_websocket_faq_shortcut_answers_without_llm(client: TestClient) -> None:
    with client.websocket_connect("/ws/conversationrelay") as ws:
        ws.send_text(json.dumps({"type": "setup", "callSid": "CAFAQ", "from": "+13105550044"}))
        ws.send_text(
            json.dumps(
                {
                    "type": "prompt",
                    "voicePrompt": "is there valet parking",
                    "lang": "en-US",
                    "last": True,
                }
            )
        )
        msg = json.loads(ws.receive_text())
    assert msg["type"] == "text"
    assert msg["last"] is True
    assert "valet" in msg["token"].lower()
    assert "seventeen" in msg["token"].lower()


def test_conversationrelay_websocket_prompt_flow(client: TestClient) -> None:
    with client.websocket_connect("/ws/conversationrelay") as ws:
        ws.send_text(json.dumps({"type": "setup", "callSid": "CAWS1", "from": "+13105550011"}))
        ws.send_text(
            json.dumps(
                {
                    "type": "prompt",
                    "voicePrompt": "reservation",
                    "lang": "en-US",
                    "last": True,
                }
            )
        )
        chunks: list[str] = []
        while True:
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "text"
            chunks.append(msg["token"])
            if msg.get("last"):
                break
    assert "name" in "".join(chunks).lower()
