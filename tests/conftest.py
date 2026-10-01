"""Shared fixtures.

Tests run against an in-memory SQLite database created fresh for each test, so
they are fast and cannot leak state into one another.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import expensebot.db as db_module
from expensebot.config import get_settings
from expensebot.handlers.errors import reset_rate_limits
from expensebot.models import Base


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply configuration from the environment instead of the developer's .env.

    Environment variables take precedence over the dotenv file, so the real
    .env is never consulted and the suite cannot depend on a local secret.
    """
    monkeypatch.setenv("BOT_TOKEN", "123456789:AAFakeTokenUsedOnlyInTests")
    monkeypatch.setenv("BOT_MODE", "polling")
    monkeypatch.setenv("TIMEZONE", "Asia/Tehran")
    monkeypatch.setenv("CURRENCY", "IRR")
    monkeypatch.setenv("DEFAULT_LOCALE", "en")
    get_settings.cache_clear()
    # The limiter keeps process-wide state; without this one test's call would
    # throttle the next one.
    reset_rate_limits()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    # StaticPool keeps every checkout on the same connection, without which an
    # in-memory database would appear empty to the next connection.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()


@pytest.fixture
async def app_db() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Point the module-level session factory at a throwaway database.

    Handlers reach the database through ``session_scope``, which reads the
    process-wide factory, so tests install their own rather than connecting to
    a real file.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    previous = db_module._session_factory
    db_module._session_factory = factory
    try:
        yield factory
    finally:
        db_module._session_factory = previous
        await engine.dispose()
