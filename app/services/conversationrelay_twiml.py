"""Build TwiML for Twilio ConversationRelay sessions."""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from app.config import get_settings
from app.services.business_hours import closed_greeting, is_open_now


def _build_welcome_greeting() -> str:
    settings = get_settings()
    # California is a two-party-consent state: we cannot record without
    # disclosing it. Prepend the disclosure whenever recording is on.
    disclosure = (
        "This call may be recorded for quality and training. "
        if settings.record_calls else ""
    )
    if is_open_now():
        return (
            f"{disclosure}"
            "Good evening, thank you for calling Novikov Beverly Hills. "
            "How may I help you?"
        )
    closed = closed_greeting("en-US")
    return (
        f"{disclosure}"
        "Thank you for calling Novikov Beverly Hills. "
        f"{closed} How may I help you?"
    )


def conversationrelay_response() -> str:
    settings = get_settings()

    root = Element("Response")
    connect = SubElement(
        root,
        "Connect",
        {
            "action": _absolute_url("/webhooks/voice/relay-action"),
            "method": "POST",
        },
    )

    relay_attrs = {
        "url": _ws_url("/ws/conversationrelay"),
        "welcomeGreeting": _build_welcome_greeting(),
        "welcomeGreetingInterruptible": "any",
        "language": settings.conversationrelay_primary_language,
        "ttsProvider": settings.conversationrelay_tts_provider,
        "transcriptionProvider": settings.conversationrelay_stt_provider,
        "interruptible": "any",
        "reportInputDuringAgentSpeech": "speech",
        "ignoreBackchannel": "true",
        "dtmfDetection": "true",
    }
    if settings.conversationrelay_tts_voice:
        relay_attrs["voice"] = settings.conversationrelay_tts_voice
    relay = SubElement(connect, "ConversationRelay", relay_attrs)

    languages = (
        ("en-US", settings.conversationrelay_voice_en),
        ("es-US", settings.conversationrelay_voice_es),
        ("ru-RU", settings.conversationrelay_voice_ru),
    )
    for code, locale_voice in languages:
        attrs = {
            "code": code,
            "ttsProvider": settings.conversationrelay_tts_provider,
            "transcriptionProvider": settings.conversationrelay_stt_provider,
        }
        chosen_voice = locale_voice or settings.conversationrelay_tts_voice
        if chosen_voice:
            attrs["voice"] = chosen_voice
        SubElement(relay, "Language", attrs)

    return tostring(root, encoding="unicode")


def relay_action_response() -> str:
    root = Element("Response")
    SubElement(root, "Say").text = "Thank you for calling. Goodbye."
    SubElement(root, "Hangup")
    return tostring(root, encoding="unicode")


def _absolute_url(path: str) -> str:
    settings = get_settings()
    return settings.app_base_url.rstrip("/") + "/" + path.lstrip("/")


def _ws_url(path: str) -> str:
    url = _absolute_url(path)
    if url.startswith("https://"):
        return "wss://" + url.removeprefix("https://")
    if url.startswith("http://"):
        return "ws://" + url.removeprefix("http://")
    return url
