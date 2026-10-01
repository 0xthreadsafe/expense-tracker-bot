"""Shared fixtures.

Tests run against an in-memory SQLite database created fresh for each test, so
they are fast and cannot leak state into one another.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from expensebot.models import Base


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
