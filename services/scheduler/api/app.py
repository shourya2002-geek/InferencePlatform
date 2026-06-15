"""Scheduler HTTP surface — health probes + Prometheus scrape endpoint."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from platform_common.config.settings import SchedulerSettings
from platform_common.observability import metrics_asgi_app


def create_app(settings: SchedulerSettings) -> FastAPI:
    app = FastAPI(title="Scheduler", version="0.1.0")
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "strategy": settings.strategy}

    @router.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ready"}

    app.include_router(router)
    app.mount("/metrics", metrics_asgi_app())
    return app
