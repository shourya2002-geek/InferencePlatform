"""Async retry with exponential backoff + full jitter.

Used by services to reconnect to Redis and by the worker to retry transient
runtime failures. Jitter prevents the thundering-herd reconnect storm that
happens when every replica retries on the same schedule after an outage.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable


async def retry_async[T](
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 5.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            return await fn()
        except retry_on as exc:  # noqa: PERF203 - retry loop is the point
            last_exc = exc
            if attempt == attempts - 1:
                break
            backoff = min(max_delay, base_delay * (2**attempt))
            await asyncio.sleep(random.uniform(0, backoff))  # full jitter
    assert last_exc is not None
    raise last_exc
