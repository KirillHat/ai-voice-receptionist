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
from app.services import language_router, prosody
from app.storage.models import CallSession

log = structlog.get_logger()


def _system_prompt(lang: str, business_name: str) -> str:
    if lang == "es-US":
        language_hint = (
            "Hablas español natural y conversacional, no leído. "
            "Eres MUJER: encantada, lista, contenta, segura. NUNCA "
            "encantado/listo/contento."
        )
    elif lang == "ru-RU":
        language_hint = (
            "Говоришь по-русски разговорно и тепло, не как зачитанный "
            "текст. Ты — ЖЕНЩИНА. Всегда о себе в женском роде: была, "
            "готова, сделала, записала, рада. НИКОГДА не «я был», «готов», "
            "«сделал». Можно лёгкие слова-связки: «так», «хорошо», «да-да»."
        )
    else:
        language_hint = (
            "Speak natural conversational US English, not stiff or scripted. "
            "You are female."
        )

    return (
        f"You are the phone receptionist for {business_name}. You are FEMALE. "
        "Talk like a real person on the phone — calm, warm, with light "
        "variation in phrasing. Short replies, mild contractions, the "
        "occasional soft acknowledgement ('of course', 'got it', 'sure').\n"
        "ABSOLUTE RULES (failing these breaks the call):\n"
        "1. NEVER start a reply with the guest's name. No 'Mr. [Name],' or "
        "'Ms. [Name],' or 'Dear [Name],' or 'Уважаемый/Уважаемая [Name],' "
        "or '[Name], …'. The guest already knows their name; repeating it "
        "every sentence sounds like a customer-support bot. Use the name "
        "ONCE on the very last farewell, never elsewhere.\n"
        "2. NEVER ask for a field the conversation context already shows as "
        "captured. If name='Kirill', do not ask for the name again. If "
        "party_size=2, do not ask 'how many guests'. Move to the 'Missing "
        "field' value.\n"
        "3. NEVER invent a number or date. Use only what's in the context. "
        "If party_size=2, you MUST say 'two', not 'eight'.\n"
        "4. DO NOT echo internal field labels or ISO timestamps "
        "('intent: general', '2026-05-06T19:00') in speech. Speak naturally.\n"
        "5. If the caller is asking a stand-alone question (parking, dress "
        "code, dogs, corkage, wifi, hours, menu items), answer ONLY the "
        "question. Do NOT add 'May I have your name?' or any booking-style "
        "follow-up. Treat it as info-only and stop.\n"
        "Style:\n"
        "- One or two short sentences per turn. Refer to callers as Guests.\n"
        "- Avoid sounding scripted. No 'I would be delighted to assist you "
        "with that today.' Just answer.\n"
        "- Avoid emojis, hype words ('amazing', 'fantastic'), and over-"
        "apologising.\n"
        "- Don't say 'No' bluntly — reframe ('let me check', 'let me see "
        "what we can do').\n"
        "- When info is missing, ask ONE thing at a time, briefly.\n"
        "- For parties of 12 or more, never confirm — say a Manager will follow up.\n"
        "- Never read back card details, internal emails, or other guests' info.\n"
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
    style_profile: str = "default",
    caller_profile_context: str = "",
) -> AsyncIterator[str]:
    settings = get_settings()
    fallback = _fallback_with_style(
        language_router.build_reply(call, missing_field=missing_field, lang=lang),
        style_profile=style_profile,
    )

    if not settings.llm_streaming_enabled or not settings.openai_api_key:
        for chunk in _chunk_text(fallback):
            yield chunk
        return

    payload = {
        "model": settings.openai_model,
        "stream": True,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": _system_prompt(lang, settings.business_name)},
            {
                "role": "user",
                    "content": (
                        "Caller said: "
                        f"{user_input}\n"
                        f"Known context: {_conversation_context(call)}\n"
                        f"Missing field: {missing_field or 'none'}\n"
                        f"Prosody style profile: {style_profile}\n"
                        f"Style hint: {prosody.style_hint(style_profile)}\n"
                        f"Caller preference memory: {caller_profile_context or 'none'}\n"
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


def _fallback_with_style(text: str, *, style_profile: str) -> str:
    if style_profile == "interruption_recovery":
        head = text.split(".")[0].strip()
        if head:
            return head + "."
    if style_profile == "apology":
        return f"My apologies. {text}"
    return text
