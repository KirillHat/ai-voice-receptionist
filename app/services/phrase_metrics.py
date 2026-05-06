"""In-memory tally of canonical TTS phrases emitted by the agent.

ConversationRelay renders TTS on Twilio's edge from text we send, billed
per minute, so a literal audio cache isn't possible without abandoning
ConversationRelay. What IS useful is knowing which canned phrases get
emitted most — those are the candidates to shorten or skip.

The counter is process-local (resets on restart). Aggregate via the
/analytics/phrase-usage endpoint or push to a stats backend later.
"""

from __future__ import annotations

import threading
from collections import Counter
from typing import Final

# Canonical labels for known phrases. Anything else is bucketed as 'dynamic'.
_KNOWN_PHRASE_LABELS: Final[dict[str, str]] = {
    "One moment, please.": "holding.en",
    "Un momento, por favor.": "holding.es",
    "Одну секунду, пожалуйста.": "holding.ru",
    "Of course.": "ack.en",
    "Claro.": "ack.es",
    "Конечно.": "ack.ru",
    "Of course, take your time.": "hold_ack.en",
    "Por supuesto, tómese su tiempo.": "hold_ack.es",
    "Конечно, не торопитесь.": "hold_ack.ru",
}

_lock = threading.Lock()
_counter: Counter[str] = Counter()


def label_for(text: str) -> str:
    """Return canonical label, or one of: 'readback.*', 'completion.*', 'dynamic'."""
    if not text:
        return "empty"
    stripped = text.strip()
    if stripped in _KNOWN_PHRASE_LABELS:
        return _KNOWN_PHRASE_LABELS[stripped]
    if stripped.startswith("Just to confirm:") or stripped.startswith("Уточняю:") or stripped.startswith("Para confirmar:"):
        return "readback"
    if "noted — our team" in stripped or "наша команда" in stripped or "le confirmará" in stripped:
        return "completion"
    return "dynamic"


def record(text: str) -> None:
    label = label_for(text)
    with _lock:
        _counter[label] += 1


def snapshot() -> dict[str, int]:
    with _lock:
        return dict(_counter)


def reset() -> None:
    with _lock:
        _counter.clear()
