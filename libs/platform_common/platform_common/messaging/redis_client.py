"""Async Redis client factory.

We standardize on ``redis.asyncio`` everywhere. ``decode_responses=False`` keeps
values as bytes so the same connection can carry both JSON text and raw image
payloads without surprising re-encoding.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from platform_common.utils.retry import retry_async


def create_redis(url: str, *, max_connections: int = 64) -> aioredis.Redis:
    """Create a pooled async Redis client.

    A pool (not a single connection) is essential: the gateway issues many
    concurrent BLPOP waits, and a shared single connection would serialize them.
    """
    pool = aioredis.ConnectionPool.from_url(
        url,
        max_connections=max_connections,
        decode_responses=False,
        health_check_interval=30,
    )
    return aioredis.Redis(connection_pool=pool)


async def ping_redis(client: aioredis.Redis) -> bool:
    """Ping with retry/backoff — used by readiness probes at startup."""

    async def _ping() -> bool:
        return bool(await client.ping())

    return await retry_async(_ping, attempts=10, base_delay=0.2, max_delay=2.0)
