"""Business-hours awareness for Novikov Beverly Hills.

Hours from the Host Training Manual:
  Mon–Wed: 11:00 – 23:00
  Thu–Sat: 11:00 – next-day 02:00
  Sun:     10:00 – 23:00
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings


# weekday: monday=0 .. sunday=6
_HOURS: dict[int, tuple[time, time, bool]] = {
    # (open, close, closes_after_midnight)
    0: (time(11, 0), time(23, 0), False),
    1: (time(11, 0), time(23, 0), False),
    2: (time(11, 0), time(23, 0), False),
    3: (time(11, 0), time(2, 0), True),
    4: (time(11, 0), time(2, 0), True),
    5: (time(11, 0), time(2, 0), True),
    6: (time(10, 0), time(23, 0), False),
}


@dataclass(frozen=True)
class HoursState:
    is_open: bool
    closes_at: datetime | None
    next_open_at: datetime | None
    now_local: datetime


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().business_timezone)


def hours_state(now: datetime | None = None) -> HoursState:
    tz = _tz()
    local = (now or datetime.now(tz)).astimezone(tz)

    # Check if a late-night window from the *previous* weekday still covers us
    # (e.g. it's 1:30 AM on Friday, restaurant opened Thursday and closes at 2 AM).
    prev_weekday = (local.weekday() - 1) % 7
    prev_open, prev_close, prev_late = _HOURS[prev_weekday]
    if prev_late and local.time() < prev_close:
        closes_at = local.replace(
            hour=prev_close.hour, minute=prev_close.minute, second=0, microsecond=0
        )
        return HoursState(
            is_open=True,
            closes_at=closes_at,
            next_open_at=None,
            now_local=local,
        )

    today_open, today_close, today_late = _HOURS[local.weekday()]

    open_dt = local.replace(
        hour=today_open.hour, minute=today_open.minute, second=0, microsecond=0
    )
    if today_late:
        close_dt = (local + timedelta(days=1)).replace(
            hour=today_close.hour, minute=today_close.minute, second=0, microsecond=0
        )
    else:
        close_dt = local.replace(
            hour=today_close.hour, minute=today_close.minute, second=0, microsecond=0
        )

    if open_dt <= local < close_dt:
        return HoursState(
            is_open=True, closes_at=close_dt, next_open_at=None, now_local=local
        )

    # Closed — figure out next opening
    if local < open_dt:
        next_open = open_dt
    else:
        days_ahead = 1
        while True:
            d = (local + timedelta(days=days_ahead)).date()
            wk = d.weekday()
            o, _c, _l = _HOURS[wk]
            next_open = datetime.combine(d, o, tzinfo=tz)
            break
    return HoursState(
        is_open=False, closes_at=None, next_open_at=next_open, now_local=local
    )


def is_open_now() -> bool:
    return hours_state().is_open


_DAY_RU = ("в понедельник", "во вторник", "в среду", "в четверг",
           "в пятницу", "в субботу", "в воскресенье")
_DAY_EN = ("Monday", "Tuesday", "Wednesday", "Thursday",
           "Friday", "Saturday", "Sunday")
_DAY_ES = ("lunes", "martes", "miércoles", "jueves",
           "viernes", "sábado", "domingo")


def closed_greeting(lang: str) -> str:
    """One-line message used when an after-hours call comes in."""
    state = hours_state()
    if state.is_open:
        return ""
    nxt = state.next_open_at
    if nxt is None:
        if lang.startswith("ru"):
            return "К сожалению, мы сейчас закрыты, но я могу записать вас на ближайший рабочий день."
        if lang.startswith("es"):
            return "Lamentablemente estamos cerrados, pero puedo tomar su reserva para el próximo horario."
        return "We're closed at the moment, but I can take your reservation for the next available time."

    is_today = nxt.date() == state.now_local.date()
    if lang.startswith("ru"):
        when = "сегодня" if is_today else _DAY_RU[nxt.weekday()]
        time_str = f"{nxt.hour}:{nxt.minute:02d}" if nxt.minute else f"{nxt.hour} утра"
        return (
            f"Сейчас мы закрыты. Откроемся {when} в {time_str} — "
            "я могу записать вас на ближайший слот."
        )
    if lang.startswith("es"):
        when = "hoy" if is_today else f"el {_DAY_ES[nxt.weekday()]}"
        time_str = nxt.strftime("%-I:%M %p" if nxt.minute else "%-I %p")
        return (
            f"Estamos cerrados ahora. Abriremos {when} a las {time_str}. "
            "Puedo tomar su reserva para entonces."
        )
    when = "today" if is_today else _DAY_EN[nxt.weekday()]
    time_str = nxt.strftime("%-I:%M %p" if nxt.minute else "%-I %p")
    return (
        f"We're closed right now. We open {when} at {time_str} — "
        "I can take your reservation for then."
    )


__all__ = ["HoursState", "hours_state", "is_open_now", "closed_greeting"]
