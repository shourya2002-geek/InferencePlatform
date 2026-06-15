"""Shared kernel for the PyTorch Inference Platform.

This package is intentionally framework-light. It contains the contracts and
cross-cutting concerns that every service depends on:

* ``schemas``       — the wire/Redis message contracts (Pydantic v2).
* ``config``        — typed settings loaded from the environment.
* ``messaging``     — Redis client + queue key conventions.
* ``observability`` — logging, Prometheus metrics, OpenTelemetry tracing.
* ``errors``        — the platform exception hierarchy.
* ``utils``         — ids, timing, circuit breaker, retry helpers.
"""

__version__ = "0.1.0"
