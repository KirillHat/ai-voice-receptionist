from __future__ import annotations

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


def test_qualifier_completes_flow() -> None:
    call = _call()

    qualifier.ingest_turn(call, "I need a private event")
    qualifier.ingest_turn(call, "This is Maria Gomez")
    qualifier.ingest_turn(call, "party of 14")
    decision = qualifier.ingest_turn(call, "next friday 7 pm")

    assert decision.completed is True
    assert "I captured" in decision.prompt
    assert qualifier.qualification_label(call) == "HOT"
