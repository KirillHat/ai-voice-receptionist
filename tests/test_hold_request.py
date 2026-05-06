from app.services import prosody


def test_detect_hold_request_english() -> None:
    assert prosody.detect_hold_request("hold on, let me check my calendar")
    assert prosody.detect_hold_request("just a second")
    assert prosody.detect_hold_request("give me a moment")
    assert prosody.detect_hold_request("Let me check.")
    assert not prosody.detect_hold_request("eight pm")
    assert not prosody.detect_hold_request("party of four")


def test_detect_hold_request_russian() -> None:
    assert prosody.detect_hold_request("Подождите секундочку")
    assert prosody.detect_hold_request("Одну секунду")
    assert prosody.detect_hold_request("Сейчас посмотрю")
    assert prosody.detect_hold_request("Дайте мне минуту")
    assert not prosody.detect_hold_request("На двух гостей")


def test_detect_hold_request_spanish() -> None:
    assert prosody.detect_hold_request("Un momento, por favor")
    assert prosody.detect_hold_request("Déjeme revisar")
    assert prosody.detect_hold_request("Espera un segundo")
    assert not prosody.detect_hold_request("Para dos personas")


def test_hold_ack_per_language() -> None:
    assert "торопитесь" in prosody.hold_acknowledgement("ru-RU").lower()
    assert "tiempo" in prosody.hold_acknowledgement("es-US").lower()
    assert "time" in prosody.hold_acknowledgement("en-US").lower()
