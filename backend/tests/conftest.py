import os

# Set test environment BEFORE any app imports
os.environ.update({
    "DATABASE_URL": "postgresql+asyncpg://nocturn:nocturn_test@localhost:5433/nocturn_test",
    "REDIS_URL": "redis://localhost:6380/0",
    "JWT_SECRET": "test-secret-key-at-least-32-characters-long",
    "ADMIN_EMAIL": "admin@test.com",
    "ADMIN_PASSWORD": "Admin123",
    "ADMIN_NICKNAME": "admin",
    "FRONTEND_URL": "http://localhost:3000",
})

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.common.database import Base, get_db
from app.common.redis import redis_client
from app.main import app

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

test_engine = create_async_engine(TEST_DATABASE_URL)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables():
    """Truncate all tables between tests."""
    yield
    async with test_session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession]:
    async with test_session_factory() as session:
        yield session


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def flush_redis():
    """Flush Redis test database before test."""
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()
