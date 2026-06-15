"""Platform-level state collectors.

Individual services export their *own* counters/histograms (latency, throughput)
which Prometheus scrapes directly. This service fills the gap: **global** state
that no single service owns — queue depths, worker liveness, and (where
available) GPU utilization. It reads that state from Redis and re-exports it as
Prometheus gauges plus a JSON snapshot for humans/dashboards.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import redis.asyncio as aioredis
from platform_common.messaging import Keys

_WORKER_STALE_S = 10.0


@dataclass(slots=True)
class PlatformSnapshot:
    request_stream_depth: int
    batch_queue_depth: int
    in_flight_batches: int
    workers_total: int
    workers_alive: int
    captured_at: float


class PlatformStateCollector:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def collect(self) -> PlatformSnapshot:
        request_depth = int(await self._redis.xlen(Keys.REQUEST_STREAM))
        batch_depth = int(await self._redis.llen(Keys.BATCH_QUEUE))

        heartbeats = await self._redis.hgetall(Keys.WORKER_HEARTBEAT)
        now = time.time()
        workers_total = len(heartbeats)
        workers_alive = 0
        in_flight = 0
        for raw_id, raw_ts in heartbeats.items():
            wid = raw_id.decode() if isinstance(raw_id, bytes) else raw_id
            try:
                last = float(raw_ts)
            except (TypeError, ValueError):
                last = 0.0
            if now - last < _WORKER_STALE_S:
                workers_alive += 1
            in_flight += int(await self._redis.llen(Keys.batch_processing(wid)))

        return PlatformSnapshot(
            request_stream_depth=request_depth,
            batch_queue_depth=batch_depth,
            in_flight_batches=in_flight,
            workers_total=workers_total,
            workers_alive=workers_alive,
            captured_at=now,
        )

    @staticmethod
    def as_dict(snapshot: PlatformSnapshot) -> dict[str, object]:
        return asdict(snapshot)
