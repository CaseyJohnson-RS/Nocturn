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
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.common.database import Base, get_db
from app.common.redis import redis_client

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

test_engine = create_async_engine(TEST_DATABASE_URL)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables once per test session."""
    # Import models so Base.metadata knows about them
    from app.modules.auth.models import User, RefreshToken, VerificationToken  # noqa: F401

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
    async with test_engine.begin() as conn:
        table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        if table_names:
            await conn.execute(text(f"TRUNCATE {table_names} CASCADE"))


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession]:
    async with test_session_factory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """HTTP client with test DB session override."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession]:
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Patch lifespan to skip migrations/seed in tests
    from app import main as main_module

    @asynccontextmanager
    async def _test_lifespan(app):
        yield

    original_lifespan = main_module.app.router.lifespan_context
    main_module.app.router.lifespan_context = _test_lifespan
    main_module.app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=main_module.app),
        base_url="http://test",
    ) as ac:
        yield ac

    main_module.app.dependency_overrides.clear()
    main_module.app.router.lifespan_context = original_lifespan


@pytest.fixture
async def flush_redis():
    """Flush Redis test database."""
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()
