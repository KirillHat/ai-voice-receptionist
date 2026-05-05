"""Turn-taking heuristics for conversational pacing and latency behavior."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class TurnTiming:
    pause_ms: int
    holding_delay_ms: int
    utterance_kind: str


def compute_timing(user_text: str) -> TurnTiming:
    settings = get_settings()
    word_count = len([w for w in user_text.strip().split() if w])

    if word_count <= settings.voice_fast_utterance_words:
        pause_ms = settings.voice_soft_pause_min_ms
        holding_delay_ms = settings.voice_holding_phrase_delay_fast_ms
        kind = "fast"
    elif word_count >= settings.voice_long_utterance_words:
        pause_ms = settings.voice_soft_pause_max_ms
        holding_delay_ms = settings.voice_holding_phrase_delay_slow_ms
        kind = "long"
    else:
        ratio = (word_count - settings.voice_fast_utterance_words) / max(
            1,
            settings.voice_long_utterance_words - settings.voice_fast_utterance_words,
        )
        span = settings.voice_soft_pause_max_ms - settings.voice_soft_pause_min_ms
        pause_ms = int(settings.voice_soft_pause_min_ms + ratio * span)
        holding_span = settings.voice_holding_phrase_delay_slow_ms - settings.voice_holding_phrase_delay_fast_ms
        holding_delay_ms = int(settings.voice_holding_phrase_delay_fast_ms + ratio * holding_span)
        kind = "medium"

    if user_text.strip().endswith(("?", "？")):
        pause_ms = max(settings.voice_soft_pause_min_ms, pause_ms - 70)

    return TurnTiming(
        pause_ms=max(settings.voice_soft_pause_min_ms, min(settings.voice_soft_pause_max_ms, pause_ms)),
        holding_delay_ms=max(500, holding_delay_ms),
        utterance_kind=kind,
    )


def is_long_utterance(user_text: str) -> bool:
    settings = get_settings()
    return len([w for w in user_text.strip().split() if w]) >= settings.voice_long_utterance_words
