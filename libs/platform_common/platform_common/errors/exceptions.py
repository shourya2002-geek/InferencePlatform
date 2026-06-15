"""Concrete platform exceptions.

Each carries an ``http_status`` so the gateway's exception handler can translate
domain failures into responses without a giant if/elif ladder.
"""

from __future__ import annotations


class PlatformError(Exception):
    """Base class for all platform-specific failures."""

    http_status: int = 500
    code: str = "platform_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class ValidationError(PlatformError):
    http_status = 422
    code = "validation_error"


class UnauthorizedError(PlatformError):
    http_status = 401
    code = "unauthorized"


class RateLimitedError(PlatformError):
    http_status = 429
    code = "rate_limited"

    def __init__(self, message: str, *, retry_after: float = 1.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class QueueOverflowError(PlatformError):
    """Raised when the scheduler queue is at capacity (backpressure)."""

    http_status = 503
    code = "queue_overflow"


class CircuitOpenError(PlatformError):
    """Raised by the gateway when the downstream circuit breaker is open."""

    http_status = 503
    code = "circuit_open"


class UpstreamTimeoutError(PlatformError):
    """The data plane did not return a result within the gateway's budget."""

    http_status = 504
    code = "upstream_timeout"


class ModelNotFoundError(PlatformError):
    http_status = 404
    code = "model_not_found"


class RuntimeBackendError(PlatformError):
    """Inference runtime failed (bad tensor, OOM, backend crash)."""

    http_status = 500
    code = "runtime_error"
