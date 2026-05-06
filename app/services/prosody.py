"""Prosody and phrasing helpers for a more human voice experience."""

from __future__ import annotations

import hashlib
import re

from app.config import get_settings

_PROFILE_HINTS = {
    "greeting": "Tone: welcoming, polished, one concise sentence then a gentle question.",
    "clarification": "Tone: light curiosity, concise, ask for one missing detail only.",
    "confirmation": "Tone: assured and warm, brief confirmation with one key detail.",
    "apology": "Tone: calm and graceful apology, no over-apologizing, move forward quickly.",
    "interruption_recovery": "Tone: very short, soft, continue from context; do not restart full reply.",
    "default": "Tone: polished and natural, two short sentences max.",
}

_HOLDING_PHRASES = {
    "en-US": "One moment, please.",
    "es-US": "Un momento, por favor.",
    "ru-RU": "Одну секунду, пожалуйста.",
}

_INTERRUPTION_ACK = {
    "en-US": "Of course.",
    "es-US": "Claro.",
    "ru-RU": "Конечно.",
}

_DISFLUENCY_MARKERS = {
    "en-US": ("certainly", "of course", "one moment"),
    "es-US": ("claro", "por supuesto", "un momento"),
    "ru-RU": ("конечно", "разумеется", "одну секунду"),
}


def style_hint(profile: str) -> str:
    return _PROFILE_HINTS.get(profile, _PROFILE_HINTS["default"])


def holding_phrase(lang: str) -> str:
    return _HOLDING_PHRASES.get(lang, _HOLDING_PHRASES["en-US"])


def interruption_ack(lang: str) -> str:
    return _INTERRUPTION_ACK.get(lang, _INTERRUPTION_ACK["en-US"])


_NAME_OPENER_PATTERNS = (
    r"^(?:dear|mr\.?|ms\.?|mrs\.?|miss)\s+[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё'\-]+\s*[,—-]?\s*",
    r"^(?:уважаем(?:ый|ая))\s+[А-ЯЁA-Z][А-Яа-яЁёA-Za-z'\-]+\s*[,—-]?\s*",
    r"^[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё'\-]{1,30}\s*,\s+",
    r"^привет\s*,\s*[А-ЯЁ][А-Яа-яЁё'\-]+\s*[,—-]?\s*",
    r"^(?:hi|hello|hey)\s*,?\s*[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё'\-]+\s*[,—-]?\s*",
)


def strip_leading_name_address(text: str, *, guest_name: str | None) -> str:
    """Remove 'Mr. Kirill,' / 'Уважаемый Кирилл,' / 'Kirill,' from the head.

    The system prompt forbids opening every reply with the guest's name,
    but gpt-4o still does it on perhaps half the turns. We post-process
    the first chunk of the streamed reply to drop that opener.
    """
    if not text:
        return text
    cleaned = text.lstrip()
    leading_ws = text[: len(text) - len(cleaned)]

    for pat in _NAME_OPENER_PATTERNS:
        match = re.match(pat, cleaned, flags=re.IGNORECASE)
        if match:
            cleaned = cleaned[match.end():]
            break

    if guest_name:
        # 'Kirill, ' or 'Кирилл, ' specifically — prefix-trim by exact name.
        first = guest_name.split()[0]
        prefix_pat = rf"^{re.escape(first)}\s*[,—-]\s*"
        match = re.match(prefix_pat, cleaned, flags=re.IGNORECASE)
        if match:
            cleaned = cleaned[match.end():]

    cleaned = cleaned.lstrip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return leading_ws + cleaned


def maybe_add_disfluency(text: str, *, lang: str, call_sid: str, turn_count: int) -> str:
    settings = get_settings()
    if not text.strip():
        return text
    if turn_count <= 0 or settings.voice_disfluency_rate <= 0:
        return text

    token = f"{call_sid}:{turn_count}:{lang}".encode()
    score = int(hashlib.sha256(token).hexdigest()[:8], 16) / 0xFFFFFFFF
    if score > settings.voice_disfluency_rate:
        return text

    marker = _DISFLUENCY_MARKERS.get(lang, _DISFLUENCY_MARKERS["en-US"])[turn_count % 3]
    lowered = text.lower().strip()
    if marker in lowered:
        return text

    if lang == "ru-RU":
        return f"{marker.capitalize()}, {text}"
    return f"{marker.capitalize()}. {text}"
