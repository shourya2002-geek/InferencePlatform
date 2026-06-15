"""Worker HTTP control surface.

The worker is primarily a queue consumer, but it also exposes a thin FastAPI app
for health probes, Prometheus scraping, and *model management* — listing
resident models and triggering a hot-reload/promotion. Keeping these as HTTP
endpoints lets ops and CI drive zero-downtime model rollouts.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException
from platform_common.errors import ModelNotFoundError
from platform_common.observability import metrics_asgi_app

from services.inference_worker.domain.registry import ModelRegistry


def build_router(registry: ModelRegistry, *, worker_id: str) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "worker_id": worker_id}

    @router.get("/readyz")
    async def readyz() -> dict[str, object]:
        return {"status": "ready", "resident_models": registry.resident()}

    @router.get("/v1/models")
    async def list_models() -> dict[str, object]:
        return {"resident": registry.resident()}

    @router.post("/v1/models/{name}/promote")
    async def promote(name: str, version: str) -> dict[str, str]:
        """Hot-reload: warm `version`, then make it 'latest' (no downtime)."""
        try:
            await registry.promote(name, version)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=exc.message) from exc
        return {"promoted": f"{name}:{version}"}

    return router


def create_app(registry: ModelRegistry, *, worker_id: str) -> FastAPI:
    app = FastAPI(title="Inference Worker", version="0.1.0")
    app.include_router(build_router(registry, worker_id=worker_id))
    app.mount("/metrics", metrics_asgi_app())
    return app
