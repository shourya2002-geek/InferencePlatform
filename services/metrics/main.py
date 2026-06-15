"""Metrics service entrypoint (composition root)."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI
from platform_common.config.settings import MetricsSettings
from platform_common.messaging import create_redis, ping_redis
from platform_common.observability import configure_logging

from services.metrics.api.app import create_app
from services.metrics.application.aggregator_loop import AggregatorLoop
from services.metrics.domain.collectors import PlatformStateCollector


def build() -> tuple[FastAPI, MetricsSettings]:
    settings = MetricsSettings()
    configure_logging(settings.log_level, service=settings.service_name)
    redis = create_redis(settings.redis_url)
    collector = PlatformStateCollector(redis)
    aggregator = AggregatorLoop(collector, interval_s=2.0)
    app = create_app(aggregator)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await ping_redis(redis)
        await aggregator.start()
        try:
            yield
        finally:
            await aggregator.stop()
            await redis.aclose()

    app.router.lifespan_context = lifespan
    return app, settings


app, _settings = build()


def main() -> None:
    uvicorn.run(
        "services.metrics.main:app",
        host=_settings.host,
        port=_settings.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
