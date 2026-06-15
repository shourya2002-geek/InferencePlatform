"""Cross-cutting observability: logs, metrics, traces.

The three pillars, wired so a single ``trace_id`` ties them together: it appears
in every structured log line, on the Prometheus exemplar-friendly labels, and as
the OpenTelemetry span/trace id.
"""

from platform_common.observability.logging import bind_trace, configure_logging, get_logger
from platform_common.observability.metrics import (
    PlatformMetrics,
    metrics_asgi_app,
    render_latest,
)
from platform_common.observability.tracing import configure_tracing, start_span

__all__ = [
    "PlatformMetrics",
    "bind_trace",
    "configure_logging",
    "configure_tracing",
    "get_logger",
    "metrics_asgi_app",
    "render_latest",
    "start_span",
]
