"""Prometheus metrics — the single registry of platform telemetry.

Every metric named in the design lives here so there is exactly one definition,
one set of labels, and one place to reason about cardinality. Services import
:class:`PlatformMetrics` and record against it; the metrics endpoint scrapes the
default registry.

Cardinality note: labels are kept to bounded, low-cardinality values
(``service``, ``model``, ``version``, ``stage``). We never label by request id or
trace id — that would explode the time-series count.
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    make_asgi_app,
)

# Latency buckets tuned for low-latency inference (sub-ms to ~2.5s tail).
_LATENCY_BUCKETS = (
    1, 2, 5, 10, 20, 35, 50, 75, 100, 150, 200, 300, 500, 750, 1000, 1500, 2500,
)
_BATCH_BUCKETS = (1, 2, 4, 8, 12, 16, 24, 32, 48, 64)


class PlatformMetrics:
    """Holder for all platform metrics, parameterized by service name.

    Implemented as a singleton-per-process via :meth:`get` so repeated imports
    don't double-register collectors (which Prometheus forbids).
    """

    _instance: PlatformMetrics | None = None

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        # request_count
        self.request_count = Counter(
            "pip_request_count_total",
            "Total inference requests seen",
            ["service", "model", "status"],
            registry=registry,
        )
        # request_latency (end-to-end, gateway-observed)
        self.request_latency = Histogram(
            "pip_request_latency_ms",
            "End-to-end request latency in milliseconds",
            ["service", "model"],
            buckets=_LATENCY_BUCKETS,
            registry=registry,
        )
        # inference_time (pure model compute, worker-observed)
        self.inference_time = Histogram(
            "pip_inference_time_ms",
            "Model forward-pass time in milliseconds",
            ["service", "model", "version"],
            buckets=_LATENCY_BUCKETS,
            registry=registry,
        )
        # batch_size
        self.batch_size = Histogram(
            "pip_batch_size",
            "Formed batch size",
            ["service", "model"],
            buckets=_BATCH_BUCKETS,
            registry=registry,
        )
        # queue_depth
        self.queue_depth = Gauge(
            "pip_queue_depth",
            "Pending items per queue stage",
            ["service", "stage"],
            registry=registry,
        )
        # worker_utilization (fraction of workers busy, or busy slots)
        self.worker_utilization = Gauge(
            "pip_worker_utilization",
            "Worker busy fraction (0..1)",
            ["service", "worker_id"],
            registry=registry,
        )
        # batch wait time, queue wait time (latency attribution)
        self.stage_latency = Histogram(
            "pip_stage_latency_ms",
            "Latency contributed by a single pipeline stage",
            ["service", "stage"],
            buckets=_LATENCY_BUCKETS,
            registry=registry,
        )

    @classmethod
    def get(cls) -> PlatformMetrics:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def metrics_asgi_app():  # type: ignore[no-untyped-def]
    """Return an ASGI app exposing the default registry at e.g. ``/metrics``."""
    return make_asgi_app()


def render_latest() -> tuple[bytes, str]:
    """Render metrics for a plain (non-ASGI) HTTP handler."""
    return generate_latest(), CONTENT_TYPE_LATEST
