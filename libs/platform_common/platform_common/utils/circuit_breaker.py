"""A minimal three-state circuit breaker.

States follow the classic Nygard pattern:

    CLOSED   -> normal operation; failures are counted.
    OPEN     -> calls are rejected immediately for ``reset_timeout`` seconds.
    HALF_OPEN-> a single trial call is allowed; success closes, failure re-opens.

The breaker protects the gateway from hammering a dead data plane: instead of
queueing thousands of doomed requests (which only makes recovery slower), it
fails fast and sheds load until the downstream looks healthy again.
"""

from __future__ import annotations

import time
from enum import StrEnum

from platform_common.errors import CircuitOpenError


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        *,
        fail_threshold: int = 20,
        reset_timeout: float = 10.0,
        name: str = "default",
    ) -> None:
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.name = name
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> CircuitState:
        self._maybe_half_open()
        return self._state

    def _maybe_half_open(self) -> None:
        if (
            self._state is CircuitState.OPEN
            and time.monotonic() - self._opened_at >= self.reset_timeout
        ):
            self._state = CircuitState.HALF_OPEN

    def allow(self) -> None:
        """Raise :class:`CircuitOpenError` if calls are currently blocked."""
        if self.state is CircuitState.OPEN:
            raise CircuitOpenError(
                f"circuit '{self.name}' is open; shedding load"
            )

    def record_success(self) -> None:
        self._failures = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if (
            self._state is CircuitState.HALF_OPEN
            or self._failures >= self.fail_threshold
        ):
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
