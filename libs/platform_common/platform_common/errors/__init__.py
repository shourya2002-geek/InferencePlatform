"""Platform exception hierarchy.

A small, explicit set of errors that map cleanly onto HTTP status codes at the
gateway boundary and onto result statuses on the data plane.
"""

from platform_common.errors.exceptions import (
    CircuitOpenError,
    ModelNotFoundError,
    PlatformError,
    QueueOverflowError,
    RateLimitedError,
    RuntimeBackendError,
    UnauthorizedError,
    UpstreamTimeoutError,
    ValidationError,
)

__all__ = [
    "CircuitOpenError",
    "ModelNotFoundError",
    "PlatformError",
    "QueueOverflowError",
    "RateLimitedError",
    "RuntimeBackendError",
    "UnauthorizedError",
    "UpstreamTimeoutError",
    "ValidationError",
]
