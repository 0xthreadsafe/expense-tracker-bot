"""Engine and session lifecycle.

A single engine is created per process and shared; sessions are short-lived and
scoped to one unit of work.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from expensebot.models import Base

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_directory(url: str) -> None:
    """SQLite will not create a missing parent directory for its file."""
    prefix = "sqlite+aiosqlite:///"
    if not url.startswith(prefix) or url.endswith(":memory:"):
        return
    path = Path(url[len(prefix) :])
    path.parent.mkdir(parents=True, exist_ok=True)


async def init_db(url: str, *, echo: bool = False) -> None:
    """Create the engine and the schema. Called once at startup."""
    global _engine, _session_factory

    _ensure_sqlite_directory(url)
    _engine = create_async_engine(url, echo=echo, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database ready")


async def dispose_db() -> None:
    """Close pooled connections. Called at shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("init_db() must be called before using the database")
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a session that commits on success and rolls back on failure.

    Handlers use this so that a half-applied write can never be left behind by
    an exception partway through.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
