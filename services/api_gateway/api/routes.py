"""Gateway HTTP routes — thin transport, zero business logic.

The route's only jobs: parse/validate the HTTP request, delegate to the
use-case, and shape the response DTO. All policy (auth, rate limit) is injected
via dependencies; all orchestration lives in the application layer.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from platform_common.config.settings import GatewaySettings
from platform_common.errors import ValidationError
from platform_common.observability import metrics_asgi_app
from platform_common.schemas import Priority
from platform_common.utils.images import validate_image_bytes

from services.api_gateway.api.dependencies import (
    enforce_rate_limit,
    get_settings,
    get_use_case,
)
from services.api_gateway.api.schemas import ClassifyResponse, LatencyBreakdown
from services.api_gateway.application.submit_use_case import SubmitInferenceUseCase

router = APIRouter()


@router.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", tags=["health"])
async def readyz(request: Request) -> dict[str, object]:
    """Readiness: confirm we can see the request stream (Redis reachable)."""
    client = request.app.state.client
    depth = await client.request_stream_depth()
    return {"status": "ready", "request_stream_depth": depth}


@router.post(
    "/v1/classify",
    response_model=ClassifyResponse,
    tags=["inference"],
    summary="Classify an uploaded image",
)
async def classify(
    request: Request,
    _api_key: Annotated[str, Depends(enforce_rate_limit)],
    use_case: Annotated[SubmitInferenceUseCase, Depends(get_use_case)],
    settings: Annotated[GatewaySettings, Depends(get_settings)],
    file: Annotated[UploadFile, File(description="image to classify")] = ...,
    model: Annotated[str, Form()] = "resnet",
    version: Annotated[str | None, Form()] = None,
    priority: Annotated[int, Form(ge=0, le=2)] = int(Priority.NORMAL),
    top_k: Annotated[int, Form(ge=1, le=1000)] = 5,
) -> ClassifyResponse:
    # --- validation (cheap, fail fast, never enqueues bad input) ---
    image = await file.read()
    try:
        validate_image_bytes(image, max_bytes=settings.max_image_bytes)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    # --- delegate to the use-case ---
    result = await use_case.execute(
        image=image,
        model_name=model,
        model_version=version,
        priority=Priority(priority),
        top_k=top_k,
        trace_id=request.state.trace_id,
    )

    # --- shape the response ---
    return ClassifyResponse(
        request_id=result.request_id,
        trace_id=result.trace_id,
        status=result.status,
        model_name=result.model_name,
        model_version=result.model_version,
        batch_size=result.batch_size,
        worker_id=result.worker_id,
        predictions=result.predictions,
        latency=LatencyBreakdown(
            queue_time_ms=result.queue_time_ms,
            batch_wait_ms=result.batch_wait_ms,
            inference_time_ms=result.inference_time_ms,
            total_time_ms=result.total_time_ms,
        ),
    )


def metrics_app():  # type: ignore[no-untyped-def]
    return metrics_asgi_app()
