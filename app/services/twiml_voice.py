"""Helpers for building TwiML voice responses."""

from __future__ import annotations

from twilio.twiml.voice_response import Gather, VoiceResponse

from app.config import get_settings


def gather_response(*, prompt: str, action_path: str) -> str:
    settings = get_settings()
    response = VoiceResponse()

    gather = Gather(
        input="speech dtmf",
        action=action_path,
        method="POST",
        timeout=settings.gather_timeout_seconds,
        speech_timeout=settings.gather_speech_timeout,
        action_on_empty_result=True,
    )
    # Split long prompts into smaller chunks to sound less robotic.
    for sentence in _split_for_voice(prompt):
        gather.say(sentence, voice=settings.twilio_say_voice, language=settings.twilio_say_language)
        gather.pause(length=1)
    response.append(gather)

    response.say(
        "I did not receive any input. Please call again if you still need assistance.",
        voice=settings.twilio_say_voice,
        language=settings.twilio_say_language,
    )
    response.hangup()
    return str(response)


def goodbye_response(*, summary_prompt: str) -> str:
    settings = get_settings()
    response = VoiceResponse()
    for sentence in _split_for_voice(summary_prompt):
        response.say(sentence, voice=settings.twilio_say_voice, language=settings.twilio_say_language)
        response.pause(length=1)
    response.say(
        "Thank you for calling Novikov Beverly Hills. Goodbye.",
        voice=settings.twilio_say_voice,
        language=settings.twilio_say_language,
    )
    response.hangup()
    return str(response)


def _split_for_voice(text: str) -> list[str]:
    parts = [segment.strip() for segment in text.split(".") if segment.strip()]
    if not parts:
        return [text]
    return [part + "." for part in parts]
