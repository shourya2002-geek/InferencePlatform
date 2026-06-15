"""SchedulerLoop — drains the request stream, batches, dispatches.

The control loop, once per tick:

1. ``XREADGROUP`` a slice of pending requests (block briefly so we never sleep
   longer than the batch timer's resolution).
2. Drop any request already past its deadline (load-shedding — don't spend a GPU
   slot on work whose answer is already useless).
3. Feed survivors into the :class:`DynamicBatcher`.
4. ``collect_ready`` → dispatch each formed batch onto the worker queue, then
   ``XACK`` its stream ids (ack only *after* durable dispatch = at-least-once).

Multiple scheduler replicas can run: the Redis consumer group load-balances
stream entries across them, so this scales horizontally and tolerates a replica
dying (unacked entries are reclaimed).
"""

from __future__ import annotations

import asyncio
import contextlib
import time

import redis.asyncio as aioredis
from platform_common.config.settings import SchedulerSettings
from platform_common.messaging import BatchQueue, RequestStream, ResultBus
from platform_common.observability import PlatformMetrics, get_logger
from platform_common.schemas import InferenceResult, RequestStatus

from services.scheduler.domain.batcher import DynamicBatcher, FormedBatch
from services.scheduler.domain.strategies import PendingItem, build_strategy

log = get_logger("scheduler")


class SchedulerLoop:
    def __init__(
        self,
        redis: aioredis.Redis,
        *,
        settings: SchedulerSettings,
        metrics: PlatformMetrics,
        consumer_name: str,
    ) -> None:
        self._redis = redis
        self._settings = settings
        self._metrics = metrics
        self._consumer = consumer_name
        self._stream = RequestStream(redis, maxlen=settings.queue_maxlen)
        self._batch_q = BatchQueue(redis)
        self._results = ResultBus(redis)
        strategy = build_strategy(settings.strategy, weights=settings.class_weights)
        self._batcher = DynamicBatcher(
            strategy,
            max_batch_size=settings.max_batch_size,
            max_wait_ms=settings.max_wait_ms,
        )
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        # Block window: never longer than the batch timer, so timeouts fire on time.
        self._block_ms = max(1, settings.max_wait_ms // 2)
        # Fallback yield when the broker doesn't actually honor `block` (e.g.
        # fakeredis in tests, or a broker returning early): prevents a hot spin
        # that would starve the event loop. Kept well under the batch timer so it
        # never adds meaningful latency.
        self._idle_sleep_s = max(0.001, settings.max_wait_ms / 4 / 1000.0)

    async def start(self) -> None:
        await self._stream.ensure_group()
        self._task = asyncio.create_task(self._run())
        log.info(
            "scheduler.started",
            strategy=self._settings.strategy,
            max_batch=self._settings.max_batch_size,
            max_wait_ms=self._settings.max_wait_ms,
            consumer=self._consumer,
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            with contextlib.suppress(Exception):
                await self._task
        # Drain anything still buffered so no request is silently lost.
        leftovers = self._batcher.flush_all()
        for fb in leftovers:
            await self._dispatch(fb)
        log.info("scheduler.stopped")

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - loop must survive transient errors
                log.exception("scheduler.tick_error")
                await asyncio.sleep(0.05)

    async def _tick(self) -> None:
        # 1. pull pending requests
        entries = await self._stream.consume(
            self._consumer,
            count=self._settings.max_batch_size,
            block_ms=self._block_ms,
        )
        # Yield real time whenever the stream had nothing new, so we never
        # busy-spin — whether idle, or holding items that are waiting out the
        # batch timer. The slice is << max_wait_ms so flush timing is unaffected.
        if not entries:
            await asyncio.sleep(self._idle_sleep_s)
        # 2. shed expired, 3. feed batcher
        for msg_id, req in entries:
            if req.is_expired():
                await self._reject(msg_id, req, "deadline exceeded before scheduling")
                continue
            self._batcher.add(PendingItem(msg_id=msg_id, request=req))

        # 4. form + dispatch ready batches
        for fb in self._batcher.collect_ready():
            await self._dispatch(fb)

        # publish queue-depth gauges for the bottleneck dashboard
        self._metrics.queue_depth.labels(
            self._settings.service_name, "pending_in_batcher"
        ).set(self._batcher.pending)
        self._metrics.queue_depth.labels(
            self._settings.service_name, "request_stream"
        ).set(await self._stream.depth())

    async def _dispatch(self, fb: FormedBatch) -> None:
        await self._batch_q.dispatch(fb.envelope)
        await self._stream.ack(*fb.msg_ids)  # ack only after durable dispatch
        self._metrics.batch_size.labels(
            self._settings.service_name, fb.envelope.model_name
        ).observe(fb.envelope.size)
        self._metrics.stage_latency.labels(
            self._settings.service_name, "batch_wait"
        ).observe(fb.envelope.batch_wait_ms)
        log.info(
            "scheduler.dispatched",
            batch_id=fb.envelope.batch_id,
            size=fb.envelope.size,
            model=f"{fb.envelope.model_name}:{fb.envelope.model_version}",
            wait_ms=round(fb.envelope.batch_wait_ms, 2),
        )

    async def _reject(self, msg_id: str, req, reason: str) -> None:  # type: ignore[no-untyped-def]
        result = InferenceResult.failure(req, RequestStatus.REJECTED, reason)
        await self._results.publish(result)
        await self._stream.ack(msg_id)
        self._metrics.request_count.labels(
            self._settings.service_name, req.model_name, RequestStatus.REJECTED.value
        ).inc()


def make_consumer_name() -> str:
    import socket

    return f"sched-{socket.gethostname()}-{int(time.time())}"
