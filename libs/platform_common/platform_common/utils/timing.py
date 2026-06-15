"""Monotonic timing helpers.

Always measure *durations* with ``time.perf_counter()`` (monotonic, high
resolution) — never with wall-clock ``time.time()``, which can jump backward on
NTP corrections. Wall-clock is only used for cross-process timestamps in the
schemas.
"""

from __future__ import annotations

import time
from types import TracebackType


def now_ms() -> float:
    """Monotonic clock reading in milliseconds."""
    return time.perf_counter() * 1000.0


def since_ms(start_ms: float) -> float:
    """Milliseconds elapsed since a previous :func:`now_ms` reading."""
    return now_ms() - start_ms


class Stopwatch:
    """Context manager that records elapsed milliseconds.

    >>> with Stopwatch() as sw:
    ...     do_work()
    >>> sw.elapsed_ms
    """

    __slots__ = ("_start", "elapsed_ms")

    def __init__(self) -> None:
        self._start = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self) -> Stopwatch:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0
