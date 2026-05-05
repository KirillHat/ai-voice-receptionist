"""Persistence and heuristics for caller-level communication preferences."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models import CallerProfile, CallSession


async def get_or_create_profile(session: AsyncSession, caller_phone: str) -> CallerProfile | None:
    if not caller_phone:
        return None
    result = await session.execute(select(CallerProfile).where(CallerProfile.caller_phone == caller_phone))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = CallerProfile(caller_phone=caller_phone)
        session.add(profile)
        await session.flush()
    return profile


def infer_speech_pace(utterance: str) -> str | None:
    lower = utterance.lower()
    fast_markers = ("quick", "brief", "short", "быстро", "кратко", "rápido", "rapido")
    slow_markers = ("slow", "slower", "step by step", "медлен", "подробнее", "despacio")
    if any(marker in lower for marker in fast_markers):
        return "fast"
    if any(marker in lower for marker in slow_markers):
        return "slow"
    return None


def infer_formality(utterance: str) -> str | None:
    lower = utterance.lower()
    formal_markers = (
        "please",
        "would you",
        "kindly",
        "пожалуйста",
        "будьте добры",
        "por favor",
    )
    casual_markers = ("hey", "yo", "привет", "hola")
    if any(marker in lower for marker in formal_markers):
        return "formal"
    if any(re.search(rf"\b{re.escape(marker)}\b", lower) for marker in casual_markers):
        return "casual"
    return None


def update_profile_from_turn(
    profile: CallerProfile,
    *,
    utterance: str,
    detected_lang: str,
    intent: str | None,
) -> None:
    if not profile.preferred_language or detected_lang and detected_lang != profile.preferred_language:
        profile.preferred_language = detected_lang

    pace = infer_speech_pace(utterance)
    if pace:
        profile.speech_pace = pace

    formality = infer_formality(utterance)
    if formality:
        profile.formality = formality

    if intent:
        intents = dict(profile.typical_intents or {})
        intents[intent] = int(intents.get(intent, 0)) + 1
        profile.typical_intents = intents


def profile_prompt_context(profile: CallerProfile | None) -> str:
    if profile is None:
        return ""

    intent_hist = profile.typical_intents or {}
    top_intent = ""
    if intent_hist:
        top_intent = max(intent_hist.items(), key=lambda item: item[1])[0]

    chunks = []
    if profile.preferred_language:
        chunks.append(f"preferred_language={profile.preferred_language}")
    if profile.speech_pace:
        chunks.append(f"speech_pace={profile.speech_pace}")
    if profile.formality:
        chunks.append(f"formality={profile.formality}")
    if top_intent:
        chunks.append(f"typical_intent={top_intent}")

    return "; ".join(chunks)


def choose_profile_mode(call: CallSession, *, interrupted_recently: bool) -> str:
    if interrupted_recently:
        return "interruption_recovery"
    if call.turn_count <= 1:
        return "greeting"
    if call.status == "qualified":
        return "confirmation"
    if call.intent is None:
        return "clarification"
    return "default"
