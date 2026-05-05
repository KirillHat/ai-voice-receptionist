"""SevenRooms reservation handoff.

SevenRooms API contracts are partner-specific in many deployments, so this
client is intentionally configurable and can be swapped per venue onboarding.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger()


async def create_reservation(lead: dict[str, Any]) -> bool:
    settings = get_settings()
    if not settings.enable_sevenrooms:
        return False
    if not settings.sevenrooms_api_base_url or not settings.sevenrooms_api_key:
        return False

    if lead.get("intent") not in {"reservation", "private_event"}:
        return False

    url = settings.sevenrooms_api_base_url.rstrip("/") + "/reservations"
    payload = {
        "venue_id": settings.sevenrooms_venue_id,
        "guest_name": lead.get("guest_name"),
        "phone": lead.get("caller_phone"),
        "party_size": lead.get("party_size"),
        "requested_at": lead.get("reservation_datetime"),
        "notes": lead.get("special_notes"),
        "source": "ai_voice_receptionist",
    }

    headers = {
        "Authorization": f"Bearer {settings.sevenrooms_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code >= 300:
        log.warning(
            "sevenrooms.create_non_2xx",
            status=response.status_code,
            body=response.text,
        )
        return False
    return True
