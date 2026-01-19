import pytest
from sqlalchemy import text

from app.models.base import Base
from app.core.db import postgres_engine, postgres_async_session_factory


@pytest.fixture(scope="function")
async def async_session():
    
    async with postgres_async_session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        await session.commit()
        yield session
    
    await postgres_engine.dispose() # It's necessary, lol 