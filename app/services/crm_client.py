"""Push qualified leads to a generic CRM webhook endpoint."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger()


async def push_lead(lead: dict[str, Any]) -> bool:
    settings = get_settings()
    if not settings.crm_webhook_url:
        return False

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.crm_auth_bearer:
        headers["Authorization"] = f"Bearer {settings.crm_auth_bearer.get_secret_value()}"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(settings.crm_webhook_url, json=lead, headers=headers)

    if response.status_code >= 300:
        log.warning("crm.push_non_2xx", status=response.status_code, body=response.text)
        return False
    return True
