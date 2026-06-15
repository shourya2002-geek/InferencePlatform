"""Token-bucket rate limiter (per API key).

A token bucket gives smooth average-rate limiting *with* burst tolerance: the
bucket refills at ``rate`` tokens/sec up to ``burst`` capacity, and each request
costs one token. Bursty-but-bounded clients pass; sustained over-rate clients are
shed with 429 + ``Retry-After``.

This implementation is **in-process** (per gateway replica). That is correct and
fast for per-replica protection; for a *global* limit across replicas you'd back
the bucket with a Redis ``INCR``/Lua script. The interface here would not change
— it's a domain port, so swapping the implementation is mechanical.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(slots=True)
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketRateLimiter:
    def __init__(self, *, rate: float, burst: int) -> None:
        self._rate = rate
        self._burst = float(burst)
        self._buckets: dict[str, _Bucket] = {}

    def allow(self, key: str, *, cost: float = 1.0) -> tuple[bool, float]:
        """Try to spend ``cost`` tokens for ``key``.

        Returns ``(allowed, retry_after_seconds)``. ``retry_after`` is 0 when
        allowed, else the time until enough tokens have refilled.
        """
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=self._burst, last_refill=now)
            self._buckets[key] = bucket

        # Refill based on elapsed time.
        elapsed = now - bucket.last_refill
        bucket.tokens = min(self._burst, bucket.tokens + elapsed * self._rate)
        bucket.last_refill = now

        if bucket.tokens >= cost:
            bucket.tokens -= cost
            return True, 0.0
        deficit = cost - bucket.tokens
        retry_after = deficit / self._rate if self._rate > 0 else 1.0
        return False, retry_after
