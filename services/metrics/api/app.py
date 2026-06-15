"""Metrics service HTTP surface: /metrics (Prometheus) + /v1/stats (JSON)."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from platform_common.observability import metrics_asgi_app

from services.metrics.application.aggregator_loop import AggregatorLoop


def create_app(aggregator: AggregatorLoop) -> FastAPI:
    app = FastAPI(title="Metrics Service", version="0.1.0")
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/v1/stats")
    async def stats() -> dict[str, object]:
        """Human/dashboard-friendly snapshot of global platform state."""
        snap = aggregator.last_snapshot
        if snap is None:
            return {"status": "warming_up"}
        from services.metrics.domain.collectors import PlatformStateCollector

        return PlatformStateCollector.as_dict(snap)

    app.include_router(router)
    app.mount("/metrics", metrics_asgi_app())
    return app
