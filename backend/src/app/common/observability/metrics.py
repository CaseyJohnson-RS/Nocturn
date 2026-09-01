"""Prometheus metrics for the API and the worker.

Naming follows the Prometheus conventions: ``<namespace>_<subsystem>_<unit>``,
counters end in ``_total``, durations are seconds. Label sets are deliberately
small — the HTTP path label is the *templated* route (``/api/notes/{note_id}``),
never the raw URL, so cardinality stays bounded.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

NAMESPACE = "nocturn"

# --- HTTP (RED: rate, errors, duration) ------------------------------------

http_requests_total = Counter(
    f"{NAMESPACE}_http_requests_total",
    "Total HTTP requests handled.",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    f"{NAMESPACE}_http_request_duration_seconds",
    "HTTP request latency.",
    ["method", "path"],
    # Tuned for a CRUD API: most traffic should land in the first few buckets.
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_requests_in_progress = Gauge(
    f"{NAMESPACE}_http_requests_in_progress",
    "HTTP requests currently being served.",
    ["method", "path"],
)

# --- Dependencies ----------------------------------------------------------

dependency_up = Gauge(
    f"{NAMESPACE}_dependency_up",
    "Readiness of a downstream dependency (1 = reachable, 0 = not).",
    ["dependency"],
)

dependency_check_duration_seconds = Histogram(
    f"{NAMESPACE}_dependency_check_duration_seconds",
    "Duration of a readiness probe against a dependency.",
    ["dependency"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
)

# --- Rate limiting ---------------------------------------------------------

rate_limit_rejected_total = Counter(
    f"{NAMESPACE}_rate_limit_rejected_total",
    "Requests rejected by the rate limiter.",
    ["bucket"],
)

rate_limit_errors_total = Counter(
    f"{NAMESPACE}_rate_limit_errors_total",
    "Rate limiter failures (Redis unreachable). Drives the fail-open alert.",
    ["outcome"],
)

# --- LLM provider (RouterAI) -----------------------------------------------

llm_requests_total = Counter(
    f"{NAMESPACE}_llm_requests_total",
    "Calls to the LLM provider.",
    ["operation", "model", "outcome"],
)

llm_request_duration_seconds = Histogram(
    f"{NAMESPACE}_llm_request_duration_seconds",
    "End-to-end duration of an LLM provider call.",
    ["operation", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0),
)

llm_time_to_first_token_seconds = Histogram(
    f"{NAMESPACE}_llm_time_to_first_token_seconds",
    "Latency from request start to the first streamed token — the SLI users feel.",
    ["model"],
    buckets=(0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 15.0, 30.0),
)

# --- SSE streams -----------------------------------------------------------

sse_active_streams = Gauge(
    f"{NAMESPACE}_sse_active_streams",
    "Currently open Server-Sent Events streams.",
    ["endpoint"],
)

sse_streams_total = Counter(
    f"{NAMESPACE}_sse_streams_total",
    "SSE streams completed, by outcome.",
    ["endpoint", "outcome"],
)

# --- Embedding queue (worker) ---------------------------------------------

embedding_queue_tasks = Gauge(
    f"{NAMESPACE}_embedding_queue_tasks",
    "Tasks in the embedding queue, by status.",
    ["status"],
)

embedding_queue_oldest_pending_seconds = Gauge(
    f"{NAMESPACE}_embedding_queue_oldest_pending_seconds",
    "Age of the oldest pending embedding task — the freshness SLI.",
)

embedding_tasks_total = Counter(
    f"{NAMESPACE}_embedding_tasks_total",
    "Embedding tasks processed by the worker.",
    ["outcome"],
)

embedding_task_duration_seconds = Histogram(
    f"{NAMESPACE}_embedding_task_duration_seconds",
    "Time to embed one note.",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# --- Worker liveness -------------------------------------------------------

worker_loop_iterations_total = Counter(
    f"{NAMESPACE}_worker_loop_iterations_total",
    "Worker main-loop iterations.",
)

worker_last_loop_timestamp_seconds = Gauge(
    f"{NAMESPACE}_worker_last_loop_timestamp_seconds",
    "Unix timestamp of the last completed worker loop — staleness = worker is wedged.",
)

worker_cleanup_deleted_total = Counter(
    f"{NAMESPACE}_worker_cleanup_deleted_total",
    "Rows purged by the periodic cleanup job.",
    ["kind"],
)

# --- Build info ------------------------------------------------------------

build_info = Gauge(
    f"{NAMESPACE}_build_info",
    "Build metadata, always 1. Use for annotating deploys.",
    ["version", "commit", "service"],
)


def set_build_info(service: str, version: str, commit: str) -> None:
    build_info.labels(version=version, commit=commit, service=service).set(1)


@contextmanager
def observe_llm_call(operation: str, model: str) -> Iterator[dict[str, float]]:
    """Time an LLM call and record its outcome.

    Yields a small mutable state dict; streaming callers set
    ``state["first_token_at"]`` when the first chunk arrives so we can derive
    time-to-first-token separately from total duration.
    """
    started = time.perf_counter()
    state: dict[str, float] = {}
    outcome = "success"
    try:
        yield state
    except Exception:
        outcome = "error"
        raise
    finally:
        elapsed = time.perf_counter() - started
        llm_request_duration_seconds.labels(operation=operation, model=model).observe(elapsed)
        llm_requests_total.labels(operation=operation, model=model, outcome=outcome).inc()
        first_token_at = state.get("first_token_at")
        if first_token_at is not None:
            llm_time_to_first_token_seconds.labels(model=model).observe(first_token_at - started)


@contextmanager
def sse_stream(endpoint: str) -> Iterator[None]:
    """Track an open SSE stream and how it ended."""
    sse_active_streams.labels(endpoint=endpoint).inc()
    outcome = "completed"
    try:
        yield
    except BaseException:
        # Client disconnects surface as CancelledError; both are "not completed".
        outcome = "aborted"
        raise
    finally:
        sse_active_streams.labels(endpoint=endpoint).dec()
        sse_streams_total.labels(endpoint=endpoint, outcome=outcome).inc()


def render_metrics() -> tuple[bytes, str]:
    """Return the exposition-format payload and its content type."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
