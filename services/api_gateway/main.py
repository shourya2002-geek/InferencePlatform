"""API Gateway entrypoint (composition root).

Wires settings → Redis → data-plane client → circuit breaker → rate limiter →
use-case → FastAPI app, and installs the tracing middleware + exception handlers.
Everything is attached to ``app.state`` so dependencies can retrieve singletons.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI
from platform_common.config.settings import GatewaySettings
from platform_common.messaging import create_redis, ping_redis
from platform_common.observability import (
    PlatformMetrics,
    configure_logging,
    configure_tracing,
)
from platform_common.utils.circuit_breaker import CircuitBreaker

from services.api_gateway.api.middleware import (
    TracingMiddleware,
    install_exception_handlers,
)
from services.api_gateway.api.routes import metrics_app, router
from services.api_gateway.application.submit_use_case import SubmitInferenceUseCase
from services.api_gateway.domain.rate_limiter import TokenBucketRateLimiter
from services.api_gateway.infrastructure.gateway_client import GatewayDataPlaneClient


def create_app() -> FastAPI:
    settings = GatewaySettings()
    configure_logging(settings.log_level, service=settings.service_name)
    configure_tracing(
        service_name=settings.service_name,
        exporter=settings.otel_traces_exporter,
        endpoint=settings.otel_exporter_otlp_endpoint,
    )
    metrics = PlatformMetrics.get()
    redis = create_redis(settings.redis_url)
    client = GatewayDataPlaneClient(redis, queue_maxlen=50_000)
    breaker = CircuitBreaker(
        fail_threshold=settings.circuit_fail_threshold,
        reset_timeout=settings.circuit_reset_seconds,
        name="data-plane",
    )
    use_case = SubmitInferenceUseCase(
        client, settings=settings, breaker=breaker, metrics=metrics
    )

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await ping_redis(redis)
        yield
        await redis.aclose()

    app = FastAPI(
        title="PyTorch Inference Platform — API Gateway",
        version="0.1.0",
        lifespan=lifespan,
    )
    # DI singletons.
    app.state.settings = settings
    app.state.client = client
    app.state.use_case = use_case
    app.state.rate_limiter = TokenBucketRateLimiter(
        rate=settings.rate_limit_rps, burst=settings.rate_limit_burst
    )
    app.state.breaker = breaker

    app.add_middleware(TracingMiddleware)
    install_exception_handlers(app)
    app.include_router(router)
    app.mount("/metrics", metrics_app())
    return app


app = create_app()


def main() -> None:
    settings = GatewaySettings()
    uvicorn.run(
        "services.api_gateway.main:app",
        host=settings.host,
        port=settings.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
