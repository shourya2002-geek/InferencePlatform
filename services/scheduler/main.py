"""Scheduler entrypoint (composition root)."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI
from platform_common.config.settings import SchedulerSettings
from platform_common.messaging import create_redis, ping_redis
from platform_common.observability import (
    PlatformMetrics,
    configure_logging,
    configure_tracing,
)

from services.scheduler.api.app import create_app
from services.scheduler.application.scheduler_loop import (
    SchedulerLoop,
    make_consumer_name,
)


def build() -> tuple[FastAPI, SchedulerSettings]:
    settings = SchedulerSettings()
    configure_logging(settings.log_level, service=settings.service_name)
    configure_tracing(
        service_name=settings.service_name,
        exporter=settings.otel_traces_exporter,
        endpoint=settings.otel_exporter_otlp_endpoint,
    )
    metrics = PlatformMetrics.get()
    redis = create_redis(settings.redis_url)
    loop = SchedulerLoop(
        redis,
        settings=settings,
        metrics=metrics,
        consumer_name=make_consumer_name(),
    )
    app = create_app(settings)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await ping_redis(redis)
        await loop.start()
        try:
            yield
        finally:
            await loop.stop()
            await redis.aclose()

    app.router.lifespan_context = lifespan
    return app, settings


app, _settings = build()


def main() -> None:
    uvicorn.run(
        "services.scheduler.main:app",
        host=_settings.host,
        port=_settings.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
