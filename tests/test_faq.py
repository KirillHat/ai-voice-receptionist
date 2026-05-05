from __future__ import annotations

import pytest

from app.services import faq


@pytest.mark.parametrize(
    ("utterance", "topic"),
    [
        ("What time do you open?", "hours"),
        ("when are you open until tonight", "hours"),
        ("what are your dinner hours", "hours"),
        ("Is there valet parking?", "valet"),
        ("how much for parking", "valet"),
        ("do you have a private dining room", "private_dining"),
        ("how many people fit in the PDR", "private_dining"),
        ("is there a DJ tonight", "dj"),
        ("do you have live music", "dj"),
        ("what's the dress code", "dress_code"),
        ("can I wear shorts", "dress_code"),
        ("do you ID for alcohol", "id_alcohol"),
        ("can I smoke on the patio", "smoking"),
        ("is vaping allowed", "smoking"),
        ("do you have gluten free pizza", "gluten_free_pizza"),
        ("do you have gluten free pasta", "gluten_free_pasta"),
        ("we're celebrating a birthday", "birthday"),
        ("when did Novikov open", "opened"),
        ("what is the wifi", "wifi"),
        ("what is your address", "address"),
        ("where are you located", "address"),
    ],
)
def test_detect_topic(utterance: str, topic: str) -> None:
    assert faq.detect_topic(utterance) == topic


@pytest.mark.parametrize(
    "utterance",
    [
        "I'd like a reservation for four",
        "my name is alex",
        "tomorrow at 8 pm",
        "",
        "hi",
    ],
)
def test_detect_topic_returns_none_for_unrelated(utterance: str) -> None:
    assert faq.detect_topic(utterance) is None


def test_pizza_matches_pizza_topic_not_pasta() -> None:
    answer = faq.match_faq("do you have gluten free pizza")
    assert answer is not None
    assert answer.topic == "gluten_free_pizza"
    assert "pizza dough is not available" in answer.text.lower()


def test_pasta_matches_pasta_topic() -> None:
    answer = faq.match_faq("any gluten free pasta options")
    assert answer is not None
    assert answer.topic == "gluten_free_pasta"
    assert "gluten free pasta" in answer.text.lower()


def test_match_faq_returns_localized_spanish() -> None:
    answer = faq.match_faq("¿hay valet parking?", lang="es-US")
    assert answer is not None
    assert answer.topic == "valet"
    assert "diecisiete" in answer.text


def test_match_faq_returns_localized_russian() -> None:
    answer = faq.match_faq("во сколько вы закрываетесь", lang="ru-RU")
    assert answer is not None
    assert answer.topic == "hours"
    assert "ужин" in answer.text.lower()


def test_match_faq_falls_back_to_english_for_unknown_lang() -> None:
    answer = faq.match_faq("when did you open", lang="fr-FR")
    assert answer is not None
    assert answer.topic == "opened"
    assert "twenty four" in answer.text.lower()


def test_match_faq_returns_none_for_unrelated_text() -> None:
    assert faq.match_faq("I'd like to book a table for two") is None
