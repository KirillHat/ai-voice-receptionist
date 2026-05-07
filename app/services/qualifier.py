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
        "забронир",
        "столик",
        "столика",
        "столиком",
        "ужин",
        "обед",
    ),
    "private_event": (
        "private",
        "event",
        "party",
        "birthday",
        "anniversary",
        "celebrat",
        "corporate",
        "evento",
        "evento privado",
        "cumpleaño",
        "aniversario",
        "celebrar",
        "fiesta",
        "мероприят",
        "банкет",
        "день рожден",
        "именин",
        "юбилей",
        "годовщин",
        "корпоратив",
        "праздн",
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
    # 'ask' = still collecting, 'readback' = asking caller to confirm,
    # 'complete' = caller confirmed, 'reopen' = caller rejected read-back
    kind: str = "ask"


def required_fields(intent: str | None) -> tuple[str, ...]:
    if intent in {"reservation", "private_event"}:
        return ("intent", "guest_name", "party_size", "reservation_datetime")
    if intent == "takeout":
        return ("intent", "guest_name")
    return ("intent", "guest_name", "reservation_datetime")


def ingest_turn(
    session: CallSession,
    utterance: str,
    *,
    lang: str | None = None,
) -> TurnDecision:
    """Process one caller turn.

    ``lang`` is the language voice.py is currently speaking to the caller.
    It's used by the read-back prompt so we don't end up doing an English
    confirmation for a Russian conversation. If omitted we fall back to a
    transcript-based heuristic.
    """
    text = _clean(utterance)
    if not text:
        return TurnDecision(
            prompt="Sorry, I did not catch that. Please repeat in one short sentence.",
            completed=False,
            missing_field=None,
        )

    last_assistant = _last_assistant_prompt(session)

    # Read-back state: caller is responding to our confirmation prompt.
    if session.status == "awaiting_confirmation":
        _append_transcript(session, role="caller", text=text)
        session.turn_count = int(session.turn_count or 0) + 1
        verdict = _confirmation_verdict(text)
        if verdict == "yes":
            summary = _localized_summary(session, lang)
            _append_transcript(session, role="assistant", text=summary)
            return TurnDecision(prompt=summary, completed=True, kind="complete")
        if verdict == "no":
            # Caller rejected — try to re-extract any corrections from the
            # same utterance, then fall through to ask the still-missing
            # field (or, if nothing changed, ask which field to fix).
            session.status = "in_progress"
            # In rejection branch the caller often immediately corrects a
            # field ('no, my name is Alla'). Allow overwrite of fields that
            # were already set from the misheard turn.
            _extract_fields(session, text, last_assistant=last_assistant, allow_overwrite=True)
            missing = _missing_fields(session)
            if missing:
                next_field = missing[0]
                prompt = _prompt_for(next_field, session.intent, lang)
                _append_transcript(session, role="assistant", text=prompt)
                return TurnDecision(
                    prompt=prompt, completed=False, missing_field=next_field, kind="reopen"
                )
            # Still complete after re-extract → ask once more for confirmation.
            session.status = "awaiting_confirmation"
            prompt = _readback_prompt(session, last_assistant, lang=lang)
            _append_transcript(session, role="assistant", text=prompt)
            return TurnDecision(prompt=prompt, completed=False, kind="readback")
        # Ambiguous response — re-extract fields and re-prompt for confirmation.
        _extract_fields(session, text, last_assistant=last_assistant)
        missing = _missing_fields(session)
        if missing:
            session.status = "in_progress"
            next_field = missing[0]
            prompt = _prompt_for(next_field, session.intent, lang)
            _append_transcript(session, role="assistant", text=prompt)
            return TurnDecision(
                prompt=prompt, completed=False, missing_field=next_field, kind="reopen"
            )
        prompt = _readback_prompt(session, last_assistant, lang=lang)
        _append_transcript(session, role="assistant", text=prompt)
        return TurnDecision(prompt=prompt, completed=False, kind="readback")

    _append_transcript(session, role="caller", text=text)
    _extract_fields(session, text, last_assistant=last_assistant)
    session.turn_count = int(session.turn_count or 0) + 1

    missing = _missing_fields(session)
    if not missing:
        # All required fields collected — first run the read-back loop so
        # any STT mishearings (Anna→Alla, May 9→May 19) get caught before
        # we mark the call qualified and create the lead.
        session.status = "awaiting_confirmation"
        prompt = _readback_prompt(session, last_assistant, lang=lang)
        _append_transcript(session, role="assistant", text=prompt)
        return TurnDecision(prompt=prompt, completed=False, kind="readback")

    next_field = missing[0]
    prompt = _prompt_for(next_field, session.intent, lang)
    _append_transcript(session, role="assistant", text=prompt)
    return TurnDecision(prompt=prompt, completed=False, missing_field=next_field)


_YES_PATTERNS = (
    r"\b(?:yes|yeah|yep|yup|sure|correct|right|exactly|that'?s right|that is right|"
    r"perfect|fine|ok|okay)\b",
    r"\b(?:да|верно|точно|правильно|именно|всё верно|все верно|правильна|правильно так)\b",
    r"\b(?:s[ií]|claro|exacto|correcto|correcta|exactamente|así es|asi es|perfecto)\b",
)
_NO_PATTERNS = (
    r"\b(?:no|nope|wrong|incorrect|not (?:right|quite)|that'?s wrong|"
    r"actually|hold on|wait)\b",
    r"\b(?:нет|неверно|неправильно|не так|погод(?:и|ите)|секундочку|стоп)\b",
    r"\b(?:no|incorrecto|incorrecta|equivocad[ao]|espera|esper[ae])\b",
)


def _confirmation_verdict(text: str) -> str | None:
    """Classify a read-back response as yes/no/None (ambiguous)."""
    lower = text.lower().strip()
    if not lower:
        return None
    no_hit = any(re.search(pat, lower) for pat in _NO_PATTERNS)
    yes_hit = any(re.search(pat, lower) for pat in _YES_PATTERNS)
    # 'no' is sticky — if both appear, prefer the correction signal so we
    # don't lock in a wrong field on a hesitant 'no, yes, that's wrong'.
    if no_hit:
        return "no"
    if yes_hit:
        return "yes"
    return None


def _readback_prompt(
    session: CallSession,
    last_assistant: str | None,
    *,
    lang: str | None = None,
) -> str:
    """Read-back text in the conversation's currently spoken language.

    Caller passes ``lang`` when known (voice.py knows active_lang). If
    not provided, we fall back to sniffing the last assistant prompt so
    direct unit-test calls still produce a reasonable answer.
    """
    if not lang:
        last = (last_assistant or "").lower()
        if any(ch in last for ch in "абвгдеёжзийклмнопрстуфхцчшщыэюя"):
            lang = "ru-RU"
        elif "ñ" in last or "¿" in last or "à" in last or " él " in last or last.startswith(("hola", "gracias", "para", "qué", "cuál")):
            lang = "es-US"
        else:
            lang = "en-US"
    guest = (session.guest_name or "").strip()
    party = session.party_size
    iso = session.reservation_datetime
    intent = session.intent or ""

    if lang == "ru-RU":
        intent_phrase = {
            "reservation": "бронь",
            "private_event": "частное мероприятие",
            "takeout": "заказ навынос",
        }.get(intent, "заявку")
        bits: list[str] = [intent_phrase]
        if party:
            bits.append(f"на {party} {_ru_guests(party)}")
        if iso:
            bits.append("на " + _humanize_datetime(iso, lang="ru-RU"))
        if guest:
            bits.append(f"на имя {guest}")
        body = " ".join(bits)
        return f"Уточняю: {body}. Всё верно?"

    if lang == "es-US":
        intent_phrase = {
            "reservation": "una reserva",
            "private_event": "un evento privado",
            "takeout": "un pedido para llevar",
        }.get(intent, "su solicitud")
        bits = [intent_phrase]
        if party:
            personas = "persona" if party == 1 else "personas"
            bits.append(f"para {party} {personas}")
        if iso:
            bits.append("el " + _humanize_datetime(iso, lang="es-US"))
        if guest:
            bits.append(f"a nombre de {guest}")
        body = " ".join(bits)
        return f"Para confirmar: {body}. ¿Es correcto?"

    intent_phrase = {
        "reservation": "a reservation",
        "private_event": "a private event",
        "takeout": "a takeout order",
    }.get(intent, "your request")
    bits = [intent_phrase]
    if party:
        guests = "guest" if party == 1 else "guests"
        bits.append(f"for {party} {guests}")
    if iso:
        bits.append("on " + _humanize_datetime(iso, lang="en-US"))
    if guest:
        bits.append(f"under {guest}")
    body = " ".join(bits)
    return f"Just to confirm: {body}. Is that correct?"


def _localized_summary(session: CallSession, lang: str | None) -> str:
    """Final 'noted, our team will confirm' message in caller's language.

    Mirrors language_router._completion_message — kept in sync but lives
    here so the transcript shipped to the dashboard reflects what the
    caller actually heard.
    """
    from app.services.language_router import _completion_message

    return _completion_message(session, lang or "en-US")


def _ru_guests(n: int) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return "гостей"
    n %= 10
    if n == 1:
        return "гостя"
    if 2 <= n <= 4:
        return "гостей"
    return "гостей"


def note_faq_turn(session: CallSession, utterance: str, answer: object) -> None:
    """Record an FAQ answer in the transcript.

    Caller utterance is already appended by ``ingest_turn`` (which voice.py
    calls before this for silent field extraction), so we just stamp the
    FAQ reply on top — replacing whatever placeholder ``ingest_turn``
    appended last.
    """
    answer_text = getattr(answer, "text", "") or ""
    if not answer_text:
        return
    transcript = list(session.transcript or [])
    if transcript and transcript[-1].get("role") == "assistant":
        transcript[-1] = {"role": "assistant", "text": answer_text}
    else:
        transcript.append({"role": "assistant", "text": answer_text})
    session.transcript = transcript


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
    allow_overwrite: bool = False,
) -> None:
    # Re-run intent detection on every turn until we get a specific intent.
    # The previous logic locked intent on the first reply, so a caller who
    # opened with 'speak Russian please' was forever stuck on intent='general'.
    if session.intent in (None, "", "general"):
        new_intent = _extract_intent(text)
        if new_intent != "general" or not session.intent:
            session.intent = new_intent

    if not session.guest_name or allow_overwrite:
        maybe_name = _extract_name(text)
        if not maybe_name and _was_asking_for(last_assistant, "name"):
            maybe_name = _extract_short_name(text)
        if maybe_name:
            session.guest_name = maybe_name

    if session.party_size is None or allow_overwrite:
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
    elif _has_explicit_time_correction(text):
        new_dt = _extract_datetime_phrase(text)
        if new_dt:
            session.reservation_datetime = _merge_time_into_stored(
                stored=session.reservation_datetime,
                new=new_dt,
                text=text,
            )

    maybe_notes = _extract_notes(text)
    if maybe_notes:
        existing = (session.special_notes or "").strip()
        if not existing:
            session.special_notes = maybe_notes
        elif maybe_notes not in existing and existing not in maybe_notes:
            # Multi-turn preferences accumulate — caller may mention high
            # chair on turn 1 and an allergy on turn 4.
            session.special_notes = (existing + " | " + maybe_notes)[:400]


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


_NOT_A_NAME_TOKENS = frozenset(
    {
        # Confirmation/rejection words a caller might say in response
        # to a name prompt that lingered into the read-back state.
        "yes", "yeah", "yep", "yup", "sure", "no", "nope", "ok", "okay",
        "fine", "correct", "right", "exactly", "perfect",
        "да", "нет", "верно", "точно", "правильно", "хорошо", "ок",
        "sí", "si", "no", "claro", "exacto", "correcto", "vale",
        # Filler words.
        "hello", "hi", "hey", "thanks", "thank", "you",
        "здравствуйте", "привет", "спасибо",
        "hola", "gracias",
    }
)


def _looks_like_name(cleaned: str) -> bool:
    lower = cleaned.lower().strip(" .,!?-")
    if not lower:
        return False
    # Strip trailing punctuation/contractions before checking against the
    # blacklist: 'that's correct' -> 'thats correct'.
    stripped = re.sub(r"[^\w\s]", "", lower)
    if stripped in _NOT_A_NAME_TOKENS:
        return False
    # Multi-word affirmations like "that's correct" / "all good" / "yes please".
    tokens = [t for t in stripped.split() if t]
    if tokens and all(t in _NOT_A_NAME_TOKENS for t in tokens):
        return False
    # Multi-word containing a strong confirmation word at the head/tail.
    if tokens and (tokens[0] in {"thats", "that"} or tokens[-1] in {"correct", "right", "thats"}):
        return False
    return True


