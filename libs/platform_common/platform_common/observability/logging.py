"""Structured JSON logging via structlog.

JSON logs are non-negotiable for a distributed system: they let you grep by
``trace_id`` across services in Loki/CloudWatch. ``bind_trace`` attaches the
current request's trace id to the context so every subsequent log line carries
it automatically.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", *, service: str = "service") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_trace(trace_id: str, **extra: str) -> None:
    """Bind a trace id (and any extra fields) to the logging context."""
    structlog.contextvars.bind_contextvars(trace_id=trace_id, **extra)


def clear_trace() -> None:
    structlog.contextvars.clear_contextvars()
