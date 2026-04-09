import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

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
    from app.modules.ai.models import ChatMessage, ChatSession  # type: ignore # noqa: F401
    from app.modules.auth.models import (  # type: ignore # noqa: F401 
        RefreshToken,  # type: ignore
        User,  # type: ignore
        VerificationToken,  # type: ignore
    )
    from app.modules.notes.models import Note, NoteTag  # type: ignore # noqa: F401
    from app.modules.rag.models import EmbeddingTask, NoteChunk  # type: ignore # noqa: F401
    from app.modules.tags.models import Tag  # type: ignore # noqa: F401

    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables():
    yield
    async with test_engine.begin() as conn:
        table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        if table_names:
            await conn.execute(text(f"TRUNCATE {table_names} CASCADE"))


@pytest.fixture()
async def db() -> AsyncGenerator[AsyncSession]:
    async with test_session_factory() as session:
        yield session


@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession]:
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from app import main as main_module

    @asynccontextmanager
    async def _test_lifespan(app: Any):
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


@pytest.fixture(autouse=True)
async def flush_redis():
    await redis_client.flushdb(asynchronous=True) # type: ignore
    yield
    await redis_client.flushdb(asynchronous=True) # type: ignore