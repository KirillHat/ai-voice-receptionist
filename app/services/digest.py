"""Daily digest of call activity, posted to Slack.

Wakes up at the configured local hour (default 23:00 in business_timezone),
aggregates the last 24 hours of calls/leads, posts a single Slack message,
sleeps until the next run.

Run as a long-lived task on app startup; or trigger one-off via the
/admin/digest endpoint for testing.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.services import slack_client
from app.storage.db import session_scope
from app.storage.models import CallSession, Lead

log = structlog.get_logger()


@dataclass
class DigestPayload:
    window_label: str
    total_calls: int
    qualified_calls: int
    intents: Counter
    labels: Counter
    total_party: int
    unanswered_questions: int
    sample_lead_names: list[str]


def _utc_window(now_local: datetime) -> tuple[datetime, datetime]:
    """24h window ending at `now_local`, expressed in UTC."""
    end = now_local.astimezone(timezone.utc)
    start = end - timedelta(hours=24)
    return start, end


async def build_payload(now_local: datetime | None = None) -> DigestPayload:
    settings = get_settings()
    tz = ZoneInfo(settings.business_timezone)
    if now_local is None:
        now_local = datetime.now(tz)
    start, end = _utc_window(now_local)

    intents: Counter[str] = Counter()
    labels: Counter[str] = Counter()
    sample_names: list[str] = []
    total_party = 0
    qualified = 0
    total_calls = 0

    async with session_scope() as db:
        calls_q = select(CallSession).where(
            CallSession.created_at >= start, CallSession.created_at < end
        )
        for call in (await db.execute(calls_q)).scalars():
            total_calls += 1
            if (call.status or "") == "qualified":
                qualified += 1
            if call.intent:
                intents[call.intent] += 1

        leads_q = select(Lead).where(
            Lead.created_at >= start, Lead.created_at < end
        )
        for lead in (await db.execute(leads_q)).scalars():
            labels[lead.qualification_label] += 1
            if lead.party_size:
                total_party += int(lead.party_size)
            if len(sample_names) < 5 and lead.guest_name:
                sample_names.append(lead.guest_name)

    return DigestPayload(
        window_label=now_local.strftime("%a, %b %-d"),
        total_calls=total_calls,
        qualified_calls=qualified,
        intents=intents,
        labels=labels,
        total_party=total_party,
        unanswered_questions=max(total_calls - qualified - intents.get("general", 0), 0),
        sample_lead_names=sample_names,
    )


def render_blocks(payload: DigestPayload) -> tuple[list[dict], str]:
    title = f"Novikov BH — daily digest ({payload.window_label})"
    intent_lines = "\n".join(
        f"• {intent}: {count}" for intent, count in sorted(payload.intents.items())
    ) or "—"
    label_lines = "\n".join(
        f"• {label}: {count}" for label, count in sorted(payload.labels.items())
    ) or "—"
    summary_text = (
        f"{title} — {payload.total_calls} calls, "
        f"{payload.qualified_calls} qualified, "
        f"{sum(payload.labels.values())} leads"
    )
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": title}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Calls*\n{payload.total_calls}"},
                {"type": "mrkdwn", "text": f"*Qualified*\n{payload.qualified_calls}"},
                {"type": "mrkdwn", "text": f"*Total guests booked*\n{payload.total_party}"},
                {"type": "mrkdwn", "text": f"*Unanswered*\n{payload.unanswered_questions}"},
            ],
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Intents*\n{intent_lines}"},
                {"type": "mrkdwn", "text": f"*Lead labels*\n{label_lines}"},
            ],
        },
    ]
    if payload.sample_lead_names:
        names = ", ".join(payload.sample_lead_names)
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Recent guests*\n{names}"},
            }
        )
    return blocks, summary_text


async def send_digest(now_local: datetime | None = None) -> bool:
    payload = await build_payload(now_local)
    blocks, summary_text = render_blocks(payload)
    log.info(
        "digest.summary",
        window=payload.window_label,
        calls=payload.total_calls,
        qualified=payload.qualified_calls,
        leads=sum(payload.labels.values()),
    )
    return await slack_client.post_digest(blocks, summary_text=summary_text)


async def _seconds_until(target_hour: int, target_minute: int = 0) -> float:
    settings = get_settings()
    tz = ZoneInfo(settings.business_timezone)
    now = datetime.now(tz)
    target = datetime.combine(now.date(), time(target_hour, target_minute), tzinfo=tz)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def run_daily(target_hour: int = 23, target_minute: int = 0) -> None:
    """Long-lived loop: sleep until target time, send digest, repeat."""
    while True:
        delay = await _seconds_until(target_hour, target_minute)
        log.info("digest.scheduled", sleep_sec=int(delay))
        await asyncio.sleep(delay)
        try:
            await send_digest()
        except Exception as exc:  # pragma: no cover — cron-style robustness
            log.exception("digest.failed", error=str(exc))
