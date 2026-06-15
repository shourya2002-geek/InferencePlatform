"""End-to-end pipeline test: gateway -> scheduler -> worker -> gateway.

Runs the real SchedulerLoop and WorkerLoop (stub backend) against fakeredis and
drives a request through the SubmitInferenceUseCase, asserting a correct result
comes back with a populated latency breakdown. This exercises streams, the
reliable batch queue, and the result mailbox together.
"""

from __future__ import annotations

import pytest
from platform_common.config.settings import (
    GatewaySettings,
    RuntimeSettings,
    SchedulerSettings,
    WorkerSettings,
)
from platform_common.observability import PlatformMetrics
from platform_common.schemas import Priority
from platform_common.utils.circuit_breaker import CircuitBreaker

from services.api_gateway.application.submit_use_case import SubmitInferenceUseCase
from services.api_gateway.infrastructure.gateway_client import GatewayDataPlaneClient
from services.inference_worker.application.worker_loop import WorkerLoop
from services.inference_worker.domain.catalog import ModelCatalog
from services.inference_worker.domain.executor import BatchExecutor
from services.inference_worker.domain.registry import ModelRegistry
from services.inference_worker.infrastructure.backends.stub_backend import StubBackend
from services.scheduler.application.scheduler_loop import SchedulerLoop


@pytest.mark.asyncio
async def test_full_pipeline(fake_redis, sample_image_bytes):
    metrics = PlatformMetrics.get()

    # --- scheduler (tiny wait window so the test is fast) ---
    sched_settings = SchedulerSettings(strategy="priority", max_batch_size=8, max_wait_ms=5)
    scheduler = SchedulerLoop(
        fake_redis, settings=sched_settings, metrics=metrics, consumer_name="test-sched"
    )

    # --- worker (stub backend) ---
    worker_settings = WorkerSettings(worker_id="test-worker", concurrency=1)
    runtime = RuntimeSettings(runtime_backend="stub", default_model="resnet",
                              default_model_version="v2")
    registry = ModelRegistry(StubBackend(), ModelCatalog(), cache_size=2)
    executor = BatchExecutor(registry, worker_id=worker_settings.worker_id)
    worker = WorkerLoop(
        fake_redis, settings=worker_settings, runtime=runtime,
        registry=registry, executor=executor, metrics=metrics,
    )

    # --- gateway use-case ---
    gw_settings = GatewaySettings(request_timeout_ms=3000)
    client = GatewayDataPlaneClient(fake_redis, queue_maxlen=10_000)
    use_case = SubmitInferenceUseCase(
        client, settings=gw_settings,
        breaker=CircuitBreaker(name="t"), metrics=metrics,
    )

    await scheduler.start()
    await worker.start()
    try:
        result = await use_case.execute(
            image=sample_image_bytes,
            model_name="resnet",
            model_version="v2",
            priority=Priority.HIGH,
            top_k=5,
            trace_id="trace-int",
        )
    finally:
        await worker.stop()
        await scheduler.stop()

    assert result.status.value == "ok"
    assert result.trace_id == "trace-int"
    assert len(result.predictions) == 5
    assert result.worker_id == "test-worker"
    assert result.total_time_ms > 0


@pytest.mark.asyncio
async def test_timeout_when_no_worker(fake_redis, sample_image_bytes):
    """With no worker running, the gateway must time out (504), not hang."""
    from platform_common.errors import UpstreamTimeoutError

    metrics = PlatformMetrics.get()
    sched_settings = SchedulerSettings(max_batch_size=8, max_wait_ms=5)
    scheduler = SchedulerLoop(
        fake_redis, settings=sched_settings, metrics=metrics, consumer_name="t2"
    )
    gw_settings = GatewaySettings(request_timeout_ms=300)
    client = GatewayDataPlaneClient(fake_redis, queue_maxlen=10_000)
    use_case = SubmitInferenceUseCase(
        client, settings=gw_settings,
        breaker=CircuitBreaker(name="t"), metrics=metrics,
    )
    await scheduler.start()
    try:
        with pytest.raises(UpstreamTimeoutError):
            await use_case.execute(
                image=sample_image_bytes, model_name="resnet", model_version="v2",
                priority=Priority.NORMAL, top_k=5, trace_id="trace-timeout",
            )
    finally:
        await scheduler.stop()
