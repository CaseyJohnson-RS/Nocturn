import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.app.common.exceptions import RateLimitError
from src.app.common.redis import redis_client
from src.app.config import settings


async def _check_rate_limit(key: str, limit: int, window: int = 60) -> None:
    """Sliding window rate limiter using Redis."""
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


def _get_client_ip(scope: Scope) -> str:
    headers = dict(scope.get("headers", []))
    forwarded = headers.get(b"x-forwarded-for")
    if forwarded:
        return forwarded.decode().split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


def _get_user_id(scope: Scope) -> str | None:
    headers = dict(scope.get("headers", []))
    auth_header = headers.get(b"authorization")
    if not auth_header:
        return None
    auth_str = auth_header.decode()
    if not auth_str.startswith("Bearer "):
        return None
    try:
        from src.app.modules.auth.service import AuthService

        payload = AuthService.decode_access_token(auth_str.removeprefix("Bearer "))
        return payload.get("sub")
    except Exception:
        return None


class RateLimitMiddleware:
    """Pure ASGI rate-limiting middleware (avoids BaseHTTPMiddleware event-loop issues)."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        method = scope["method"]

        if method == "OPTIONS" or path in ("/api/health", "/api/docs", "/api/openapi.json"):
            await self.app(scope, receive, send)
            return

        try:
            await self._apply_rate_limit(scope, path)
        except RateLimitError as exc:
            response = JSONResponse({"detail": exc.detail}, status_code=429)
            await response(scope, receive, send)
            return
        except Exception:
            if method in ("GET", "HEAD"):
                await self.app(scope, receive, send)
                return
            response = JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _apply_rate_limit(self, scope: Scope, path: str) -> None:
        ip = _get_client_ip(scope)

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

        user_id = _get_user_id(scope)
        if not user_id:
            return

        if path.startswith("/api/ai/"):
            await _check_rate_limit(f"rl:ai:{user_id}", settings.rate_ai_per_minute)
        else:
            await _check_rate_limit(f"rl:crud:{user_id}", settings.rate_crud_per_minute)
