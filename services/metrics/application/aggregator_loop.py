"""AggregatorLoop — periodically samples platform state into Prometheus gauges.

Runs as a background task: every ``interval`` seconds it asks the collector for a
snapshot and writes the values into gauges. Gauges (not counters) are correct
here because depth/liveness are point-in-time levels, not monotonic totals.
"""

from __future__ import annotations

import asyncio
import contextlib

from platform_common.observability import get_logger
from prometheus_client import Gauge

from services.metrics.domain.collectors import PlatformSnapshot, PlatformStateCollector

log = get_logger("metrics.aggregator")

# Platform-global gauges (distinct from per-service metrics in PlatformMetrics).
_REQUEST_DEPTH = Gauge("pip_platform_request_stream_depth", "Pending requests in ingest stream")
_BATCH_DEPTH = Gauge("pip_platform_batch_queue_depth", "Formed batches awaiting a worker")
_INFLIGHT = Gauge("pip_platform_inflight_batches", "Batches currently reserved by workers")
_WORKERS_TOTAL = Gauge("pip_platform_workers_total", "Workers with a heartbeat record")
_WORKERS_ALIVE = Gauge("pip_platform_workers_alive", "Workers with a fresh heartbeat")


class AggregatorLoop:
    def __init__(
        self, collector: PlatformStateCollector, *, interval_s: float = 2.0
    ) -> None:
        self._collector = collector
        self._interval = interval_s
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._last: PlatformSnapshot | None = None

    @property
    def last_snapshot(self) -> PlatformSnapshot | None:
        return self._last

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(Exception):
                await self._task

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                snap = await self._collector.collect()
                self._publish(snap)
                self._last = snap
            except Exception:  # noqa: BLE001 - never let the sampler die
                log.exception("metrics.collect_error")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)

    @staticmethod
    def _publish(snap: PlatformSnapshot) -> None:
        _REQUEST_DEPTH.set(snap.request_stream_depth)
        _BATCH_DEPTH.set(snap.batch_queue_depth)
        _INFLIGHT.set(snap.in_flight_batches)
        _WORKERS_TOTAL.set(snap.workers_total)
        _WORKERS_ALIVE.set(snap.workers_alive)
