"""Structured JSON logging with request correlation.

Every log line is a single JSON object so Loki/Promtail can index it without
regex parsing. ``request_id`` is carried in a contextvar, which means it also
shows up on log records emitted deep inside services without threading the id
through every call signature.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)

# Attributes LogRecord always carries; anything else was passed via `extra=`
# and is worth promoting to a top-level JSON field.
_RESERVED = frozenset(
    (
        "args asctime created exc_info exc_text filename funcName levelname levelno"
        " lineno module msecs message msg name pathname process processName"
        " relativeCreated stack_info thread threadName taskName"
    ).split()
)


def get_request_id() -> str | None:
    return request_id_var.get()


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as one line of JSON."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id

        user_id = user_id_var.get()
        if user_id:
            payload["user_id"] = user_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = repr(value)
            payload[key] = value

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(service: str) -> None:
    """Install the JSON formatter on the root logger.

    Set ``LOG_FORMAT=plain`` to get human-readable output while developing.
    """
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    plain = os.getenv("LOG_FORMAT", "json").lower() == "plain"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        if plain
        else JsonFormatter(service)
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn installs its own handlers; make them propagate to ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # These are chatty at INFO and drown out application logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
