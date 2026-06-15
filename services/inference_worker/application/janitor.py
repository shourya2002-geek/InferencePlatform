"""DeadWorkerJanitor — recovers batches stranded by crashed workers.

Each worker writes a heartbeat timestamp. If a worker's heartbeat goes stale
(it crashed or was OOM-killed), any surviving worker's janitor moves that
worker's in-flight batches back onto the queue so they get re-served. This is
the cluster-level half of crash recovery (the worker also recovers its *own*
orphans on restart).

Idempotent and safe to run on every worker: ``recover_orphans`` is a no-op if the
processing list is already empty, and the heartbeat is deleted after recovery so
only one janitor acts per dead worker.
"""

from __future__ import annotations

import asyncio
import contextlib
import time

import redis.asyncio as aioredis
from platform_common.messaging import BatchQueue, Keys
from platform_common.observability import get_logger

log = get_logger("janitor")


class DeadWorkerJanitor:
    def __init__(
        self,
        redis: aioredis.Redis,
        *,
        stale_after_s: float = 10.0,
        scan_interval_s: float = 5.0,
        self_worker_id: str = "",
    ) -> None:
        self._redis = redis
        self._batch_q = BatchQueue(redis)
        self._stale_after_s = stale_after_s
        self._scan_interval_s = scan_interval_s
        self._self_id = self_worker_id
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(Exception):
                await self._task

    async def _loop(self) -> None:
        while not self._stop.is_set():
            with contextlib.suppress(Exception):
                await self._scan_once()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self._scan_interval_s)

    async def _scan_once(self) -> None:
        now = time.time()
        heartbeats = await self._redis.hgetall(Keys.WORKER_HEARTBEAT)
        for raw_id, raw_ts in heartbeats.items():
            wid = raw_id.decode() if isinstance(raw_id, bytes) else raw_id
            if wid == self._self_id:
                continue
            try:
                last = float(raw_ts)
            except (TypeError, ValueError):
                last = 0.0
            if now - last < self._stale_after_s:
                continue
            recovered = await self._batch_q.recover_orphans(wid)
            await self._redis.hdel(Keys.WORKER_HEARTBEAT, wid)
            if recovered:
                log.warning(
                    "janitor.recovered_dead_worker", dead_worker=wid, batches=recovered
                )
