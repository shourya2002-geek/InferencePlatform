"""HTTP response/request DTOs for the gateway.

These are the *public API* contract — distinct from the internal
``platform_common.schemas`` wire models. Keeping them separate means we can
evolve the internal queue format without breaking clients (and vice versa).
"""

from __future__ import annotations

from platform_common.schemas import ClassPrediction, RequestStatus
from pydantic import BaseModel, Field


class LatencyBreakdown(BaseModel):
    queue_time_ms: float
    batch_wait_ms: float
    inference_time_ms: float
    total_time_ms: float


class ClassifyResponse(BaseModel):
    request_id: str
    trace_id: str
    status: RequestStatus
    model_name: str
    model_version: str | None
    batch_size: int
    worker_id: str
    predictions: list[ClassPrediction]
    latency: LatencyBreakdown


class ErrorResponse(BaseModel):
    error: str = Field(description="machine-readable error code")
    detail: str
    trace_id: str | None = None
