"""Typed settings for the Twilio Voice receptionist."""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Twilio Voice
    twilio_account_sid: str = "AC00000000000000000000000000000000"
    twilio_auth_token: SecretStr = SecretStr("dummy_token")
    twilio_voice_from: str = "+13105550123"
    twilio_validate_signature: bool = True
    debug_skip_twilio_signature: bool = False

    # Voice UX
    twilio_say_voice: str = "woman"
    twilio_say_language: str = "en-US"
    gather_timeout_seconds: int = 4
    gather_speech_timeout: str = "auto"
    voice_mode: str = "twiml_gather"  # twiml_gather | conversationrelay
    conversationrelay_primary_language: str = "en-US"
    conversationrelay_tts_provider: str = "ElevenLabs"
    conversationrelay_stt_provider: str = "Deepgram"
    # ElevenLabs multilingual female voice; one ID covers en/es/ru.
    # Override per locale via the *_voice_* settings below if needed.
    conversationrelay_tts_voice: str = "Rachel"
    conversationrelay_voice_en: str = ""
    conversationrelay_voice_es: str = ""
    conversationrelay_voice_ru: str = ""
    llm_streaming_enabled: bool = True
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"

    # Routing
    app_base_url: str = "http://localhost:8000"

    # Integrations
    slack_webhook_url: SecretStr | None = None
    crm_webhook_url: str | None = None
    crm_auth_bearer: SecretStr | None = None
    enable_sevenrooms: bool = False
    sevenrooms_api_base_url: str | None = None
    sevenrooms_api_key: SecretStr | None = None
    sevenrooms_venue_id: str | None = None

    # Recording + analytics
    record_calls: bool = True
    recording_channels: str = "dual"
    recording_track: str = "both"
    recording_trim: str = "trim-silence"
    recording_status_callback_path: str = "/webhooks/voice/recording-status"

    # App
    business_name: str = "Novikov Beverly Hills"
    business_timezone: str = "America/Los_Angeles"
    business_phone_display: str = "+1 (310) 555-0199"
    database_url: str = "sqlite+aiosqlite:///./data/voice_leads.db"
    log_level: str = "INFO"
    environment: str = "development"
    sentry_dsn: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
