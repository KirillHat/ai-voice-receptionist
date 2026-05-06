from datetime import datetime, timedelta, timezone

import pytest

from app.services.digest import build_payload, render_blocks
from app.storage.db import init_db, session_scope
from app.storage.models import CallSession, Lead


@pytest.mark.asyncio
async def test_build_payload_aggregates_calls_and_leads() -> None:
    await init_db()
    now = datetime.now(timezone.utc)
    async with session_scope() as db:
        db.add(
            CallSession(
                call_sid="DIG_A", caller_phone="+15555550001",
                intent="reservation", status="qualified",
                guest_name="Alice", party_size=4,
                created_at=now - timedelta(hours=2),
            )
        )
        db.add(
            CallSession(
                call_sid="DIG_B", caller_phone="+15555550002",
                intent="takeout", status="qualified",
                guest_name="Bob", created_at=now - timedelta(hours=1),
            )
        )
        db.add(
            Lead(
                call_sid="DIG_A", caller_phone="+15555550001",
                intent="reservation", guest_name="Alice", party_size=4,
                qualification_label="WARM", summary="Test reservation",
                created_at=now - timedelta(hours=2),
            )
        )
        db.add(
            Lead(
                call_sid="DIG_B", caller_phone="+15555550002",
                intent="takeout", guest_name="Bob",
                qualification_label="WARM", summary="Test takeout",
                created_at=now - timedelta(hours=1),
            )
        )

    payload = await build_payload()
    assert payload.total_calls >= 2
    assert payload.qualified_calls >= 2
    assert payload.intents.get("reservation", 0) >= 1
    assert payload.intents.get("takeout", 0) >= 1
    assert payload.labels.get("WARM", 0) >= 2
    assert payload.total_party >= 4

    blocks, summary = render_blocks(payload)
    assert "daily digest" in summary.lower()
    assert any(b.get("type") == "header" for b in blocks)
