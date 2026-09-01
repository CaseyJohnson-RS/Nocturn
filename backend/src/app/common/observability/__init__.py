"""Observability primitives: structured logging, Prometheus metrics, request context.

Kept dependency-light on purpose: only ``prometheus_client`` is required, the
JSON log formatter is hand-rolled so the same code runs in the API and in the
worker without pulling a logging framework into the image.
"""

from src.app.common.observability.logging import (
    get_request_id,
    request_id_var,
    setup_logging,
)
from src.app.common.observability.metrics import (
    REGISTRY,
    observe_llm_call,
    render_metrics,
    sse_stream,
)

__all__ = [
    "REGISTRY",
    "get_request_id",
    "observe_llm_call",
    "render_metrics",
    "request_id_var",
    "setup_logging",
    "sse_stream",
]
