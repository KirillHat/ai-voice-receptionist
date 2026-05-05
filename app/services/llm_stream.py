"""Streaming reply generation for ConversationRelay.

If OpenAI credentials are configured, stream tokens from Chat Completions SSE.
Otherwise, fallback to deterministic local prompt generation.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import structlog

from app.config import get_settings
from app.services import language_router
from app.storage.models import CallSession

log = structlog.get_logger()


def _system_prompt(lang: str, business_name: str) -> str:
    if lang == "es-US":
        language_hint = "Responde en español claro y natural, formal pero cálido."
    elif lang == "ru-RU":
        language_hint = "Отвечай по-русски, вежливо и сдержанно, в стиле fine-dining."
    else:
        language_hint = "Reply in natural US English."

    return (
        f"You are the phone receptionist for {business_name}, a fine-dining "
        "Italian-themed restaurant. Voice persona: classy, sophisticated, "
        "understated, confident, polished, and precise. Warm but reserved.\n"
        "Style rules:\n"
        "- One or two short sentences per turn. Refer to callers as Guests, "
        "never customers.\n"
        "- Avoid: emojis, multiple exclamations, slang ('yummy', 'awesome', "
        "'no problem', 'totally', 'you guys', 'hey'), hype words ('amazing', "
        "'fantastic', 'the best'), and over-apologising.\n"
        "- Substitutions: say 'My pleasure' (not 'no problem'); 'Let me find "
        "that out for you' (not 'I don't know'); 'May I offer you...' (not "
        "'can I grab you'); 'That item is currently unavailable — I'd be "
        "happy to recommend an alternative' (not 'we're out of that'). "
        "Avoid the word 'No' — reframe as 'Let me check with my Manager' "
        "or 'Let me take care of that for you'.\n"
        "- When info is missing, ask ONE thing at a time.\n"
        "- For parties of 12 or more, never confirm — say a Manager will confirm.\n"
        "- Never read back card details, internal email addresses, or other "
        "guests' information.\n"
        f"{language_hint}"
    )


def _conversation_context(call: CallSession) -> str:
    return (
        f"intent={call.intent or ''}; "
        f"name={call.guest_name or ''}; "
        f"party_size={call.party_size or ''}; "
        f"reservation_datetime={call.reservation_datetime or ''}; "
        f"notes={call.special_notes or ''}; "
        f"status={call.status}; "
        f"turn_count={call.turn_count or 0}"
    )


async def stream_reply(
    *,
    call: CallSession,
    user_input: str,
    missing_field: str | None,
    lang: str,
) -> AsyncIterator[str]:
    settings = get_settings()
    fallback = language_router.build_reply(call, missing_field=missing_field, lang=lang)

    if not settings.llm_streaming_enabled or not settings.openai_api_key:
        for chunk in _chunk_text(fallback):
            yield chunk
        return

    payload = {
        "model": settings.openai_model,
        "stream": True,
        "temperature": 0.35,
        "messages": [
            {"role": "system", "content": _system_prompt(lang, settings.business_name)},
            {
                "role": "user",
                "content": (
                    "Caller said: "
                    f"{user_input}\n"
                    f"Known context: {_conversation_context(call)}\n"
                    f"Missing field: {missing_field or 'none'}\n"
                    "Craft next phone utterance now."
                ),
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }

    full = ""
    try:
        async with httpx.AsyncClient(timeout=35) as client, client.stream(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue

                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if not content:
                    continue

                full += content
                yield content
    except Exception as exc:
        log.warning("llm.stream_fallback", error=str(exc))
        for chunk in _chunk_text(fallback):
            yield chunk
        return

    if not full.strip():
        for chunk in _chunk_text(fallback):
            yield chunk


def _chunk_text(text: str) -> list[str]:
    words = text.strip().split()
    if not words:
        return ["Could you please repeat that?"]
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        if len(current) >= 5:
            chunks.append(" ".join(current) + " ")
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks
