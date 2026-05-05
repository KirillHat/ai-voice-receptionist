"""Prosody and phrasing helpers for a more human voice experience."""

from __future__ import annotations

import hashlib

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
