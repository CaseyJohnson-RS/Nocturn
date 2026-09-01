"""Pure-ASGI middleware: request correlation + RED metrics + access logs.

Written against the raw ASGI interface (not ``BaseHTTPMiddleware``) for the
same reason the rate limiter is — ``BaseHTTPMiddleware`` wraps the response in
a task group that breaks SSE streaming and swallows client disconnects.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.app.common.observability.logging import request_id_var
from src.app.common.observability.metrics import (
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
)

logger = logging.getLogger("nocturn.access")

REQUEST_ID_HEADER = b"x-request-id"

# Not worth a metrics series, and scraping itself must not inflate the RED rate.
EXCLUDED_PATHS = frozenset({"/metrics", "/livez", "/readyz"})


def _templated_path(scope: Scope) -> str:
    """The route pattern, e.g. ``/api/notes/{note_id}``.

    Starlette puts the matched route into the scope during routing, and because
    downstream apps mutate the same dict we can read it *after* the call. Requests
    that match no route collapse into a single ``<unmatched>`` series so a 404
    scanner cannot explode label cardinality.
    """
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else "<unmatched>"


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["path"] in EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        incoming = headers.get(REQUEST_ID_HEADER)
        request_id = incoming.decode() if incoming else uuid.uuid4().hex
        token = request_id_var.set(request_id)

        method = scope["method"]
        started = time.perf_counter()
        status_code = 500
        # Latency is measured to response *headers*, not to the last body byte:
        # otherwise every SSE stream would land in the top bucket and destroy
        # the latency SLI.
        duration: float | None = None

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, duration
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = time.perf_counter() - started
                message.setdefault("headers", [])
                message["headers"].append((REQUEST_ID_HEADER, request_id.encode()))
            await send(message)

        in_progress = http_requests_in_progress.labels(method=method, path="all")
        in_progress.inc()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            in_progress.dec()
            if duration is None:
                duration = time.perf_counter() - started
            path = _templated_path(scope)
            http_requests_total.labels(
                method=method, path=path, status=str(status_code)
            ).inc()
            http_request_duration_seconds.labels(method=method, path=path).observe(duration)
            logger.info(
                "%s %s %s",
                method,
                scope.get("path", ""),
                status_code,
                extra={
                    "http_method": method,
                    "http_path": path,
                    "http_status": status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            request_id_var.reset(token)
