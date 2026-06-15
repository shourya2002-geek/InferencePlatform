"""Tests for the dynamic batching engine — the size/timeout flush rules."""

from __future__ import annotations

import time

import pytest
from platform_common.schemas import InferenceRequest, Priority

from services.scheduler.domain.batcher import DynamicBatcher
from services.scheduler.domain.strategies import (
    FIFOScheduler,
    PendingItem,
    PriorityScheduler,
    build_strategy,
)


def _req(i: int, *, model="resnet", version="v2", priority=Priority.NORMAL):
    return InferenceRequest(
        request_id=f"r{i}",
        trace_id="t",
        model_name=model,
        model_version=version,
        priority=priority,
        image_ref=f"r{i}",
    )


def _item(i: int, *, arrived_ms: float | None = None, **kw) -> PendingItem:
    it = PendingItem(msg_id=f"m{i}", request=_req(i, **kw))
    if arrived_ms is not None:
        it.arrived_ms = arrived_ms
    return it


def test_flush_on_max_size():
    b = DynamicBatcher(FIFOScheduler(), max_batch_size=4, max_wait_ms=10_000)
    for i in range(4):
        b.add(_item(i))
    formed = b.collect_ready()
    assert len(formed) == 1
    assert formed[0].envelope.size == 4
    assert b.pending == 0


def test_no_flush_before_size_or_timeout():
    b = DynamicBatcher(FIFOScheduler(), max_batch_size=8, max_wait_ms=10_000)
    for i in range(3):
        b.add(_item(i))
    assert b.collect_ready() == []
    assert b.pending == 3


def test_flush_on_timeout():
    b = DynamicBatcher(FIFOScheduler(), max_batch_size=32, max_wait_ms=10)
    # Pretend these arrived 50ms ago → past the 10ms wait window.
    for i in range(2):
        b.add(_item(i, arrived_ms=time.perf_counter() * 1000 - 50))
    formed = b.collect_ready()
    assert len(formed) == 1
    assert formed[0].envelope.size == 2


def test_large_backlog_splits_into_multiple_batches():
    b = DynamicBatcher(FIFOScheduler(), max_batch_size=4, max_wait_ms=10_000)
    for i in range(10):
        b.add(_item(i))
    formed = b.collect_ready()
    # 10 items, batch=4 → two full batches of 4; remaining 2 stay (no trigger).
    assert [f.envelope.size for f in formed] == [4, 4]
    assert b.pending == 2


def test_batches_are_homogeneous_by_model():
    b = DynamicBatcher(FIFOScheduler(), max_batch_size=4, max_wait_ms=1)
    b.add(_item(1, model="resnet", version="v1", arrived_ms=0))
    b.add(_item(2, model="resnet", version="v2", arrived_ms=0))
    formed = b.collect_ready()
    keys = {(f.envelope.model_name, f.envelope.model_version) for f in formed}
    # two distinct model keys → two separate batches
    assert keys == {("resnet", "v1"), ("resnet", "v2")}


def test_priority_strategy_orders_high_first():
    strat = PriorityScheduler()
    items = [
        _item(1, priority=Priority.LOW, arrived_ms=0),
        _item(2, priority=Priority.HIGH, arrived_ms=1),
        _item(3, priority=Priority.NORMAL, arrived_ms=2),
    ]
    ordered = strat.order_items(items)
    assert [int(i.request.priority) for i in ordered] == [2, 1, 0]


@pytest.mark.parametrize("name", ["fifo", "priority", "weighted"])
def test_strategy_factory(name):
    assert build_strategy(name).name == name


def test_flush_all_drains_everything():
    b = DynamicBatcher(build_strategy("weighted"), max_batch_size=4, max_wait_ms=10_000)
    for i in range(6):
        b.add(_item(i))
    formed = b.flush_all()
    assert sum(f.envelope.size for f in formed) == 6
    assert b.pending == 0
