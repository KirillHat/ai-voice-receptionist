from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.business_hours import closed_greeting, hours_state

LA = ZoneInfo("America/Los_Angeles")


def test_open_during_lunch_monday() -> None:
    state = hours_state(datetime(2026, 5, 4, 13, 0, tzinfo=LA))  # Mon 1 PM
    assert state.is_open
    assert state.closes_at and state.closes_at.hour == 23


def test_closed_late_monday_night() -> None:
    state = hours_state(datetime(2026, 5, 5, 1, 0, tzinfo=LA))  # Tue 1 AM
    assert not state.is_open
    assert state.next_open_at and state.next_open_at.hour == 11


def test_open_in_late_night_window_friday() -> None:
    # Friday 1:30 AM is still inside Thursday's open window (closes Fri 2 AM).
    state = hours_state(datetime(2026, 5, 8, 1, 30, tzinfo=LA))
    assert state.is_open
    assert state.closes_at and state.closes_at.hour == 2


def test_closed_greeting_lang_dispatch() -> None:
    # Just ensure they don't crash and return strings — content depends on
    # current wall clock at test time.
    assert isinstance(closed_greeting("en-US"), str)
    assert isinstance(closed_greeting("ru-RU"), str)
    assert isinstance(closed_greeting("es-US"), str)
