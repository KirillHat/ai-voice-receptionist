from __future__ import annotations

import re

from app.services import qualifier
from app.storage.models import CallSession


def _call() -> CallSession:
    return CallSession(call_sid="CA123", caller_phone="+13105550000")


def test_qualifier_extracts_reservation_fields() -> None:
    call = _call()

    qualifier.ingest_turn(call, "Hi, I need a reservation tomorrow at 8 pm for 4")
    qualifier.ingest_turn(call, "My name is John Carter")

    assert call.intent == "reservation"
    assert call.party_size == 4
    assert call.guest_name == "John Carter"
    assert call.reservation_datetime is not None
    assert "T20:00" in call.reservation_datetime


def test_qualifier_completes_flow() -> None:
    call = _call()

    qualifier.ingest_turn(call, "I need a private event")
    qualifier.ingest_turn(call, "This is Maria Gomez")
    qualifier.ingest_turn(call, "party of 14")
    decision = qualifier.ingest_turn(call, "next friday 7 pm")

    assert decision.completed is True
    # Natural-language confirmation: must mention the captured fields by
    # value, NEVER echo internal labels like 'intent: ' or raw ISO timestamps.
    prompt = decision.prompt
    assert "Maria Gomez" in prompt
    assert "private event" in prompt.lower()
    assert "intent:" not in prompt.lower()
    assert "party_size:" not in prompt.lower()
    assert "T19:00" not in prompt  # ISO leakage
    assert qualifier.qualification_label(call) == "HOT"
    assert "T19:00" in (call.reservation_datetime or "")


def test_qualifier_rejects_non_datetime_short_reply() -> None:
    call = _call()
    qualifier.ingest_turn(call, "reservation")
    qualifier.ingest_turn(call, "my name is alex")
    qualifier.ingest_turn(call, "for 4")
    decision = qualifier.ingest_turn(call, "not sure yet")

    assert decision.completed is False
    assert call.reservation_datetime is None


def test_qualifier_normalizes_multilingual_datetime_phrases() -> None:
    call = _call()
    qualifier.ingest_turn(call, "reservation")
    qualifier.ingest_turn(call, "my name is alex")
    qualifier.ingest_turn(call, "for 4")
    qualifier.ingest_turn(call, "в пятницу к восьми")
    assert re.search(r"T08:00|T20:00", call.reservation_datetime or "")

    call2 = _call()
    qualifier.ingest_turn(call2, "reservation")
    qualifier.ingest_turn(call2, "my name is alex")
    qualifier.ingest_turn(call2, "for 2")
    qualifier.ingest_turn(call2, "mañana a las ocho")
    assert re.search(r"T08:00|T20:00", call2.reservation_datetime or "")
