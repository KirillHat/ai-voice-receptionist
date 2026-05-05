"""Lead qualification logic for voice calls.

This is intentionally deterministic for predictable demos and easy testing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.storage.models import CallSession

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "reservation": (
        "reservation",
        "table",
        "book",
        "booking",
        "dinner",
        "lunch",
        "reserva",
        "mesa",
        "бронир",
    ),
    "private_event": (
        "private",
        "event",
        "party",
        "birthday",
        "corporate",
        "evento",
        "evento privado",
        "мероприят",
        "банкет",
    ),
    "takeout": (
        "takeout",
        "pickup",
        "delivery",
        "order",
        "para llevar",
        "recoger",
        "доставка",
        "самовывоз",
    ),
}

_NUMBER_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "один": 1,
    "два": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
}


@dataclass
class TurnDecision:
    prompt: str
    completed: bool
    missing_field: str | None = None


def required_fields(intent: str | None) -> tuple[str, ...]:
    if intent in {"reservation", "private_event"}:
        return ("intent", "guest_name", "party_size", "reservation_datetime")
    if intent == "takeout":
        return ("intent", "guest_name")
    return ("intent", "guest_name", "reservation_datetime")


def ingest_turn(session: CallSession, utterance: str) -> TurnDecision:
    text = _clean(utterance)
    if not text:
        return TurnDecision(
            prompt="Sorry, I did not catch that. Please repeat in one short sentence.",
            completed=False,
            missing_field=None,
        )

    _append_transcript(session, role="caller", text=text)
    _extract_fields(session, text)
    session.turn_count = int(session.turn_count or 0) + 1

    missing = _missing_fields(session)
    if not missing:
        summary = summarize(session)
        _append_transcript(session, role="assistant", text=summary)
        return TurnDecision(prompt=summary, completed=True)

    next_field = missing[0]
    prompt = _prompt_for(next_field, session.intent)
    _append_transcript(session, role="assistant", text=prompt)
    return TurnDecision(prompt=prompt, completed=False, missing_field=next_field)


def note_faq_turn(session: CallSession, utterance: str, answer: object) -> None:
    """Record an FAQ exchange in the transcript without advancing qualification.

    FAQ matches are answered by the deterministic matcher before the qualifier
    runs, so we still want the back-and-forth visible in the call transcript
    for analytics, but we should not treat the question as a missing-field
    response.
    """
    text = _clean(utterance)
    if not text:
        return
    _append_transcript(session, role="caller", text=text)
    answer_text = getattr(answer, "text", "") or ""
    if answer_text:
        _append_transcript(session, role="assistant", text=answer_text)
    session.turn_count = int(session.turn_count or 0) + 1


def summarize(session: CallSession) -> str:
    intent_label = {
        "reservation": "table reservation",
        "private_event": "private event inquiry",
        "takeout": "takeout inquiry",
        "general": "general inquiry",
    }.get(session.intent or "general", "inquiry")

    details: list[str] = [f"{intent_label}"]
    if session.guest_name:
        details.append(f"name: {session.guest_name}")
    if session.party_size:
        details.append(f"party size: {session.party_size}")
    if session.reservation_datetime:
        details.append(f"time: {session.reservation_datetime}")
    if session.special_notes:
        details.append(f"notes: {session.special_notes}")

    joined = "; ".join(details)
    return (
        "Perfect, thank you. I have everything I need and our team will confirm shortly. "
        f"I captured: {joined}."
    )


def qualification_label(session: CallSession) -> str:
    if session.intent == "private_event":
        if (session.party_size or 0) >= 12:
            return "HOT"
        return "WARM"
    if session.intent == "reservation":
        if (session.party_size or 0) >= 6:
            return "HOT"
        return "WARM"
    if session.intent == "takeout":
        return "WARM"
    return "COLD"


def _missing_fields(session: CallSession) -> list[str]:
    missing: list[str] = []
    fields = required_fields(session.intent)
    for field in fields:
        if getattr(session, field, None) in (None, ""):
            missing.append(field)
    return missing


def _extract_fields(session: CallSession, text: str) -> None:
    if not session.intent:
        session.intent = _extract_intent(text)

    if not session.guest_name:
        maybe_name = _extract_name(text)
        if maybe_name:
            session.guest_name = maybe_name

    if session.party_size is None:
        maybe_party = _extract_party_size(text)
        if maybe_party:
            session.party_size = maybe_party

    if not session.reservation_datetime:
        maybe_time = _extract_datetime_phrase(text)
        if maybe_time:
            session.reservation_datetime = maybe_time

    if not session.special_notes:
        maybe_notes = _extract_notes(text)
        if maybe_notes:
            session.special_notes = maybe_notes


def _extract_intent(text: str) -> str:
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(word in text for word in keywords):
            return intent
    return "general"


def _extract_name(text: str) -> str | None:
    patterns = [
        r"(?:my name is|this is|i am|i'm)\s+([a-z][a-z\-\s']{1,40})",
        r"(?:name)\s+([a-z][a-z\-\s']{1,40})",
        r"(?:me llamo|soy)\s+([a-záéíóúñ][a-záéíóúñ\-\s']{1,40})",
        r"(?:меня зовут|это)\s+([а-яё][а-яё\-\s']{1,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _title_case(match.group(1).strip(" .,!"))
    return None


def _extract_party_size(text: str) -> int | None:
    digit_match = re.search(
        r"(?:party of|for|we are|we're|para|somos|нас|на)\s+(\d{1,2})\b",
        text,
    )
    if digit_match:
        value = int(digit_match.group(1))
        if 1 <= value <= 30:
            return value

    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", text):
            return value
    return None


def _extract_datetime_phrase(text: str) -> str | None:
    relative_tokens = ("today", "tonight", "tomorrow", "next ")
    date_time_patterns = [
        r"\b(?:today|tonight|tomorrow)\b",
        r"\bnext\s+\w+(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?",
        r"\b\d{1,2}[:.]\d{2}\s*(?:am|pm)?\b",
        r"\b\d{1,2}\s*(?:am|pm)\b",
        r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?\b",
    ]

    matches: list[str] = []
    for pattern in date_time_patterns:
        for m in re.finditer(pattern, text):
            matches.append(m.group(0).strip())

    if matches:
        return " ".join(dict.fromkeys(matches))[:120]

    if any(token in text for token in relative_tokens):
        return text[:120]
    return None


def _extract_notes(text: str) -> str | None:
    if "allergy" in text or "birthday" in text or "anniversary" in text:
        return text[:200]
    return None


def _prompt_for(field: str, intent: str | None) -> str:
    if field == "intent":
        return "Are you calling for a reservation, a private event, or takeout?"
    if field == "guest_name":
        return "May I have your full name for the booking note?"
    if field == "party_size":
        return "How many guests should I note for your party?"
    if field == "reservation_datetime":
        if intent == "takeout":
            return "When would you like to pick up your order?"
        return "What date and time would you like?"
    return "Could you share one more detail so I can finish your request?"


def _append_transcript(session: CallSession, *, role: str, text: str) -> None:
    transcript = list(session.transcript or [])
    transcript.append({"role": role, "text": text})
    session.transcript = transcript


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())
