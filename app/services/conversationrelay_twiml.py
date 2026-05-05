"""Build TwiML for Twilio ConversationRelay sessions."""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from app.config import get_settings


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
        "welcomeGreeting": (
            "Good evening, thank you for calling Novikov Beverly Hills. "
            "How may I help you?"
        ),
        "welcomeGreetingInterruptible": "any",
        "language": settings.conversationrelay_primary_language,
        "ttsProvider": settings.conversationrelay_tts_provider,
        "voice": settings.conversationrelay_tts_voice,
        "transcriptionProvider": settings.conversationrelay_stt_provider,
        "interruptible": "any",
        "reportInputDuringAgentSpeech": "speech",
        "ignoreBackchannel": "true",
        "dtmfDetection": "true",
    }
    relay = SubElement(connect, "ConversationRelay", relay_attrs)

    languages = (
        ("en-US", settings.conversationrelay_voice_en),
        ("es-US", settings.conversationrelay_voice_es),
        ("ru-RU", settings.conversationrelay_voice_ru),
    )
    for code, locale_voice in languages:
        SubElement(
            relay,
            "Language",
            {
                "code": code,
                "ttsProvider": settings.conversationrelay_tts_provider,
                "voice": locale_voice or settings.conversationrelay_tts_voice,
                "transcriptionProvider": settings.conversationrelay_stt_provider,
            },
        )

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
