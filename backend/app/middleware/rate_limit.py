import time
from collections.abc import Callable, Awaitable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.common.exceptions import RateLimitError, ServiceUnavailableError
from app.common.redis import redis_client
from app.config import settings


async def _check_rate_limit(key: str, limit: int, window: int = 60) -> None:
    """Sliding window rate limiter using Redis."""
    try:
        now = time.time()
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        count = results[2]
        if count > limit:
            raise RateLimitError("Too many requests")
    except RateLimitError:
        raise
    except Exception:
        # Redis unavailable — behavior depends on endpoint type
        raise


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_user_id(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        from app.modules.auth.service import AuthService
        payload = AuthService.decode_access_token(auth_header.removeprefix("Bearer "))
        return payload.get("sub")
    except Exception:
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        method = request.method

        if method == "OPTIONS" or path in ("/api/health", "/api/docs", "/api/openapi.json"):
            return await call_next(request)

        try:
            await self._apply_rate_limit(request, path)
        except RateLimitError:
            raise
        except Exception:
            # Redis down
            if method in ("GET", "HEAD"):
                # Fail-open for reads (NFR-REL-03)
                return await call_next(request)
            raise ServiceUnavailableError("Service temporarily unavailable")

        return await call_next(request)

    async def _apply_rate_limit(self, request: Request, path: str) -> None:
        ip = _get_client_ip(request)

        if path.startswith("/api/auth/"):
            if path in ("/api/auth/request-password-reset", "/api/auth/resend-confirmation"):
                await _check_rate_limit(f"rl:email:{ip}", settings.rate_email_ops_per_minute)
            elif path in ("/api/auth/confirm-email", "/api/auth/reset-password"):
                await _check_rate_limit(f"rl:verify:{ip}", settings.rate_verify_per_minute)
            elif path == "/api/auth/refresh":
                await _check_rate_limit(f"rl:refresh:{ip}", settings.rate_refresh_per_minute)
            else:
                await _check_rate_limit(f"rl:auth:{ip}", settings.rate_auth_per_minute)
            return

        user_id = _get_user_id(request)
        if not user_id:
            return

        if path.startswith("/api/ai/"):
            await _check_rate_limit(f"rl:ai:{user_id}", settings.rate_ai_per_minute)
        else:
            await _check_rate_limit(f"rl:crud:{user_id}", settings.rate_crud_per_minute)
