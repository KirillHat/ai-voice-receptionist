"""Lightweight multilingual datetime normalization for reservation speech."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_RELATIVE_DAY_OFFSETS: tuple[tuple[str, int], ...] = (
    ("today", 0),
    ("tonight", 0),
    ("tomorrow", 1),
    ("сегодня", 0),
    ("сегодня вечером", 0),
    ("завтра", 1),
    ("hoy", 0),
    ("esta noche", 0),
    ("mañana", 1),
    ("manana", 1),
)


# Month name → number, multilingual. Russian months take genitive form
# (января/февраля/...) because callers say 'девятого мая', 'на 9 мая'.
_MONTH_BY_NAME: dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
    "января": 1, "январь": 1,
    "февраля": 2, "февраль": 2,
    "марта": 3, "март": 3,
    "апреля": 4, "апрель": 4,
    "мая": 5, "май": 5,
    "июня": 6, "июнь": 6,
    "июля": 7, "июль": 7,
    "августа": 8, "август": 8,
    "сентября": 9, "сентябрь": 9,
    "октября": 10, "октябрь": 10,
    "ноября": 11, "ноябрь": 11,
    "декабря": 12, "декабрь": 12,
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9, "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_WEEKDAY_BY_TOKEN = {
    "monday": 0,
    "mon": 0,
    "понедельник": 0,
    "lunes": 0,
    "tuesday": 1,
    "tue": 1,
    "вторник": 1,
    "martes": 1,
    "wednesday": 2,
    "wed": 2,
    "среда": 2,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "thursday": 3,
    "thu": 3,
    "четверг": 3,
    "friday": 4,
    "fri": 4,
    "пятница": 4,
    "пятницу": 4,
    "viernes": 4,
    "saturday": 5,
    "sat": 5,
    "суббота": 5,
    "sábado": 5,
    "sabado": 5,
    "sunday": 6,
    "sun": 6,
    "воскресенье": 6,
    "domingo": 6,
}

_TIME_WORDS = {
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
    "восьми": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
}

_TIME_OF_DAY_HINTS: tuple[tuple[str, tuple[int, int]], ...] = (
    ("morning", (11, 0)),
    ("afternoon", (14, 0)),
    ("evening", (19, 0)),
    ("night", (20, 0)),
    ("утром", (11, 0)),
    ("днем", (14, 0)),
    ("днём", (14, 0)),
    ("вечером", (19, 0)),
    ("ночью", (20, 0)),
    ("mañana por la mañana", (11, 0)),
    ("por la mañana", (11, 0)),
    ("por la tarde", (14, 0)),
    ("por la noche", (20, 0)),
    ("tarde", (14, 0)),
)


def normalize_datetime_text(
    text: str,
    *,
    timezone_name: str,
    now: datetime | None = None,
) -> str | None:
    """Normalize spoken datetime references into ISO-8601 in business timezone."""
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return None

    lower = cleaned.lower()
    tz = ZoneInfo(timezone_name)
    ref = now.astimezone(tz) if now else datetime.now(tz)

    base_date = _extract_explicit_date(lower, ref)
    if base_date is None:
        base_date = _extract_relative_date(lower, ref)
    if base_date is None:
        base_date = _extract_weekday_date(lower, ref)

    hour, minute = _extract_time(lower)
    if hour is None:
        hour, minute = _extract_time_hint(lower)
    elif hour < 12 and _has_pm_modifier(lower):
        # 'семь часов вечера' / 'seven in the evening' / 'siete de la tarde'.
        hour += 12
    elif hour == 12 and _has_am_modifier(lower):
        hour = 0

    if base_date is None and hour is None:
        return None

    if base_date is None:
        base_date = ref.date()
        if hour is not None and (hour < ref.hour or (hour == ref.hour and minute <= ref.minute)):
            base_date = base_date + timedelta(days=1)

    if hour is None:
        hour, minute = (19, 0)

    normalized = datetime(
        year=base_date.year,
        month=base_date.month,
        day=base_date.day,
        hour=hour,
        minute=minute,
        tzinfo=tz,
    )
    return normalized.isoformat(timespec="minutes")


def _extract_explicit_date(lower: str, ref: datetime):
    us = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", lower)
    if us:
        month = int(us.group(1))
        day = int(us.group(2))
        year = _coerce_year(us.group(3), ref.year)
        return _safe_date(year, month, day)

    eu = re.search(r"\b(\d{1,2})[.](\d{1,2})(?:[.](\d{2,4}))?\b", lower)
    if eu:
        day = int(eu.group(1))
        month = int(eu.group(2))
        year = _coerce_year(eu.group(3), ref.year)
        return _safe_date(year, month, day)

    # 'May 9' / 'May 9th' / 'May 9, 2027'
    en_md = re.search(
        r"\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|"
        r"july|jul|august|aug|september|sept|sep|october|oct|november|nov|"
        r"december|dec)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?\b",
        lower,
    )
    if en_md:
        month = _MONTH_BY_NAME.get(en_md.group(1))
        if month:
            day = int(en_md.group(2))
            year = _coerce_year(en_md.group(3), ref.year)
            picked = _safe_date(year, month, day)
            if picked and picked < ref.date() and not en_md.group(3):
                picked = _safe_date(year + 1, month, day)
            if picked:
                return picked

    # '9 мая' / 'девятого мая' (we already digitized words upstream so just digits)
    # / '9 de mayo' / 'el 9 de mayo'
    dm = re.search(
        r"\b(?:el\s+|на\s+|до\s+)?(\d{1,2})\s*(?:de\s+|-)?\s*"
        r"(января|январь|февраля|февраль|марта|март|апреля|апрель|мая|май|"
        r"июня|июнь|июля|июль|августа|август|сентября|сентябрь|октября|"
        r"октябрь|ноября|ноябрь|декабря|декабрь|"
        r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
        r"setiembre|octubre|noviembre|diciembre)\b",
        lower,
    )
    if dm:
        month = _MONTH_BY_NAME.get(dm.group(2))
        if month:
            day = int(dm.group(1))
            picked = _safe_date(ref.year, month, day)
            if picked and picked < ref.date():
                picked = _safe_date(ref.year + 1, month, day)
            if picked:
                return picked

    return None


def _extract_relative_date(lower: str, ref: datetime):
    for token, days in _RELATIVE_DAY_OFFSETS:
        if token in lower:
            return (ref + timedelta(days=days)).date()
    return None


def _extract_weekday_date(lower: str, ref: datetime):
    for token, weekday in _WEEKDAY_BY_TOKEN.items():
        if re.search(rf"\b{re.escape(token)}\b", lower):
            return _next_weekday(ref, weekday, lower)
    return None


def _extract_time(lower: str) -> tuple[int | None, int]:
    ampm_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", lower)
    if ampm_match:
        hour = int(ampm_match.group(1))
        minute = int(ampm_match.group(2) or "0")
        suffix = ampm_match.group(3)
        if suffix == "pm" and hour != 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute

    plain_match = re.search(r"\b(?:at|к|a las|a la|en|на)?\s*(\d{1,2})(?::(\d{2}))\b", lower)
    if plain_match:
        hour = int(plain_match.group(1))
        minute = int(plain_match.group(2) or "0")
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute

    short_hour = re.search(r"\b(?:at|к|a las|a la)?\s*(\d{1,2})\b", lower)
    if short_hour and _looks_like_time_context(lower):
        hour = int(short_hour.group(1))
        if 0 <= hour <= 23:
            return hour, 0

    for word, value in _TIME_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", lower) and _looks_like_time_context(lower):
            return value, 0

    return None, 0


def _extract_time_hint(lower: str) -> tuple[int | None, int]:
    for token, hm in _TIME_OF_DAY_HINTS:
        if token in lower:
            return hm
    return None, 0


def _looks_like_time_context(lower: str) -> bool:
    tokens = (
        " at ",
        " around ",
        " tonight",
        " tomorrow",
        "вечер",
        "утро",
        "днем",
        "днём",
        "ноч",
        "a las",
        "hora",
        "вечером",
        "к ",
    )
    return any(token in f" {lower} " for token in tokens)


def _next_weekday(ref: datetime, target_weekday: int, lower: str):
    delta = (target_weekday - ref.weekday()) % 7
    wants_next = any(token in lower for token in ("next", "следующ", "próxim", "proxim"))
    if delta == 0 or wants_next:
        delta = 7 if delta == 0 else delta
    return (ref + timedelta(days=delta)).date()


_PM_MODIFIERS = (
    "pm",
    "p.m.",
    "evening",
    "night",
    "in the evening",
    "in the afternoon",
    "вечера",
    "вечером",
    "ночи",
    "ночью",
    "дня",  # 'три часа дня' = 3 PM
    "днём",
    "днем",
    "de la tarde",
    "de la noche",
    "por la tarde",
    "por la noche",
)
_AM_MODIFIERS = (
    "am",
    "a.m.",
    "in the morning",
    "morning",
    "утра",
    "утром",
    "de la mañana",
    "por la mañana",
)


def _has_pm_modifier(lower: str) -> bool:
    return any(token in lower for token in _PM_MODIFIERS)


def _has_am_modifier(lower: str) -> bool:
    return any(token in lower for token in _AM_MODIFIERS)


def _coerce_year(raw: str | None, current_year: int) -> int:
    if not raw:
        return current_year
    year = int(raw)
    if year < 100:
        return 2000 + year
    return year


def _safe_date(year: int, month: int, day: int):
    try:
        return datetime(year=year, month=month, day=day).date()
    except ValueError:
        return None
