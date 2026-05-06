"""Core webhook tests for the Twilio Voice flow."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.services.turn_taking import TurnTiming


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
        client.post(
            "/webhooks/voice/collect",
            data={
                "CallSid": "CA222",
                "From": "+13105550102",
                "SpeechResult": "tomorrow at 8 pm",
            },
        )
        # Read-back loop adds a confirmation turn before the fan-out fires.
        r = client.post(
            "/webhooks/voice/collect",
            data={
                "CallSid": "CA222",
                "From": "+13105550102",
                "SpeechResult": "yes that's correct",
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


def test_websocket_sends_holding_phrase_when_first_chunk_is_slow(
    client: TestClient,
) -> None:
    async def _slow_reply(**_: str):
        await asyncio.sleep(0.08)
        yield "May I have your full name for the booking note?"

    try:
        with patch(
            "app.webhooks.voice.llm_stream.stream_reply",
            _slow_reply,
        ), patch(
            "app.webhooks.voice.turn_taking.compute_timing",
            return_value=TurnTiming(pause_ms=0, holding_delay_ms=40, utterance_kind="fast"),
        ), client.websocket_connect("/ws/conversationrelay") as ws:
            ws.send_text(json.dumps({"type": "setup", "callSid": "CAWSH1", "from": "+13105550012"}))
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
            messages: list[dict[str, object]] = []
            for _ in range(4):
                item = json.loads(ws.receive_text())
                messages.append(item)
                if item.get("type") == "text" and item.get("last") is True:
                    break
        text_tokens = [str(item.get("token", "")) for item in messages if item.get("type") == "text"]
        assert any("one moment" in token.lower() for token in text_tokens)
        assert messages[-1].get("last") is True
    finally:
        get_settings.cache_clear()


def test_websocket_interrupt_recovery_acknowledges_before_continuing(client: TestClient) -> None:
    async def _reply(**_: str):
        yield "May I have your full name"
        yield " for the booking note?"

    with patch(
        "app.webhooks.voice.llm_stream.stream_reply",
        _reply,
    ), client.websocket_connect("/ws/conversationrelay") as ws:
        ws.send_text(json.dumps({"type": "setup", "callSid": "CAWSI1", "from": "+13105550013"}))
        ws.send_text(
            json.dumps(
                {
                    "type": "interrupt",
                    "durationUntilInterruptMs": 450,
                }
            )
        )
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
        messages: list[dict[str, object]] = []
        for _ in range(5):
            item = json.loads(ws.receive_text())
            messages.append(item)
            if item.get("type") == "text" and item.get("last") is True:
                break
    text_messages = [item for item in messages if item.get("type") == "text"]
    assert text_messages[0].get("last") is False
    assert "of course" in str(text_messages[0].get("token", "")).lower()
    assert text_messages[-1].get("last") is True


def test_websocket_combines_partial_prompt_chunks(client: TestClient) -> None:
    captured: dict[str, str] = {}

    async def _reply(*, user_input: str, **_: str):
        captured["user_input"] = user_input
        yield "Thanks."

    with patch(
        "app.webhooks.voice.llm_stream.stream_reply",
        _reply,
    ), client.websocket_connect("/ws/conversationrelay") as ws:
        ws.send_text(json.dumps({"type": "setup", "callSid": "CAWSP1", "from": "+13105550014"}))
        ws.send_text(
            json.dumps(
                {
                    "type": "prompt",
                    "voicePrompt": "I need a",
                    "lang": "en-US",
                    "last": False,
                }
            )
        )
        ws.send_text(
            json.dumps(
                {
                    "type": "prompt",
                    "voicePrompt": "reservation tomorrow at 8",
                    "lang": "en-US",
                    "last": True,
                }
            )
        )
        msg = json.loads(ws.receive_text())
    assert msg["type"] == "text"
    assert msg["last"] is True
    assert captured["user_input"] == "I need a reservation tomorrow at 8"
