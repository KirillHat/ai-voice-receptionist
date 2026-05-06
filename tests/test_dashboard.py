import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.db import init_db, session_scope
from app.storage.models import CallSession, Lead


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.mark.asyncio
async def _seed() -> None:
    await init_db()
    async with session_scope() as db:
        db.add(
            CallSession(
                call_sid="DASH_A", caller_phone="+15551112222",
                intent="reservation", guest_name="Olga", party_size=4,
                reservation_datetime="2026-05-09T20:00-07:00",
                status="qualified", turn_count=4,
                transcript=[
                    {"role": "caller", "text": "I'd like a table for 4"},
                    {"role": "assistant", "text": "May I have your name?"},
                    {"role": "caller", "text": "Olga"},
                    {"role": "assistant", "text": "Just to confirm: ..."},
                ],
            )
        )
        db.add(
            Lead(
                call_sid="DASH_A", caller_phone="+15551112222",
                intent="reservation", guest_name="Olga", party_size=4,
                reservation_datetime="2026-05-09T20:00-07:00",
                qualification_label="WARM", summary="Test booking",
            )
        )


def test_dashboard_renders(client) -> None:
    import asyncio
    asyncio.run(_seed())

    r = client.get("/dashboard")
    assert r.status_code == 200
    body = r.text
    assert "Receptionist dashboard" in body
    assert "Olga" in body
    assert "WARM" in body


def test_call_detail_renders(client) -> None:
    import asyncio
    asyncio.run(_seed())

    r = client.get("/dashboard/call/DASH_A")
    assert r.status_code == 200
    assert "DASH_A" in r.text
    assert "Olga" in r.text
    assert "table for 4" in r.text  # transcript visible


def test_call_detail_404_for_missing(client) -> None:
    r = client.get("/dashboard/call/DOES_NOT_EXIST")
    assert r.status_code == 404
