"""Inference worker entrypoint.

Composition root: builds the backend (factory), the model registry, the executor,
the worker loop and the janitor, then serves the HTTP control surface while the
loop consumes batches in the background. This is the only place concrete classes
are wired together (Dependency Injection by hand — no magic container needed).
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI
from platform_common.config.settings import RuntimeSettings, WorkerSettings
from platform_common.messaging import create_redis, ping_redis
from platform_common.observability import (
    PlatformMetrics,
    configure_logging,
    configure_tracing,
    get_logger,
)

from services.inference_worker.api.app import create_app
from services.inference_worker.application.janitor import DeadWorkerJanitor
from services.inference_worker.application.worker_loop import WorkerLoop
from services.inference_worker.domain.catalog import ModelCatalog
from services.inference_worker.domain.executor import BatchExecutor
from services.inference_worker.domain.registry import ModelRegistry
from services.inference_worker.infrastructure.backends import build_backend

log = get_logger("worker.main")


def build() -> tuple[FastAPI, WorkerSettings]:
    settings = WorkerSettings()
    runtime = RuntimeSettings()
    configure_logging(settings.log_level, service=settings.service_name)
    configure_tracing(
        service_name=settings.service_name,
        exporter=settings.otel_traces_exporter,
        endpoint=settings.otel_exporter_otlp_endpoint,
    )
    metrics = PlatformMetrics.get()

    redis = create_redis(settings.redis_url)
    backend = build_backend(
        runtime.runtime_backend,
        device=runtime.device,
        mixed_precision=runtime.enable_mixed_precision,
        quantize=runtime.enable_quantization,
    )
    catalog = ModelCatalog(runtime.model_artifact_dir)
    registry = ModelRegistry(
        backend,
        catalog,
        device=runtime.device,
        cache_size=runtime.model_cache_size,
    )
    executor = BatchExecutor(registry, worker_id=settings.worker_id)
    worker = WorkerLoop(
        redis,
        settings=settings,
        runtime=runtime,
        registry=registry,
        executor=executor,
        metrics=metrics,
    )
    janitor = DeadWorkerJanitor(redis, self_worker_id=settings.worker_id)

    app = create_app(registry, worker_id=settings.worker_id)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await ping_redis(redis)
        await worker.start()
        await janitor.start()
        try:
            yield
        finally:
            # Graceful shutdown: stop accepting, drain in-flight, release model.
            await janitor.stop()
            await worker.stop()
            await redis.aclose()

    app.router.lifespan_context = lifespan
    return app, settings


app, _settings = build()


def main() -> None:
    uvicorn.run(
        "services.inference_worker.main:app",
        host=_settings.host,
        port=_settings.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
