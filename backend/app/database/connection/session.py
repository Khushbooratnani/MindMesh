from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def create_async_engine_instance(
    database_url: str | None = None,
    echo: bool | None = None,
    **engine_kwargs: Any,
) -> AsyncEngine:
    """Create a new AsyncEngine instance."""
    url = database_url or settings.database_url
    is_echo = echo if echo is not None else settings.database_echo
    
    # SQLite in-memory / testing configuration adjustments
    if "sqlite" in url:
        return create_async_engine(
            url,
            echo=is_echo,
            **engine_kwargs,
        )

    # PostgreSQL / asyncpg configuration
    return create_async_engine(
        url,
        echo=is_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        **engine_kwargs,
    )


def get_async_engine() -> AsyncEngine:
    """Get or initialize the shared singleton AsyncEngine."""
    global _engine, _session_maker
    if _engine is None:
        _engine = create_async_engine_instance()
        _session_maker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get or initialize the shared async session maker."""
    global _session_maker
    if _session_maker is None:
        get_async_engine()
    assert _session_maker is not None
    return _session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an async database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db_engine() -> None:
    """Dispose of the active engine connection pool."""
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None


# Alias for direct session factory access
AsyncSessionLocal = get_session_maker
