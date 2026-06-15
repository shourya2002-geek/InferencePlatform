"""Core inference message contracts.

The lifecycle of a single request, expressed in three messages:

    InferenceRequest  -- gateway -> scheduler queue  (one per client request)
    BatchEnvelope     -- scheduler -> worker queue    (N requests grouped)
    InferenceResult   -- worker -> gateway result list (one per client request)

All timestamps are epoch seconds (float) captured with ``time.time()`` so they
can be compared across processes. Durations on ``InferenceResult`` are in
milliseconds because that is the unit humans reason about for latency budgets.
"""

from __future__ import annotations

import time
from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field, NonNegativeFloat


class Priority(IntEnum):
    """Request priority. Higher value == scheduled sooner.

    Modeled as an ``IntEnum`` so it serializes to a plain integer and so the
    scheduler can compare/sort priorities arithmetically.
    """

    LOW = 0
    NORMAL = 1
    HIGH = 2


class RequestStatus(StrEnum):
    """Terminal/!terminal status carried on a result."""

    OK = "ok"
    TIMEOUT = "timeout"
    ERROR = "error"
    REJECTED = "rejected"


class ClassPrediction(BaseModel):
    """A single (label, score) pair from the classifier head."""

    label: str
    index: int
    score: float


class InferenceRequest(BaseModel):
    """A single client request as it travels gateway -> scheduler -> worker.

    The raw image bytes are *not* embedded here. They are stored once in Redis
    under ``image_ref`` (see ``messaging.keys.image_key``) and referenced by id.
    This keeps queue messages small and lets the scheduler reason about
    thousands of pending requests without moving megabytes of pixels around.
    """

    request_id: str
    trace_id: str
    model_name: str
    model_version: str | None = None  # None => "latest" resolved by the worker
    priority: Priority = Priority.NORMAL
    image_ref: str
    image_bytes_len: int = 0
    top_k: int = Field(default=5, ge=1, le=1000)
    enqueued_at: float = Field(default_factory=time.time)
    deadline_at: float | None = None  # absolute epoch deadline; scheduler may drop

    def is_expired(self, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        return self.deadline_at is not None and now >= self.deadline_at


class BatchEnvelope(BaseModel):
    """A batch of requests handed to a worker as a unit.

    The batch is homogeneous in ``(model_name, model_version)`` — the batcher
    only ever groups requests that target the same loaded model, because they
    must share a single forward pass.
    """

    batch_id: str
    model_name: str
    model_version: str | None
    requests: list[InferenceRequest]
    formed_at: float = Field(default_factory=time.time)
    # how long the batcher waited (ms) before flushing — useful for tracing
    batch_wait_ms: NonNegativeFloat = 0.0

    @property
    def size(self) -> int:
        return len(self.requests)


class InferenceResult(BaseModel):
    """The per-request answer written back to the gateway.

    Carries a full latency breakdown so the gateway (and Grafana) can attribute
    where time went: queue wait, batch-formation wait, and pure model compute.
    """

    request_id: str
    trace_id: str
    status: RequestStatus = RequestStatus.OK
    model_name: str = ""
    model_version: str | None = None
    predictions: list[ClassPrediction] = Field(default_factory=list)
    batch_id: str | None = None
    batch_size: int = 1
    worker_id: str = ""
    # latency breakdown (milliseconds)
    queue_time_ms: NonNegativeFloat = 0.0
    batch_wait_ms: NonNegativeFloat = 0.0
    inference_time_ms: NonNegativeFloat = 0.0
    total_time_ms: NonNegativeFloat = 0.0
    error: str | None = None

    @classmethod
    def failure(
        cls,
        request: InferenceRequest,
        status: RequestStatus,
        error: str,
    ) -> InferenceResult:
        return cls(
            request_id=request.request_id,
            trace_id=request.trace_id,
            status=status,
            model_name=request.model_name,
            model_version=request.model_version,
            error=error,
        )
