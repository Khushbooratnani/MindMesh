import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database.connection.session import get_db_session
from app.database.models.base import Base
from app.database.models.user import UserModel
from app.services.auth_service import AuthService
from app.main import app

# Shared async test engine using in-memory SQLite with static pool
_TEST_ENGINE: AsyncEngine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TEST_SESSION_MAKER = async_sessionmaker(
    bind=_TEST_ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables in the in-memory test database for the entire test session."""
    async def _init_tables():
        async with _TEST_ENGINE.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with _TEST_SESSION_MAKER() as session:
            user = await session.get(UserModel, "U_DEVELOPMENT")
            if not user:
                user = UserModel(
                    id="U_DEVELOPMENT",
                    username="dev_user",
                    password_hash=AuthService.hash_password("DevPassword123!"),
                    created_at=datetime.now(timezone.utc),
                )
                session.add(user)
                await session.commit()

    asyncio.run(_init_tables())
    yield
    async def _drop_tables():
        async with _TEST_ENGINE.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await _TEST_ENGINE.dispose()

    asyncio.run(_drop_tables())


@pytest.fixture(autouse=True)
def override_database_dependency():
    """Override FastAPI get_db_session with the test session maker."""
    async def _test_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with _TEST_SESSION_MAKER() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = _test_get_db_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
def db_session():
    """Provide a test session maker helper."""
    return _TEST_SESSION_MAKER
