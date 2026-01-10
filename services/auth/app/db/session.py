from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.db.engine import engine

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
