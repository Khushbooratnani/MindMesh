"""
Dedicated database connection manager for the separate Private Locker Authentication Database.
Defaults to an isolated URL or in-memory SQLite during local testing.
"""
from collections.abc import AsyncGenerator
import os
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.local_first.models import LockerAuthBase

# Allow configuring a dedicated database URL for mindmesh_locker_auth
LOCKER_AUTH_DATABASE_URL = os.getenv(
    "LOCKER_AUTH_DATABASE_URL",
    getattr(settings, "locker_auth_database_url", None)
    or "sqlite+aiosqlite:///:memory:",
)

_auth_engine: Optional[AsyncEngine] = None
_auth_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def get_locker_auth_engine() -> AsyncEngine:
    global _auth_engine
    if _auth_engine is None:
        is_sqlite = "sqlite" in LOCKER_AUTH_DATABASE_URL
        connect_args = {"check_same_thread": False} if is_sqlite else {}
        _auth_engine = create_async_engine(
            LOCKER_AUTH_DATABASE_URL,
            connect_args=connect_args,
            poolclass=StaticPool if is_sqlite else None,
            echo=False,
        )
    return _auth_engine


def get_locker_auth_session_maker() -> async_sessionmaker[AsyncSession]:
    global _auth_session_maker
    if _auth_session_maker is None:
        engine = get_locker_auth_engine()
        _auth_session_maker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _auth_session_maker


async def init_locker_auth_db() -> None:
    """Initialize schema for the separate locker auth database."""
    engine = get_locker_auth_engine()
    async with engine.begin() as conn:
        await conn.run_sync(LockerAuthBase.metadata.create_all)


async def get_locker_auth_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining a session on the separate auth database."""
    session_maker = get_locker_auth_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
