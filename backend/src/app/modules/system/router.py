"""Operational endpoints: liveness, readiness, metrics.

Split on purpose:

* ``/livez``  — is the process alive? Never touches a dependency, so a database
  blip can never cause the orchestrator to restart-loop a healthy process.
* ``/readyz`` — should this instance receive traffic? Checks Postgres and Redis.
* ``/metrics``— Prometheus scrape target.

``/api/health`` is kept as-is for backwards compatibility with the existing
frontend and Render's health check.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import text

from src.app.common.database.engine import engine
from src.app.common.observability.metrics import (
    dependency_check_duration_seconds,
    dependency_up,
    render_metrics,
)
from src.app.common.redis import redis_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

DEPENDENCY_TIMEOUT_SECONDS = 2.0
# Readiness is polled every couple of seconds by the orchestrator and by the
# load balancer; caching keeps the probe from becoming its own load source.
CACHE_TTL_SECONDS = 2.0

_cache: dict[str, Any] = {"at": 0.0, "result": None}


async def _check_postgres() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _check_redis() -> None:
    await redis_client.ping()


async def _probe(name: str, coro_factory) -> tuple[bool, str | None]:
    started = time.perf_counter()
    try:
        await asyncio.wait_for(coro_factory(), timeout=DEPENDENCY_TIMEOUT_SECONDS)
    except Exception as exc:
        dependency_up.labels(dependency=name).set(0)
        logger.warning("Readiness probe failed", extra={"dependency": name, "error": str(exc)})
        return False, f"{type(exc).__name__}: {exc}"
    else:
        dependency_up.labels(dependency=name).set(1)
        return True, None
    finally:
        dependency_check_duration_seconds.labels(dependency=name).observe(
            time.perf_counter() - started
        )


@router.get("/livez", summary="Liveness probe")
async def livez() -> dict[str, str]:
    """Process is up and the event loop is responsive. No dependencies checked."""
    return {"status": "alive"}


@router.get("/readyz", summary="Readiness probe")
async def readyz(response: Response) -> dict[str, Any]:
    """Instance is ready to serve traffic: Postgres and Redis both reachable."""
    now = time.monotonic()
    if _cache["result"] is not None and now - _cache["at"] < CACHE_TTL_SECONDS:
        payload = _cache["result"]
    else:
        pg_ok, pg_err = await _probe("postgres", _check_postgres)
        redis_ok, redis_err = await _probe("redis", _check_redis)
        payload = {
            "status": "ready" if pg_ok and redis_ok else "not_ready",
            "checks": {
                "postgres": {"ok": pg_ok, "error": pg_err},
                "redis": {"ok": redis_ok, "error": redis_err},
            },
        }
        _cache["at"] = now
        _cache["result"] = payload

    if payload["status"] != "ready":
        response.status_code = 503
    return payload


@router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
async def metrics() -> Response:
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)
