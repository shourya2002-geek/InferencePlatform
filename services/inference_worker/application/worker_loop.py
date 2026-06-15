"""WorkerLoop — the data-plane consumer.

Pulls reserved batches off the queue, executes them, and publishes results.
Concerns it owns:

* **Concurrency** — runs ``concurrency`` parallel serve-slots so a worker can
  overlap I/O (image fetch) with compute. Each slot reserves one batch at a time.
* **Reliability** — uses the reliable-queue reserve/complete protocol; on startup
  it recovers its own orphaned in-flight batches (crash recovery).
* **Liveness** — writes a heartbeat so a janitor can recover *other* dead
  workers' batches.
* **Timeouts** — a batch that exceeds ``batch_timeout_ms`` is failed (its results
  marked TIMEOUT) rather than wedging a slot forever.
* **Observability** — records inference time, batch size, queue depth, and a
  per-worker utilization gauge.
"""

from __future__ import annotations

import asyncio
import contextlib
import time

import redis.asyncio as aioredis
from platform_common.config.settings import RuntimeSettings, WorkerSettings
from platform_common.messaging import BatchQueue, ImageStore, Keys, ResultBus
from platform_common.observability import PlatformMetrics, bind_trace, get_logger
from platform_common.schemas import BatchEnvelope, InferenceResult, RequestStatus

from services.inference_worker.domain.executor import BatchExecutor
from services.inference_worker.domain.registry import ModelRegistry

log = get_logger("worker")
_HEARTBEAT_INTERVAL_S = 2.0


class WorkerLoop:
    def __init__(
        self,
        redis: aioredis.Redis,
        *,
        settings: WorkerSettings,
        runtime: RuntimeSettings,
        registry: ModelRegistry,
        executor: BatchExecutor,
        metrics: PlatformMetrics,
    ) -> None:
        self._redis = redis
        self._settings = settings
        self._runtime = runtime
        self._registry = registry
        self._executor = executor
        self._metrics = metrics
        self._batch_q = BatchQueue(redis)
        self._images = ImageStore(redis)
        self._results = ResultBus(redis)
        self._stop = asyncio.Event()
        self._busy_slots = 0
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        wid = self._settings.worker_id
        # 1. Recover any batches we left in-flight when we last died.
        recovered = await self._batch_q.recover_orphans(wid)
        if recovered:
            log.info("worker.recovered_orphans", worker_id=wid, count=recovered)
        # 2. Warm-load the default model so the first request isn't cold.
        await self._registry.preload(
            self._runtime.default_model, self._runtime.default_model_version
        )
        # 3. Launch heartbeat + N serve slots.
        self._tasks.append(asyncio.create_task(self._heartbeat_loop()))
        for slot in range(self._settings.concurrency):
            self._tasks.append(asyncio.create_task(self._serve_loop(slot)))
        log.info(
            "worker.started",
            worker_id=wid,
            concurrency=self._settings.concurrency,
            backend=self._runtime.runtime_backend,
            device=self._runtime.device,
        )

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._redis.hdel(Keys.WORKER_HEARTBEAT, self._settings.worker_id)
        log.info("worker.stopped", worker_id=self._settings.worker_id)

    async def _heartbeat_loop(self) -> None:
        wid = self._settings.worker_id
        while not self._stop.is_set():
            await self._redis.hset(Keys.WORKER_HEARTBEAT, wid, str(time.time()))
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=_HEARTBEAT_INTERVAL_S)

    async def _serve_loop(self, slot: int) -> None:
        wid = self._settings.worker_id
        while not self._stop.is_set():
            try:
                batch = await self._batch_q.reserve(wid, block_s=1.0)
                if batch is None:
                    # Guard against brokers that don't honor BLMOVE's block
                    # (e.g. fakeredis): a tiny yield prevents a hot spin. On real
                    # Redis the blmove above already blocked, so this is a no-op-ish.
                    await asyncio.sleep(0.002)
                    continue
                await self._process(batch)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - a slot must never die silently
                log.exception("worker.slot_error", worker_id=wid, slot=slot)
                await asyncio.sleep(0.1)

    async def _process(self, batch: BatchEnvelope) -> None:
        wid = self._settings.worker_id
        self._busy_slots += 1
        self._publish_utilization()
        bind_trace(batch.requests[0].trace_id if batch.requests else "", worker=wid)
        try:
            images = await self._fetch_images(batch)
            timeout_s = self._settings.batch_timeout_ms / 1000.0
            try:
                results = await asyncio.wait_for(
                    self._executor.execute(batch, images), timeout=timeout_s
                )
            except TimeoutError:
                results = [
                    InferenceResult.failure(
                        r, RequestStatus.TIMEOUT, "batch execution timed out"
                    )
                    for r in batch.requests
                ]
                log.warning("worker.batch_timeout", batch_id=batch.batch_id)

            await self._publish_results(batch, results)
            await self._batch_q.complete(wid, batch)
        finally:
            self._busy_slots -= 1
            self._publish_utilization()
            await self._cleanup_images(batch)

    async def _fetch_images(self, batch: BatchEnvelope) -> dict[str, bytes | None]:
        keys = [Keys.image(r.request_id) for r in batch.requests]
        values = await self._redis.mget(keys)
        return {r.request_id: v for r, v in zip(batch.requests, values, strict=True)}

    async def _publish_results(
        self, batch: BatchEnvelope, results: list[InferenceResult]
    ) -> None:
        ok = 0
        for res in results:
            await self._results.publish(res)
            status = res.status.value
            self._metrics.request_count.labels(
                self._settings.service_name, res.model_name, status
            ).inc()
            if res.status is RequestStatus.OK:
                ok += 1
                self._metrics.inference_time.labels(
                    self._settings.service_name, res.model_name, res.model_version or "?"
                ).observe(res.inference_time_ms)
        self._metrics.batch_size.labels(
            self._settings.service_name, batch.model_name
        ).observe(batch.size)
        qd = await self._batch_q.depth()
        self._metrics.queue_depth.labels(self._settings.service_name, "batch_queue").set(qd)
        log.info(
            "worker.batch_done",
            batch_id=batch.batch_id,
            size=batch.size,
            ok=ok,
            model=f"{batch.model_name}:{batch.model_version}",
        )

    async def _cleanup_images(self, batch: BatchEnvelope) -> None:
        with contextlib.suppress(Exception):
            await self._redis.delete(*[Keys.image(r.request_id) for r in batch.requests])

    def _publish_utilization(self) -> None:
        util = self._busy_slots / max(1, self._settings.concurrency)
        self._metrics.worker_utilization.labels(
            self._settings.service_name, self._settings.worker_id
        ).set(util)
