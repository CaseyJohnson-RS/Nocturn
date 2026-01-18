import aioredis
from app.core.settings import settings


_redis = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis
