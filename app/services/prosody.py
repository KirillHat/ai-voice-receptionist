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
    "en-US": (
        "of course", "certainly", "sure", "got it", "alright",
        "okay", "let me see", "let's see", "hmm", "well",
        "absolutely", "right",
    ),
    "es-US": (
        "claro", "por supuesto", "perfecto", "muy bien", "bueno",
        "a ver", "pues", "vale", "entendido", "okay",
    ),
    "ru-RU": (
        "конечно", "разумеется", "хорошо", "понятно", "ага",
        "так", "сейчас", "ну", "ясно", "так-так",
    ),
}

# Soft "thinking" interjections that sound like a real person taking a
# half-beat to think — used sparingly and only when the reply is a
# multi-clause answer (confirmations, multi-detail FAQ).
_THINKING_INTERJECTIONS = {
    "en-US": ("Mmm,", "Hmm,", "Right,", "So,"),
    "es-US": ("Mmm,", "Hmm,", "Bueno,", "Así que,"),
    "ru-RU": ("Ммм,", "Так,", "Угу,", "Хорошо,"),
}


def style_hint(profile: str) -> str:
    return _PROFILE_HINTS.get(profile, _PROFILE_HINTS["default"])


def holding_phrase(lang: str) -> str:
    return _HOLDING_PHRASES.get(lang, _HOLDING_PHRASES["en-US"])


def interruption_ack(lang: str) -> str:
    return _INTERRUPTION_ACK.get(lang, _INTERRUPTION_ACK["en-US"])


_HOLD_PATTERNS: tuple[str, ...] = (
    r"\bhold on\b",
    r"\bhang on\b",
    r"\bone (?:second|sec|moment|minute)\b",
    r"\bjust a (?:second|sec|moment|minute)\b",
    r"\bgive me a (?:second|sec|moment|minute)\b",
    r"\blet me (?:check|see|think|grab|look)\b",
    r"\bпогоди\w*\b",
    r"\bсекундочк\w*\b",
    r"\bодну секунд\w*\b",
    r"\bминуточк\w*\b",
    r"\bподожди\w*\b",
    r"\bдай(?:те)?\s+(?:мне|мин|секунд)\w*\b",
    r"\bсейчас\s+посмотрю\b",
    r"\bun momento\b",
    r"\bun segundo\b",
    r"\bdéjeme\s+(?:revisar|ver|pensar)\b",
    r"\bdame un momento\b",
    r"\bespera\w*\b",
)
_HOLD_ACK = {
    "en-US": "Of course, take your time.",
    "es-US": "Por supuesto, tómese su tiempo.",
    "ru-RU": "Конечно, не торопитесь.",
}


_SILENCE_NUDGE = {
    "en-US": "Are you still there?",
    "es-US": "¿Sigue ahí?",
    "ru-RU": "Вы на линии?",
}
_SILENCE_GIVEUP = {
    "en-US": (
        "I haven't heard from you in a moment. "
        "Our team will give you a call back shortly. Have a wonderful day."
    ),
    "es-US": (
        "Parece que no le escucho. "
        "Nuestro equipo le devolverá la llamada en breve. Que tenga un buen día."
    ),
    "ru-RU": (
        "Кажется, связь пропала. "
        "Наша команда перезвонит вам в ближайшее время. Хорошего дня."
    ),
}


def silence_nudge(lang: str) -> str:
    return _SILENCE_NUDGE.get(lang, _SILENCE_NUDGE["en-US"])


def silence_giveup(lang: str) -> str:
    return _SILENCE_GIVEUP.get(lang, _SILENCE_GIVEUP["en-US"])


def detect_hold_request(utterance: str) -> bool:
    """True when the caller is asking us to pause ('hold on, let me check')."""
    if not utterance:
        return False
    lower = utterance.lower().strip()
    return any(re.search(pat, lower) for pat in _HOLD_PATTERNS)


def hold_acknowledgement(lang: str) -> str:
    return _HOLD_ACK.get(lang, _HOLD_ACK["en-US"])


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
    """Maybe prepend a natural conversational marker ("of course", "так",
    "let me see") to the start of the bot's reply.

    The marker is picked deterministically per (call_sid, turn) so a
    given call has consistent variety, but rotates across the wider
    pool of options below. Gated by voice_disfluency_rate (default
    18%) — most replies stay clean, only a fraction get a soft opener.
    """
    settings = get_settings()
    if not text.strip():
        return text
    if turn_count <= 0 or settings.voice_disfluency_rate <= 0:
        return text

    token = f"{call_sid}:{turn_count}:{lang}".encode()
    digest = hashlib.sha256(token).hexdigest()
    score = int(digest[:8], 16) / 0xFFFFFFFF
    if score > settings.voice_disfluency_rate:
        return text

    pool = _DISFLUENCY_MARKERS.get(lang, _DISFLUENCY_MARKERS["en-US"])
    pick_idx = int(digest[8:14], 16) % len(pool)
    marker = pool[pick_idx]

    lowered = text.lower().strip()
    if any(lowered.startswith(m) for m in pool):
        # Don't double-stack markers if the LLM already started with one.
        return text

    if lang == "ru-RU":
        return f"{marker.capitalize()}, {text}"
    return f"{marker.capitalize()}, {text}"


def maybe_add_thinking_pause(text: str, *, lang: str, call_sid: str, turn_count: int) -> str:
    """For multi-clause answers, occasionally inject a brief 'mmm,' lead
    or an ellipsis after the first comma so the line carries a natural
    pause (ElevenLabs reads '…' as a thoughtful beat).

    Used independently of the prefix marker, gated by the same rate so
    we don't overload the reply with fillers.
    """
    settings = get_settings()
    if not text.strip() or turn_count <= 0:
        return text
    rate = settings.voice_disfluency_rate
    if rate <= 0:
        return text

    token = f"thinking:{call_sid}:{turn_count}:{lang}".encode()
    digest = hashlib.sha256(token).hexdigest()
    score = int(digest[:8], 16) / 0xFFFFFFFF
    # Half the disfluency rate — these are heavier and we want them rarer.
    if score > rate * 0.5:
        return text

    pool = _THINKING_INTERJECTIONS.get(lang, _THINKING_INTERJECTIONS["en-US"])
    pick = pool[int(digest[8:14], 16) % len(pool)]
    # Avoid stacking if reply already opens with a soft marker.
    head = text.lstrip()
    if not head:
        return text
    first_word = head.split()[0].lower().rstrip(",.!?")
    skip_prefixes = {m.split()[0].lower() for m in _DISFLUENCY_MARKERS.get(lang, ()) if m}
    skip_prefixes.update({"mmm", "ммм", "hmm"})
    if first_word in skip_prefixes:
        return text
    return f"{pick} {text}"
