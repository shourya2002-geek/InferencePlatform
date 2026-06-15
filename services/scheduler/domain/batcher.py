"""DynamicBatcher — the core latency/throughput trade, made explicit.

Pending requests are bucketed by ``model_key`` (a batch must be homogeneous: one
forward pass = one model). The batcher flushes a bucket when **either**:

* it reaches ``max_batch_size`` (throughput trigger — fill the accelerator), or
* its oldest request has waited ``max_wait_ms`` (latency trigger — bound the tail).

That single rule is the whole game:

* Larger ``max_batch_size`` → higher throughput, higher tail latency.
* Larger ``max_wait_ms``     → bigger average batches under light load, but every
  request pays up to that wait.

The strategy (FIFO/Priority/Weighted) decides ordering; the batcher owns timing.
This class is pure and synchronous so it is trivially unit-testable and
benchmarkable without Redis.
"""

from __future__ import annotations

from dataclasses import dataclass

from platform_common.schemas import BatchEnvelope
from platform_common.utils.ids import new_batch_id
from platform_common.utils.timing import now_ms

from services.scheduler.domain.strategies import PendingItem, SchedulingStrategy


@dataclass(slots=True)
class FormedBatch:
    envelope: BatchEnvelope
    msg_ids: list[str]  # stream ids to XACK once durably dispatched


class DynamicBatcher:
    def __init__(
        self,
        strategy: SchedulingStrategy,
        *,
        max_batch_size: int,
        max_wait_ms: float,
    ) -> None:
        self._strategy = strategy
        self._max_batch = max_batch_size
        self._max_wait = max_wait_ms
        self._buckets: dict[str, list[PendingItem]] = {}
        self._size = 0

    @property
    def pending(self) -> int:
        return self._size

    def add(self, item: PendingItem) -> None:
        self._buckets.setdefault(item.model_key, []).append(item)
        self._size += 1

    def _bucket_age_ms(self, items: list[PendingItem], now: float) -> float:
        if not items:
            return 0.0
        return now - min(i.arrived_ms for i in items)

    def collect_ready(self, now: float | None = None) -> list[FormedBatch]:
        """Form and return every batch that should flush right now.

        Called on each scheduler tick. May return multiple batches (several
        buckets ready, or one bucket holding more than ``max_batch_size``).
        """
        now = now if now is not None else now_ms()
        formed: list[FormedBatch] = []

        for key in self._strategy.rank_buckets(self._buckets):
            items = self._buckets.get(key)
            if not items:
                continue
            # Keep draining this bucket while it satisfies a flush trigger.
            while items:
                size_trigger = len(items) >= self._max_batch
                time_trigger = self._bucket_age_ms(items, now) >= self._max_wait
                if not (size_trigger or time_trigger):
                    break
                formed.append(self._flush_one(key, items, now))
            if not items:
                del self._buckets[key]

        return formed

    def flush_all(self, now: float | None = None) -> list[FormedBatch]:
        """Force-flush everything (used on graceful shutdown to drain)."""
        now = now if now is not None else now_ms()
        formed: list[FormedBatch] = []
        for key in list(self._buckets):
            items = self._buckets[key]
            while items:
                formed.append(self._flush_one(key, items, now))
            del self._buckets[key]
        return formed

    def _flush_one(
        self, key: str, items: list[PendingItem], now: float
    ) -> FormedBatch:
        ordered = self._strategy.order_items(items)
        chosen = ordered[: self._max_batch]
        chosen_ids = {id(i) for i in chosen}
        # Remove chosen items from the live bucket (identity-based).
        remaining = [i for i in items if id(i) not in chosen_ids]
        items[:] = remaining
        self._size -= len(chosen)

        oldest = min(i.arrived_ms for i in chosen)
        first = chosen[0].request
        envelope = BatchEnvelope(
            batch_id=new_batch_id(),
            model_name=first.model_name,
            model_version=first.model_version,
            requests=[i.request for i in chosen],
            batch_wait_ms=max(0.0, now - oldest),
        )
        return FormedBatch(envelope=envelope, msg_ids=[i.msg_id for i in chosen])
