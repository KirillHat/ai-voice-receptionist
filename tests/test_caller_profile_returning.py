from app.services.caller_profile import (
    is_returning_caller,
    mark_call_started,
    returning_caller_greeting,
    update_profile_from_turn,
)
from app.storage.models import CallerProfile


def _profile() -> CallerProfile:
    return CallerProfile(
        caller_phone="+15551231234",
        typical_intents={},
        visit_count=0,
    )


def test_returning_caller_requires_two_visits_and_a_name() -> None:
    p = _profile()
    assert not is_returning_caller(p)
    mark_call_started(p)  # visit_count=1, no name
    assert not is_returning_caller(p)
    update_profile_from_turn(
        p, utterance="my name is Olga", detected_lang="en-US", intent="reservation",
        guest_name="Olga",
    )
    assert p.last_guest_name == "Olga"
    assert not is_returning_caller(p)  # still 1 visit
    mark_call_started(p)  # visit_count=2
    assert is_returning_caller(p)


def test_returning_greeting_uses_last_name() -> None:
    p = _profile()
    p.visit_count = 3
    p.last_guest_name = "Анна"
    assert "Анна" in returning_caller_greeting(p, "ru-RU")
    assert "back" in returning_caller_greeting(p, "en-US").lower()
    assert "Anna" not in returning_caller_greeting(p, "ru-RU")  # uses Cyrillic
