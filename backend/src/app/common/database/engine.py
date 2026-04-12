from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
)
"""
Async SQLAlchemy engine.

This engine manages database connections using an asynchronous driver.
It is configured via application settings:

- database_url: connection string for the database.
- echo: enables SQL query logging when True.
- pool_size: number of persistent connections maintained in the pool.
- max_overflow: number of extra connections allowed beyond the pool size.

The engine is intended to be shared across the entire application.
"""

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
"""
Factory for creating AsyncSession instances.

Parameters:
- engine: the async engine used to establish DB connections.
- expire_on_commit=False: prevents ORM objects from being expired after commit,
  allowing continued access to their attributes without reloading from the DB.

This factory should be used whenever a new database session is required.
"""


async def get_db() -> AsyncGenerator[AsyncSession]:
    """
    Provide a transactional database session.

    This function is an async generator that yields an AsyncSession.
    It is typically used as a dependency (e.g., in FastAPI) or as a
    context-managed session provider in application services.

    Lifecycle:
    1. A new AsyncSession is created using the session factory.
    2. The session is yielded to the caller.
    3. After the caller finishes:
       - If no exception occurred, the transaction is committed.
       - If an exception occurred, the transaction is rolled back.
    4. The session is automatically closed when the context exits.

    Yields:
        AsyncSession: an active database session.

    Raises:
        Exception: re-raises any exception that occurred during session usage
        after performing a rollback.

    Notes:
        - This pattern enforces a single transaction per usage scope.
        - Be cautious when using nested transactions or manual commits inside
          the yielded session, as it may interfere with this lifecycle.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
