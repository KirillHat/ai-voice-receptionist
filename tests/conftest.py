from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC00000000000000000000000000000000")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "dummy_token")
    monkeypatch.setenv("DEBUG_SKIP_TWILIO_SIGNATURE", "true")
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURE", "true")
    monkeypatch.setenv("RECORD_CALLS", "false")
    monkeypatch.setenv("VOICE_MODE", "twiml_gather")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./data/test_voice.db")

    for db_path in (Path("data/test_voice.db"), Path("data/voice_leads.db")):
        if db_path.exists():
            db_path.unlink()

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

    for db_path in (Path("data/test_voice.db"), Path("data/voice_leads.db")):
        if db_path.exists():
            db_path.unlink()
