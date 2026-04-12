import redis.asyncio as aioredis

from src.app.config import settings

redis_client: aioredis.Redis = aioredis.from_url(  # type: ignore[no-any-return]
    settings.redis_url,
    decode_responses=True,
)
"""Singleton Redis client instance.

This client is initialized once at application startup using the configured
Redis URL. It is reused across requests to avoid creating multiple connections.
"""


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency that provides an async Redis client.

    Returns the shared Redis client instance used by the application.
    Intended for use with FastAPI's dependency injection system.
    """
    return redis_client