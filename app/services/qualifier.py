"""Lead qualification logic for voice calls.

This is intentionally deterministic for predictable demos and easy testing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import get_settings
from app.services import datetime_nlu
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
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "twenty one": 21,
    "twenty two": 22,
    "twenty four": 24,
    "twenty five": 25,
    "thirty": 30,
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
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "veinte": 20,
    "treinta": 30,
    "один": 1,
    "одного": 1,
    "два": 2,
    "двух": 2,
    "двое": 2,
    "двоих": 2,
    "три": 3,
    "трёх": 3,
    "трех": 3,
    "трое": 3,
    "троих": 3,
    "четыре": 4,
    "четырёх": 4,
    "четырех": 4,
    "четверо": 4,
    "четверых": 4,
    "пять": 5,
    "пяти": 5,
    "пятерых": 5,
    "пятеро": 5,
    "шесть": 6,
    "шести": 6,
    "шестеро": 6,
    "шестерых": 6,
    "семь": 7,
    "семи": 7,
    "семеро": 7,
    "семерых": 7,
    "восемь": 8,
    "восьми": 8,
    "восьмерых": 8,
    "девять": 9,
    "девяти": 9,
    "десять": 10,
    "десяти": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "пятнадцать": 15,
    "двадцать": 20,
    "тридцать": 30,
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

    last_assistant = _last_assistant_prompt(session)

    _append_transcript(session, role="caller", text=text)
    _extract_fields(session, text, last_assistant=last_assistant)
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
    """Natural-language confirmation in English.

    Spoken to the guest, so we MUST NOT echo internal field labels
    ('intent', 'party_size', ISO timestamps). The matching localized
    versions live in language_router._completion_message.
    """
    pieces: list[str] = []

    intent_phrase = {
        "reservation": "your reservation",
        "private_event": "your private event",
        "takeout": "your takeout order",
    }.get(session.intent or "", "your request")
    pieces.append(intent_phrase)

    if session.party_size:
        guests = "guest" if session.party_size == 1 else "guests"
        pieces.append(f"for {session.party_size} {guests}")
    if session.reservation_datetime:
        pieces.append("on " + _humanize_datetime(session.reservation_datetime, lang="en-US"))

    body = " ".join(pieces)
    opener = f"Thank you, {session.guest_name}." if session.guest_name else "Thank you."
    return f"{opener} I have {body} noted — our team will confirm shortly."


def _humanize_datetime(value: str, *, lang: str) -> str:
    """Turn an ISO-8601 string (or whatever fragment we captured) into speech."""
    from datetime import datetime as _dt

    raw = value.strip()
    try:
        # Be lenient: accept '2026-05-09T19:00-07:00' or '2026-05-09T19:00:00'.
        cleaned = raw
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        parsed = _dt.fromisoformat(cleaned)
    except ValueError:
        return raw  # fall back to whatever we got

    if lang == "ru-RU":
        months = (
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря",
        )
        date_part = f"{parsed.day} {months[parsed.month - 1]}"
        time_part = _ru_time_phrase(parsed.hour, parsed.minute)
        return f"{date_part} в {time_part}"
    if lang == "es-US":
        months = (
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        )
        date_part = f"{parsed.day} de {months[parsed.month - 1]}"
        time_part = _es_time_phrase(parsed.hour, parsed.minute)
        return f"{date_part} a las {time_part}"
    rendered = parsed.strftime("%B %-d at %-I:%M %p")
    if rendered.endswith(":00 AM") or rendered.endswith(":00 PM"):
        rendered = rendered.replace(":00 ", " ")
    return rendered


def _ru_time_phrase(hour: int, minute: int) -> str:
    period = "вечера" if 17 <= hour <= 23 else "ночи" if hour < 5 else "утра" if hour < 12 else "дня"
    twelve = hour if hour <= 12 else hour - 12
    if twelve == 0:
        twelve = 12
    if minute:
        return f"{twelve}:{minute:02d} {period}"
    return f"{twelve} {period}"


def _es_time_phrase(hour: int, minute: int) -> str:
    period = "de la tarde" if 12 <= hour <= 18 else "de la noche" if hour > 18 or hour < 5 else "de la mañana"
    twelve = hour if hour <= 12 else hour - 12
    if twelve == 0:
        twelve = 12
    if minute:
        return f"{twelve}:{minute:02d} {period}"
    return f"{twelve} {period}"


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


def _extract_fields(
    session: CallSession,
    text: str,
    *,
    last_assistant: str | None = None,
) -> None:
    # Re-run intent detection on every turn until we get a specific intent.
    # The previous logic locked intent on the first reply, so a caller who
    # opened with 'speak Russian please' was forever stuck on intent='general'.
    if session.intent in (None, "", "general"):
        new_intent = _extract_intent(text)
        if new_intent != "general" or not session.intent:
            session.intent = new_intent

    if not session.guest_name:
        maybe_name = _extract_name(text)
        if not maybe_name and _was_asking_for(last_assistant, "name"):
            maybe_name = _extract_short_name(text)
        if maybe_name:
            session.guest_name = maybe_name

    if session.party_size is None:
        maybe_party = _extract_party_size(text)
        if maybe_party is None and _was_asking_for(last_assistant, "party"):
            maybe_party = _extract_short_party(text)
        if maybe_party:
            session.party_size = maybe_party

    if not session.reservation_datetime:
        maybe_time = _extract_datetime_phrase(text)
        if not maybe_time and _was_asking_for(last_assistant, "datetime"):
            maybe_time = _extract_short_datetime(text)
        if maybe_time:
            session.reservation_datetime = maybe_time

    if not session.special_notes:
        maybe_notes = _extract_notes(text)
        if maybe_notes:
            session.special_notes = maybe_notes


_NAME_QUESTION_TOKENS = (
    "name",
    "имя",
    "зовут",
    "nombre",
    "se llama",
)
_PARTY_QUESTION_TOKENS = (
    "guests",
    "people",
    "party",
    "гостей",
    "человек",
    "personas",
)
_DATETIME_QUESTION_TOKENS = (
    "date",
    "time",
    "when",
    "what date",
    "what time",
    "дата",
    "время",
    "когда",
    "fecha",
    "hora",
    "cuándo",
    "cuando",
    "pickup",
    "pick up",
)


def _was_asking_for(last_assistant: str | None, field: str) -> bool:
    if not last_assistant:
        return False
    lower = last_assistant.lower()
    if field == "name":
        return any(token in lower for token in _NAME_QUESTION_TOKENS)
    if field == "party":
        return any(token in lower for token in _PARTY_QUESTION_TOKENS)
    if field == "datetime":
        return any(token in lower for token in _DATETIME_QUESTION_TOKENS)
    return False


def _extract_short_name(text: str) -> str | None:
    """Treat a 1–3 word reply as a name when we just asked for one."""
    cleaned = re.sub(r"[.,!?]+$", "", text).strip()
    if not cleaned:
        return None
    parts = [p for p in cleaned.split() if p and not p.isdigit()]
    if not parts or len(parts) > 3:
        return None
    if any(token in cleaned for token in _INTENT_KEYWORDS["reservation"]):
        return None
    if any(token in cleaned for token in _INTENT_KEYWORDS["private_event"]):
        return None
    if any(token in cleaned for token in _INTENT_KEYWORDS["takeout"]):
        return None
    return _title_case(cleaned)


_TIME_LIKE_TOKENS = (
    r"\b(?:o'?clock|am|pm|p\.m\.|a\.m\.)\b",
    r"\bin the\s+(?:morning|afternoon|evening|night)\b",
    r"\b(?:часов|часа|час|вечера|утра|дня|ночи|минут)\b",
    r"\b(?:de la (?:mañana|tarde|noche)|en la (?:mañana|tarde|noche))\b",
)


def _looks_like_time_phrase(text: str) -> bool:
    return any(re.search(pat, text) for pat in _TIME_LIKE_TOKENS)


def _extract_short_party(text: str) -> int | None:
    # Even when the assistant just asked for party size, the caller may
    # answer with a time instead ('в семь часов вечера'). Don't grab a
    # bare number from a sentence that is clearly about time.
    if _looks_like_time_phrase(text):
        return None
    digits = re.search(r"\b(\d{1,2})\b", text)
    if digits:
        value = int(digits.group(1))
        if 1 <= value <= 30:
            return value
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", text):
            return value
    return None


def _extract_short_datetime(text: str) -> str | None:
    """Extract datetime-like short replies when we just asked for date/time."""
    cleaned = re.sub(r"[.,!?]+$", "", text).strip()
    if not cleaned:
        return None

    lower = cleaned.lower()
    if any(
        phrase in lower
        for phrase in (
            "not sure",
            "don't know",
            "dont know",
            "later",
            "whatever",
            "idk",
            "no idea",
            "не знаю",
            "без разницы",
            "позже",
            "no se",
            "no sé",
            "da igual",
            "más tarde",
        )
    ):
        return None

    normalized = datetime_nlu.normalize_datetime_text(
        cleaned,
        timezone_name=get_settings().business_timezone,
    )
    if normalized:
        return normalized

    datetime_signal_patterns = (
        r"\b\d{1,2}[:.]\d{2}\s*(?:am|pm)?\b",
        r"\b\d{1,2}\s*(?:am|pm)\b",
        r"\b(?:today|tonight|tomorrow|next)\b",
        r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b",
        r"\b(?:завтра|сегодня|вечером|утром|дн[её]м|понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)\b",
        r"\b(?:mañana|hoy|esta noche|lunes|martes|miércoles|jueves|viernes|sábado|domingo)\b",
    )
    if any(re.search(pattern, lower) for pattern in datetime_signal_patterns):
        return None

    # Accept compact STT fragments with a leading number, e.g. "8 evening".
    if re.search(r"^\d{1,2}\b", lower):
        return None

    return None


def _last_assistant_prompt(session: CallSession) -> str | None:
    transcript = list(session.transcript or [])
    for entry in reversed(transcript):
        if entry.get("role") == "assistant":
            return entry.get("text") or None
    return None


def _extract_intent(text: str) -> str:
    # Order matters: 'private event' should win over 'book a private event'.
    # 'takeout' and 'private_event' are more specific than 'reservation' (which
    # picks up generic words like 'book' or 'dinner'), so check them first.
    priority = ("private_event", "takeout", "reservation")
    for intent in priority:
        keywords = _INTENT_KEYWORDS[intent]
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
    # Auto-extract only when there's a strong contextual cue. We dropped the
    # bare 'на N' Russian trigger because 'на 9 мая' (date) was being parsed
    # as party=9, and the bare-number-word fallback because 'семь часов'
    # (time) was being parsed as party=7. Bare numbers/words without those
    # strong cues are handled by _extract_short_party in the state-aware
    # branch (only after we explicitly asked for the party size).
    contextual_digit = re.search(
        r"(?:party of|for|we are|we're|table for|para|somos|нас|нас будет|для)"
        r"\s+(\d{1,2})\b",
        text,
    )
    if contextual_digit:
        value = int(contextual_digit.group(1))
        if 1 <= value <= 30:
            return value

    guests_digit = re.search(
        r"\b(\d{1,2})\s*(?:guests?|people|persons?|adults?|"
        r"гостей|человек|людей|persona[s]?)\b",
        text,
    )
    if guests_digit:
        value = int(guests_digit.group(1))
        if 1 <= value <= 30:
            return value

    # Word numbers in two situations:
    # 1. Right after a strong context cue: 'for two', 'party of three',
    #    'table for four', 'нас будет четверо', 'somos tres'.
    # 2. Adjacent to a noun: 'four guests', 'two people', 'четверо гостей',
    #    'dos personas'.
    word_alt = "|".join(re.escape(w) for w in _NUMBER_WORDS)
    after_cue = re.search(
        r"(?:party of|for|we are|we're|table for|para|somos|нас|нас будет|для)"
        rf"\s+({word_alt})\b",
        text,
    )
    if after_cue:
        return _NUMBER_WORDS[after_cue.group(1)]

    near_noun = re.search(
        rf"\b({word_alt})\b\s+(?:guests?|people|persons?|adults?|"
        r"гостей|человек|людей|persona[s]?)\b",
        text,
    )
    if near_noun:
        return _NUMBER_WORDS[near_noun.group(1)]
    return None


def _extract_datetime_phrase(text: str) -> str | None:
    normalized = datetime_nlu.normalize_datetime_text(
        text,
        timezone_name=get_settings().business_timezone,
    )
    if normalized:
        return normalized

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
        return None
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