_NAME_TAIL_BOUNDARY = re.compile(
    r"\s+(?:from|with|and|but|y|на|для|из|de\s+la|de\s+los|de)\s+"
    r"|[,;]",
    re.IGNORECASE,
)


def _extract_short_name(text: str) -> str | None:
    """Treat a 1–3 word reply as a name when we just asked for one.

    Also handles trailing introducer tail-phrases like 'David from Goldman
    Sachs' -> 'David' or 'Anna and my friend' -> 'Anna'.
    """
    cleaned = re.sub(r"[.,!?]+$", "", text).strip()
    if not cleaned:
        return None
    # Strip boundary tail so 'David from Goldman Sachs' becomes 'David'.
    cut = _NAME_TAIL_BOUNDARY.search(cleaned)
    if cut:
        cleaned = cleaned[: cut.start()].strip()
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
    if not _looks_like_name(cleaned):
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
    # Trim trailing affixes that often follow a self-introduction:
    #   'David from Goldman Sachs' -> stop at ' from '
    #   'I'm Anna and I have a nut allergy' -> stop at ' and '
    #   'My name is Sarah, I want a window seat' -> stop at the comma
    boundary_re = re.compile(
        r"\s+(?:from|with|and|but|y|на|для|из|de\s+la|de\s+los|de)\s+"
        r"|[,;]",
        re.IGNORECASE,
    )
    patterns = [
        r"(?:my name is|this is|i am|i'm)\s+([a-z][a-z\-\s']{1,40})",
        r"(?:^|[\s,])(?:name)\s+is\s+([a-z][a-z\-\s']{1,40})",
        r"(?:me llamo|soy|mi nombre es)\s+([a-záéíóúñ][a-záéíóúñ\-\s']{1,40})",
        r"(?:меня зовут|меня называют)\s+([а-яё][а-яё\-\s']{1,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1)
        cut = boundary_re.search(raw)
        if cut:
            raw = raw[: cut.start()]
        cleaned = raw.strip(" .,!?-")
        if not cleaned or not _looks_like_name(cleaned):
            continue
        return _title_case(cleaned)
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

    # Russian collective genitive forms after 'на' are unambiguous party
    # markers — 'на двоих', 'на троих', 'на четверых' ('for two/three/four
    # people'). They are never used as date/time fragments, so the 'на N'
    # trigger we dropped earlier is safe specifically for these words.
    collective_only = re.search(
        r"\bна\s+(двоих|троих|четверых|пятерых|шестерых|семерых|восьмерых|"
        r"девятерых|десятерых|двадцатерых|двое|трое|четверо|пятеро|шестеро|"
        r"семеро|восьмеро)\b",
        text,
    )
    if collective_only and collective_only.group(1) in _NUMBER_WORDS:
        return _NUMBER_WORDS[collective_only.group(1)]
    return None


_EXPLICIT_TIME_SIGNAL = re.compile(
    r"\b(?:am|pm|p\.m\.?|a\.m\.?)\b|"
    r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|"
    r"\b(?:вечера|вечером|утра|утром|дня|днём|днем|ночи|ночью)\b|"
    r"de\s+la\s+(?:tarde|noche|mañana)\b|"
    r"por\s+la\s+(?:tarde|noche|mañana)\b|"
    r"\b(?:noon|midnight|полдень|полночь|mediodía|medianoche)\b",
    re.IGNORECASE,
)
_DATE_SIGNAL = re.compile(
    r"\b(?:today|tonight|tomorrow|next|monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday|january|february|march|april|may|june|july|"
    r"august|september|october|november|december|"
    r"сегодня|завтра|следующ\w+|понедельник|вторник|среда|четверг|"
    r"пятница|пятницу|суббота|воскресенье|"
    r"января|февраля|марта|апреля|мая|июня|июля|августа|сентября|"
    r"октября|ноября|декабря|"
    r"hoy|mañana|lunes|martes|miércoles|jueves|viernes|sábado|domingo|"
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
    r"octubre|noviembre|diciembre)\b|\b\d{1,2}[/.]\d{1,2}\b",
    re.IGNORECASE,
)


def _has_explicit_time_correction(text: str) -> bool:
    return bool(_EXPLICIT_TIME_SIGNAL.search(text))


def _has_explicit_date_marker(text: str) -> bool:
    return bool(_DATE_SIGNAL.search(text))


def _merge_time_into_stored(*, stored: str, new: str, text: str) -> str:
    """Replace HH:MM in stored ISO with HH:MM from a fresh time-only correction.

    If the new utterance also carries a date marker, prefer the new value
    wholesale instead of merging.
    """
    if _has_explicit_date_marker(text):
        return new
    try:
        from datetime import datetime as _dt

        stored_dt = _dt.fromisoformat(stored)
        new_dt = _dt.fromisoformat(new)
    except ValueError:
        return new
    merged = stored_dt.replace(hour=new_dt.hour, minute=new_dt.minute)
    return merged.isoformat(timespec="minutes")


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


_NOTES_KEYWORDS: tuple[str, ...] = (
    # Allergies / dietary
    "allerg", "аллерг", "alerg", "intoleran", "непереносимост",
    "vegan", "veган", "vegetarian", "вегетариан", "vegano", "vegetariano",
    "gluten-free", "gluten free", "без глютен", "sin gluten",
    "halal", "халяль", "kosher", "кошер",
    "nut", "peanut", "арахис", "орех", "nuez", "frutos secos",
    "shellfish", "marisco", "морепродукт", "креветк",
    "dairy", "lactose", "лактоз", "молоч", "lácteo",
    "fish", "рыб", "pescado",
    # Special occasions
    "birthday", "день рожден", "именин", "cumpleaño", "cumpleanos",
    "anniversary", "годовщин", "юбилей", "aniversario",
    "engagement", "помолвк", "compromiso",
    "celebration", "праздн", "celebrar",
    # Seating preferences
    "by the window", "window seat", "у окна", "junto a la ventana",
    "quiet table", "тих", "tranquilo",
    "patio", "терраса", "terraza",
    "private room", "pdr", "приватн", "privado",
    "outdoor", "outside",
    # Family
    "high chair", "kid", "child", "stroller",
    "детский", "ребенок", "ребёнок", "коляск",
    "niño", "niña", "silla alta",
    # Other common
    "wheelchair", "коляск", "silla de ruedas",
    "stroller",
    "wine pair", "tasting",
)


def _extract_notes(text: str) -> str | None:
    """Snapshot the caller's utterance when it carries a special request.

    Stored verbatim (truncated) so the host team sees the original phrasing
    when preparing the table — 'with high chair', 'by the window', 'nut
    allergy' — without us interpreting beyond keyword detection.
    """
    lower = text.lower()
    if any(kw in lower for kw in _NOTES_KEYWORDS):
        return text.strip()[:200]
    return None


_FIELD_PROMPTS: dict[str, dict[str, str]] = {
    "en-US": {
        "intent": "Are you calling for a reservation, a private event, or takeout?",
        "guest_name": "May I have your full name for the booking note?",
        "party_size": "How many guests should I note for your party?",
        "reservation_datetime": "What date and time would you like?",
        "reservation_datetime_takeout": "When would you like to pick up your order?",
        "default": "Could you share one more detail so I can finish your request?",
    },
    "ru-RU": {
        "intent": "Подскажите, вы звоните по поводу брони, частного мероприятия или заказа навынос?",
        "guest_name": "Подскажите, пожалуйста, ваше полное имя для брони.",
        "party_size": "На сколько гостей оформить заявку?",
        "reservation_datetime": "Какую дату и время вам удобно забронировать?",
        "reservation_datetime_takeout": "Во сколько вам удобно забрать заказ?",
        "default": "Поделитесь, пожалуйста, ещё одной деталью, и я завершу заявку.",
    },
    "es-US": {
        "intent": "¿Llama por una reserva, un evento privado o para llevar?",
        "guest_name": "¿Me comparte su nombre completo para la reserva?",
        "party_size": "¿Para cuántas personas debo anotarlo?",
        "reservation_datetime": "¿Qué fecha y hora le viene bien?",
        "reservation_datetime_takeout": "¿A qué hora desea recoger el pedido?",
        "default": "¿Me comparte un detalle más para terminar su solicitud?",
    },
}


def _prompt_for(field: str, intent: str | None, lang: str | None = None) -> str:
    bundle = _FIELD_PROMPTS.get(lang or "en-US", _FIELD_PROMPTS["en-US"])
    if field == "reservation_datetime" and intent == "takeout":
        return bundle["reservation_datetime_takeout"]
    return bundle.get(field, bundle["default"])


def _append_transcript(session: CallSession, *, role: str, text: str) -> None:
    transcript = list(session.transcript or [])
    transcript.append({"role": role, "text": text})
    session.transcript = transcript


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())
