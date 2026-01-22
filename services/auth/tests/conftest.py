import pytest
from sqlalchemy import text

from app.adapters.outbound.persistence.sqlalchemy.models import Base
from app.infrastructure.db.postgres import engine, async_session_factory


@pytest.fixture(scope="function")
async def async_session():
    
    async with async_session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        await session.commit()
        yield session
    
    await engine.dispose() # It's necessary, lol 