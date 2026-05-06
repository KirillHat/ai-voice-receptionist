"""Async SQLAlchemy engine + session scope helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.storage.models import Base

_settings = get_settings()

engine = create_async_engine(_settings.database_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_lightweight_migrations)


def _apply_lightweight_migrations(sync_conn) -> None:
    """Add columns introduced after a table was first created.

    Uses ``ALTER TABLE ADD COLUMN``. Safe for SQLite (which doesn't support
    DROP/ALTER), and Postgres tolerates ``IF NOT EXISTS``. We catch the
    duplicate-column error so the call is idempotent on every dialect.
    """
    from sqlalchemy import text as _sql

    pending: tuple[tuple[str, str, str], ...] = (
        ("caller_profiles", "last_guest_name", "VARCHAR(128)"),
        ("caller_profiles", "visit_count", "INTEGER DEFAULT 0"),
        ("caller_profiles", "last_call_at", "TIMESTAMP"),
    )
    for table, col, ddl in pending:
        try:
            sync_conn.execute(_sql(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        except Exception:
            # Column already exists, or table not yet created — both are fine.
            pass


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
