from app.services import menu
from app.services.faq import match_faq


def test_index_loads_with_items() -> None:
    idx = menu.load_index()
    assert len(idx.items) > 100, "menu.json should ship with at least the basic dish list"
    assert "Desserts" in idx.category_names or "Dessert" in idx.category_names


def test_has_item_exact_and_fuzzy() -> None:
    assert menu.has_item("Tiramisu").name == "Tiramisu"
    assert "Tomahawk" in menu.has_item("tomahawk").name
    assert menu.has_item("does not exist xyzzy") is None


def test_has_item_translates_russian() -> None:
    hit = menu.has_item("лобстер")
    assert hit is not None and "Lobster" in hit.name


def test_list_category_returns_dishes() -> None:
    desserts = menu.list_category("Desserts", limit=3)
    assert desserts and len(desserts) <= 3


def test_match_faq_specific_dish_beats_category() -> None:
    answer = match_faq("Do you have a tomahawk steak?", "en-US")
    assert answer is not None
    assert "Tomahawk" in answer.text


def test_match_faq_category_listing() -> None:
    answer = match_faq("What desserts do you have?", "en-US")
    assert answer is not None
    assert answer.topic.startswith("menu_category_")


def test_match_faq_price_known_dish_returns_price() -> None:
    answer = match_faq("How much is the tomahawk?", "en-US")
    assert answer is not None
    assert "$" in answer.text or "market" in answer.text.lower()


def test_match_faq_price_unknown_dish_defers() -> None:
    answer = match_faq("How much is the xyzzy?", "en-US")
    assert answer is not None
    assert answer.topic == "menu_price_deferred"


def test_match_faq_russian_dish_lookup() -> None:
    answer = match_faq("У вас есть лобстер?", "ru-RU")
    assert answer is not None
    assert answer.topic.startswith("menu_item_")


def test_match_faq_booking_intent_skips_menu() -> None:
    assert match_faq("I want to book a table", "en-US") is None
