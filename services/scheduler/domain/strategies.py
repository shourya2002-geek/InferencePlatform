"""Scheduling strategies — the pluggable policy for *which* work runs next.

The batcher decides *when* to flush (size/timeout); the strategy decides *order*:
which model's bucket to serve first and how to order requests inside it. This is
the Strategy Pattern — all three share one interface so the scheduler is
configured with a string and never branches on policy.

    FIFO     — fair, simple: oldest request wins. No starvation, no priority.
    Priority — strict priority: HIGH always beats NORMAL beats LOW. Risk:
               low-priority starvation under sustained high-priority load.
    Weighted — weighted fair queuing across priority classes: HIGH gets more
               service but LOW still makes progress (no starvation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from platform_common.schemas import InferenceRequest, Priority
from platform_common.utils.timing import now_ms


@dataclass(slots=True)
class PendingItem:
    """A queued request plus the bookkeeping the scheduler needs."""

    msg_id: str  # Redis stream id, for XACK after dispatch
    request: InferenceRequest
    arrived_ms: float = field(default_factory=now_ms)  # monotonic, for age/wait

    @property
    def model_key(self) -> str:
        return f"{self.request.model_name}:{self.request.model_version}"


@runtime_checkable
class SchedulingStrategy(Protocol):
    name: str

    def rank_buckets(self, buckets: dict[str, list[PendingItem]]) -> list[str]:
        """Return model keys in the order their buckets should be serviced."""
        ...

    def order_items(self, items: list[PendingItem]) -> list[PendingItem]:
        """Order the items within one bucket for batch selection."""
        ...


class FIFOScheduler:
    name = "fifo"

    def rank_buckets(self, buckets: dict[str, list[PendingItem]]) -> list[str]:
        # Serve the bucket whose oldest item has waited longest.
        return sorted(
            buckets,
            key=lambda k: min(i.arrived_ms for i in buckets[k]) if buckets[k] else 0.0,
        )

    def order_items(self, items: list[PendingItem]) -> list[PendingItem]:
        return sorted(items, key=lambda i: i.arrived_ms)


class PriorityScheduler:
    name = "priority"

    def rank_buckets(self, buckets: dict[str, list[PendingItem]]) -> list[str]:
        # Bucket priority = its highest-priority waiting request; tie-break oldest.
        def score(key: str) -> tuple[int, float]:
            items = buckets[key]
            if not items:
                return (-1, 0.0)
            top = max(int(i.request.priority) for i in items)
            oldest = min(i.arrived_ms for i in items)
            return (top, -oldest)  # higher priority first, then older first

        return sorted(buckets, key=score, reverse=True)

    def order_items(self, items: list[PendingItem]) -> list[PendingItem]:
        # Highest priority first; within a priority, oldest first (fairness).
        return sorted(items, key=lambda i: (-int(i.request.priority), i.arrived_ms))


class WeightedScheduler:
    """Weighted fair queuing across priority classes.

    Each priority class gets ``weight`` service credits. We serve buckets in
    priority order but rotate the *starting* class by a credit counter so lower
    classes still get served roughly ``weight_low / sum(weights)`` of the time —
    preventing the starvation that strict priority causes.
    """

    name = "weighted"

    def __init__(self, weights: list[int]) -> None:
        # weights indexed by priority level, highest priority first.
        self._weights = weights or [1]
        self._credits: dict[int, int] = {}

    def _weight_for(self, priority: int) -> int:
        # Map priority enum value to a weight (clamp into range).
        idx = max(0, min(len(self._weights) - 1, (Priority.HIGH - priority)))
        return self._weights[idx]

    def rank_buckets(self, buckets: dict[str, list[PendingItem]]) -> list[str]:
        def score(key: str) -> float:
            items = buckets[key]
            if not items:
                return -1.0
            # weight-adjusted urgency: higher weight & older => served sooner
            top = max(int(i.request.priority) for i in items)
            oldest = min(i.arrived_ms for i in items)
            age = now_ms() - oldest
            return self._weight_for(top) * (1.0 + age)

        return sorted(buckets, key=score, reverse=True)

    def order_items(self, items: list[PendingItem]) -> list[PendingItem]:
        # Order by weight-adjusted urgency so a heavily-weighted class leads, but
        # an old low-priority item can still climb as its age grows.
        def urgency(i: PendingItem) -> float:
            age = now_ms() - i.arrived_ms
            return self._weight_for(int(i.request.priority)) * (1.0 + age)

        return sorted(items, key=urgency, reverse=True)


def build_strategy(name: str, *, weights: list[int] | None = None) -> SchedulingStrategy:
    """Factory: map a config string to a strategy instance."""
    name = name.lower()
    if name == "fifo":
        return FIFOScheduler()
    if name == "priority":
        return PriorityScheduler()
    if name == "weighted":
        return WeightedScheduler(weights or [8, 3, 1])
    raise ValueError(f"unknown scheduling strategy '{name}' (fifo|priority|weighted)")
