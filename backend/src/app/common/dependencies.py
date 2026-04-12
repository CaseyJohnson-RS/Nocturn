from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.common.database.engine import get_db
from src.app.common.redis import get_redis

DBSession = Annotated[
    AsyncSession,
    Depends(get_db),
]
"""FastAPI dependency alias for an asynchronous SQLAlchemy database session.

This type is used in endpoint signatures to automatically provide an
`AsyncSession` instance from the application's database session provider.
"""

RedisClient = Annotated[
    Redis,
    Depends(get_redis),
]
"""FastAPI dependency alias for an asynchronous Redis client.

This type is used in endpoint signatures to inject a Redis connection
from the application's Redis provider dependency.
"""
