"""SQLAlchemy models for call sessions and qualified leads."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_sid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    caller_phone: Mapped[str] = mapped_column(String(32), index=True)

    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    guest_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    party_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reservation_datetime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    special_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recording_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recording_duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="in_progress")
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    transcript: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_sid: Mapped[str] = mapped_column(String(64), index=True)
    caller_phone: Mapped[str] = mapped_column(String(32), index=True)
    intent: Mapped[str] = mapped_column(String(32))
    guest_name: Mapped[str] = mapped_column(String(128))
    party_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reservation_datetime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    special_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualification_label: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class CallerProfile(Base):
    __tablename__ = "caller_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    caller_phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    preferred_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    speech_pace: Mapped[str | None] = mapped_column(String(16), nullable=True)
    formality: Mapped[str | None] = mapped_column(String(16), nullable=True)
    typical_intents: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    last_guest_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    visit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_call_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
