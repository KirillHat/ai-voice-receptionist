"""Slack notifier for qualified leads."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger()


async def notify_lead(lead: dict[str, Any]) -> bool:
    settings = get_settings()
    if not settings.slack_webhook_url:
        return False

    payload = {
        "text": f"New voice lead: {lead['qualification_label']} - {lead['guest_name']}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": (
                        f"{lead['qualification_label']} voice lead "
                        f"from {lead['guest_name']}"
                    ),
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Intent*\n{lead['intent']}"},
                    {"type": "mrkdwn", "text": f"*Caller*\n{lead['caller_phone']}"},
                    {"type": "mrkdwn", "text": f"*Party size*\n{lead.get('party_size') or '-'}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Date/time*\n{lead.get('reservation_datetime') or '-'}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f">_{lead['summary']}_"},
            },
        ],
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            settings.slack_webhook_url.get_secret_value(),
            json=payload,
        )

    if response.status_code != 200:
        log.warning("slack.notify_non_200", status=response.status_code, body=response.text)
    return response.status_code == 200
