"""Conversion-funnel aggregator over CallSession records.

A booking-intent caller progresses through stages: greeted → intent
captured → name captured → party captured → datetime captured → caller
confirmed (qualified). Each stage is a hurdle; tracking where calls drop
off tells us where to invest in the bot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import CallSession


# Order matters — each stage assumes everything above it is also captured.
STAGES: tuple[str, ...] = (
    "greeted",
    "intent_captured",
    "name_captured",
    "party_captured",
    "datetime_captured",
    "qualified",
)


@dataclass
class FunnelReport:
    window_hours: int
    total: int
    booking_total: int  # callers with booking intent only
    faq_only: int       # callers who asked questions but never started booking
    counts: dict[str, int]
    drop_off: dict[str, int]
    drop_rate: dict[str, float]


def _stage_for(call: CallSession) -> str:
    """Return the furthest stage this call reached.

    For booking intents (reservation/private_event) all four fields are
    needed before qualification. For takeout, only intent + name are
    required, so we treat that as 'datetime_captured' equivalent.
    """
    intent = call.intent or ""
    if call.status == "qualified":
        return "qualified"
    if call.reservation_datetime:
        return "datetime_captured"
    if call.party_size:
        return "party_captured"
    if call.guest_name:
        # Takeout doesn't need party/datetime, so a takeout-with-name is
        # essentially fully captured but unconfirmed.
        if intent == "takeout":
            return "datetime_captured"
        return "name_captured"
    if intent and intent != "general":
        return "intent_captured"
    return "greeted"


def _is_booking_caller(call: CallSession) -> bool:
    """A booking caller is one who reached at least 'intent_captured'.

    Pure FAQ/menu/allergy queries leave intent at None or 'general' and
    should not be counted in the booking funnel — they have no booking
    intent to drop from.
    """
    intent = call.intent or ""
    return intent in {"reservation", "private_event", "takeout"}


async def build_report(
    db: AsyncSession, *, window_hours: int = 168
) -> FunnelReport:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    q = select(CallSession).where(CallSession.created_at >= cutoff)
    all_calls = list((await db.execute(q)).scalars())

    booking_calls = [c for c in all_calls if _is_booking_caller(c)]
    faq_only = len(all_calls) - len(booking_calls)

    counts = dict.fromkeys(STAGES, 0)
    for call in booking_calls:
        reached = _stage_for(call)
        idx = STAGES.index(reached)
        for s in STAGES[: idx + 1]:
            counts[s] += 1

    drop_off: dict[str, int] = {}
    drop_rate: dict[str, float] = {}
    for cur, nxt in zip(STAGES, STAGES[1:]):
        delta = counts[cur] - counts[nxt]
        drop_off[f"{cur}->{nxt}"] = max(delta, 0)
        if counts[cur] > 0:
            drop_rate[f"{cur}->{nxt}"] = round(delta / counts[cur], 3)
        else:
            drop_rate[f"{cur}->{nxt}"] = 0.0

    return FunnelReport(
        window_hours=window_hours,
        total=len(all_calls),
        booking_total=len(booking_calls),
        faq_only=faq_only,
        counts=counts,
        drop_off=drop_off,
        drop_rate=drop_rate,
    )
