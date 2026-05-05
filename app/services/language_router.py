"""Language normalization and localized human-like prompts."""

from __future__ import annotations

import re

from app.storage.models import CallSession

_DEFAULT_LANG = "en-US"


def normalize_language(lang: str | None, text: str | None = None) -> str:
    raw = (lang or "").strip().lower()
    if raw in {"en", "en-us", "en-gb"}:
        # The STT layer may say "en-US" while the caller actually asked to
        # switch — fall through to the text heuristics before trusting it.
        forced = _force_switch_from_text(text)
        if forced is not None:
            return forced
        return "en-US"
    if raw in {"es", "es-us", "es-es"}:
        return "es-US"
    if raw in {"ru", "ru-ru"}:
        return "ru-RU"
    if text:
        if re.search(r"[а-яА-Я]", text):
            return "ru-RU"
        if re.search(r"[¿¡]", text) or any(
            token in text.lower() for token in ("hola", "reserva", "mesa", "para")
        ):
            return "es-US"
        forced = _force_switch_from_text(text)
        if forced is not None:
            return forced
    return _DEFAULT_LANG


_SWITCH_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "ru-RU",
        (
            r"\b(?:in |speak |switch to |change to |po[\s-]?)?russian\b",
            r"\bна русск\w*\b",
            r"\bпо[\s-]?русски\b",
            r"\bговорить (?:по\s)?русск\w*\b",
        ),
    ),
    (
        "es-US",
        (
            r"\b(?:in |speak |switch to |change to )?spanish\b",
            r"\bespañol\b",
            r"\bhabla\w* español\b",
        ),
    ),
    (
        "en-US",
        (
            r"\b(?:in |speak |switch to |change to |back to )?english\b",
            r"\bпо[\s-]?английски\b",
        ),
    ),
)


def _force_switch_from_text(text: str | None) -> str | None:
    if not text:
        return None
    lower = text.lower()
    for code, patterns in _SWITCH_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, lower):
                return code
    return None


def build_reply(session: CallSession, *, missing_field: str | None, lang: str) -> str:
    if missing_field is None:
        return _completion_message(session, lang)
    return _question_for_field(missing_field, session.intent, lang)


def _question_for_field(field: str, intent: str | None, lang: str) -> str:
    prompts = {
        "en-US": {
            "intent": "Are you calling for a reservation, private event, or takeout?",
            "guest_name": "May I get your full name for the booking note?",
            "party_size": "How many guests should I note for your party?",
            "reservation_datetime": (
                "What date and time should I note?"
                if intent != "takeout"
                else "What time should we expect your pickup?"
            ),
            "default": "Could you share one more detail so I can finish this for you?",
        },
        "es-US": {
            "intent": "¿Llama por una reserva, un evento privado o para llevar?",
            "guest_name": "¿Me comparte su nombre completo para la reserva?",
            "party_size": "¿Para cuántas personas debo anotarlo?",
            "reservation_datetime": (
                "¿Qué fecha y hora le viene bien?"
                if intent != "takeout"
                else "¿A qué hora desea recoger el pedido?"
            ),
            "default": "¿Me comparte un detalle más para terminar su solicitud?",
        },
        "ru-RU": {
            "intent": "Вы звоните по поводу брони, частного мероприятия или заказа навынос?",
            "guest_name": "Подскажите, пожалуйста, ваше полное имя для брони.",
            "party_size": "На сколько гостей оформить заявку?",
            "reservation_datetime": (
                "Какую дату и время вам удобно забронировать?"
                if intent != "takeout"
                else "Во сколько вам будет удобно забрать заказ?"
            ),
            "default": "Поделитесь, пожалуйста, еще одной деталью, и я завершу заявку.",
        },
    }

    bundle = prompts.get(lang, prompts[_DEFAULT_LANG])
    return bundle.get(field, bundle["default"])


def _completion_message(session: CallSession, lang: str) -> str:
    guest = session.guest_name or "guest"
    party = str(session.party_size) if session.party_size else "-"
    when = session.reservation_datetime or "-"

    if lang == "es-US":
        return (
            f"Perfecto, {guest}. Ya está todo anotado. "
            f"Tipo: {session.intent or 'consulta'}. Personas: {party}. Fecha y hora: {when}. "
            "Nuestro equipo le confirmará en breve."
        )
    if lang == "ru-RU":
        return (
            f"Отлично, {guest}. Я все зафиксировала. "
            f"Тип запроса: {session.intent or 'запрос'}. Гостей: {party}. Дата и время: {when}. "
            "Наша команда скоро свяжется для подтверждения."
        )
    return (
        f"Perfect, {guest}. I have everything noted: "
        f"type {session.intent or 'inquiry'}, party size {party}, time {when}. "
        "Our team will confirm shortly."
    )
