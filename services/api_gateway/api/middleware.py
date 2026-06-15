"""Request-tracing middleware + platform exception handlers.

The middleware mints (or honors an inbound) ``trace_id``, binds it to the
logging context, stamps it on ``request.state`` and the response header
(``X-Trace-Id``), and emits one structured access log per request. That trace id
is the correlation key threaded through every downstream Redis message.

The exception handlers translate the platform error hierarchy into clean JSON +
the right HTTP status, so route code can just ``raise`` domain errors.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from platform_common.errors import PlatformError, RateLimitedError
from platform_common.observability import bind_trace, get_logger
from platform_common.observability.logging import clear_trace
from platform_common.utils.ids import new_trace_id
from platform_common.utils.timing import Stopwatch
from starlette.middleware.base import BaseHTTPMiddleware

log = get_logger("gateway.http")


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable]
    ):
        trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
        request.state.trace_id = trace_id
        bind_trace(trace_id, path=request.url.path, method=request.method)
        try:
            with Stopwatch() as sw:
                response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            log.info(
                "http.access",
                status=response.status_code,
                duration_ms=round(sw.elapsed_ms, 2),
            )
            return response
        finally:
            clear_trace()


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PlatformError)
    async def _platform_error(request: Request, exc: PlatformError) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None)
        headers = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(max(1, round(exc.retry_after)))
        log.warning("http.platform_error", code=exc.code, status=exc.http_status)
        return JSONResponse(
            status_code=exc.http_status,
            headers=headers,
            content={"error": exc.code, "detail": exc.message, "trace_id": trace_id},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None)
        log.exception("http.unhandled_error")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "detail": "unexpected server error",
                "trace_id": trace_id,
            },
        )
