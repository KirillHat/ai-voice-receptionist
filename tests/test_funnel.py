import pytest

from app.services.funnel import _stage_for, build_report
from app.storage.db import init_db, session_scope
from app.storage.models import CallSession


def _call(**kwargs) -> CallSession:
    base = {
        "call_sid": kwargs.pop("call_sid", "FN_X"),
        "caller_phone": kwargs.pop("caller_phone", "+15555550000"),
        "intent": None,
        "guest_name": None,
        "party_size": None,
        "reservation_datetime": None,
        "status": "in_progress",
        "turn_count": 0,
        "transcript": [],
    }
    base.update(kwargs)
    return CallSession(**base)


def test_stage_for_each_milestone() -> None:
    assert _stage_for(_call()) == "greeted"
    assert _stage_for(_call(intent="reservation")) == "intent_captured"
    assert _stage_for(_call(intent="reservation", guest_name="A")) == "name_captured"
    assert _stage_for(_call(intent="reservation", guest_name="A", party_size=2)) == "party_captured"
    assert (
        _stage_for(_call(intent="reservation", guest_name="A", party_size=2,
                         reservation_datetime="2026-05-09T20:00")) == "datetime_captured"
    )
    qualified = _call(intent="reservation", guest_name="A", party_size=2,
                      reservation_datetime="2026-05-09T20:00", status="qualified")
    assert _stage_for(qualified) == "qualified"


def test_takeout_fast_path_skips_party_datetime() -> None:
    assert _stage_for(_call(intent="takeout", guest_name="Bob")) == "datetime_captured"


@pytest.mark.asyncio
async def test_build_report_counts_and_drops() -> None:
    await init_db()
    async with session_scope() as db:
        # 3 callers reach intent, 2 give a name, 1 confirms.
        db.add_all([
            _call(call_sid="F1", caller_phone="+15551111111"),  # greeted only
            _call(call_sid="F2", caller_phone="+15552222222", intent="reservation"),
            _call(call_sid="F3", caller_phone="+15553333333",
                  intent="reservation", guest_name="N"),
            _call(call_sid="F4", caller_phone="+15554444444",
                  intent="reservation", guest_name="M",
                  party_size=4, reservation_datetime="2026-05-09T20:00",
                  status="qualified"),
        ])

    async with session_scope() as db:
        report = await build_report(db, window_hours=24)

    # Booking-only calls (3 of the 4 seeded), greeted-only caller is faq_only.
    assert report.booking_total >= 3
    assert report.faq_only >= 1
    assert report.counts["greeted"] >= 3
    assert report.counts["qualified"] >= 1
    # Drop rate is a 0..1 fraction
    assert 0.0 <= report.drop_rate["greeted->intent_captured"] <= 1.0
