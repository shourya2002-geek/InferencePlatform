"""SubmitInferenceUseCase — the gateway's one piece of business logic.

Pure orchestration, no FastAPI types. It:

1. checks the circuit breaker (fail fast if the data plane is unhealthy),
2. builds an :class:`InferenceRequest` with a deadline derived from the timeout
   budget (so the scheduler can shed it if it expires in-queue),
3. submits image + request to the data plane,
4. blocks on the result mailbox up to the timeout,
5. translates the outcome into a result or a typed platform error, and records
   the breaker success/failure that drives load-shedding.

Keeping this framework-free is what lets us unit-test the whole request path
against fakeredis with no HTTP server.
"""

from __future__ import annotations

import time

from platform_common.config.settings import GatewaySettings
from platform_common.errors import UpstreamTimeoutError
from platform_common.observability import PlatformMetrics, get_logger
from platform_common.schemas import (
    InferenceRequest,
    InferenceResult,
    Priority,
    RequestStatus,
)
from platform_common.utils.circuit_breaker import CircuitBreaker
from platform_common.utils.ids import new_request_id
from platform_common.utils.timing import Stopwatch

from services.api_gateway.infrastructure.gateway_client import GatewayDataPlaneClient

log = get_logger("gateway.usecase")


class SubmitInferenceUseCase:
    def __init__(
        self,
        client: GatewayDataPlaneClient,
        *,
        settings: GatewaySettings,
        breaker: CircuitBreaker,
        metrics: PlatformMetrics,
    ) -> None:
        self._client = client
        self._settings = settings
        self._breaker = breaker
        self._metrics = metrics

    async def execute(
        self,
        *,
        image: bytes,
        model_name: str,
        model_version: str | None,
        priority: Priority,
        top_k: int,
        trace_id: str,
    ) -> InferenceResult:
        # 1. fail fast if downstream is unhealthy
        self._breaker.allow()

        timeout_s = self._settings.request_timeout_ms / 1000.0
        request = InferenceRequest(
            request_id=new_request_id(),
            trace_id=trace_id,
            model_name=model_name,
            model_version=model_version,
            priority=priority,
            image_ref="",  # filled by the store; reference is the request_id
            image_bytes_len=len(image),
            top_k=top_k,
            deadline_at=time.time() + timeout_s,
        )
        request.image_ref = request.request_id

        with Stopwatch() as sw:
            # 2-3. submit
            await self._client.submit(request, image)
            # 4. await the answer
            result = await self._client.await_result(
                request.request_id, timeout_s=timeout_s
            )

        if result is None:
            # 5a. timeout: record a failure (may trip the breaker) and raise 504
            self._breaker.record_failure()
            self._record(model_name, RequestStatus.TIMEOUT, sw.elapsed_ms)
            log.warning(
                "gateway.timeout",
                request_id=request.request_id,
                trace_id=trace_id,
                waited_ms=round(sw.elapsed_ms, 1),
            )
            raise UpstreamTimeoutError(
                f"no result within {self._settings.request_timeout_ms}ms"
            )

        # 5b. success path (even a per-item ERROR result means the plane is alive)
        self._breaker.record_success()
        result.total_time_ms = result.total_time_ms or sw.elapsed_ms
        self._record(model_name, result.status, sw.elapsed_ms)
        return result

    def _record(self, model: str, status: RequestStatus, elapsed_ms: float) -> None:
        svc = self._settings.service_name
        self._metrics.request_count.labels(svc, model, status.value).inc()
        self._metrics.request_latency.labels(svc, model).observe(elapsed_ms)
