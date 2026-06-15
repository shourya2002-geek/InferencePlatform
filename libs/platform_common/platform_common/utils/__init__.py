"""Small, dependency-free utilities used across services."""

from platform_common.utils.circuit_breaker import CircuitBreaker, CircuitState
from platform_common.utils.ids import new_batch_id, new_request_id, new_trace_id
from platform_common.utils.retry import retry_async
from platform_common.utils.timing import Stopwatch, now_ms, since_ms

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "Stopwatch",
    "new_batch_id",
    "new_request_id",
    "new_trace_id",
    "now_ms",
    "retry_async",
    "since_ms",
]
