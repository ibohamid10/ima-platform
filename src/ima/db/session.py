"""Async database engine and session helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ima.config import settings

_ENGINE_CACHE: dict[str, AsyncEngine] = {}


def get_engine(database_url: str | None = None) -> AsyncEngine:
    """Return a cached async SQLAlchemy engine."""

    url = database_url or settings.database_url
    if url not in _ENGINE_CACHE:
        _ENGINE_CACHE[url] = create_async_engine(url, pool_pre_ping=True)
    return _ENGINE_CACHE[url]


def get_session_factory(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory for the given database URL."""

    return async_sessionmaker(get_engine(database_url), expire_on_commit=False)


@asynccontextmanager
async def session_scope(database_url: str | None = None) -> AsyncIterator[AsyncSession]:
    """Yield an async database session."""

    session_factory = get_session_factory(database_url)
    async with session_factory() as session:
        yield session
