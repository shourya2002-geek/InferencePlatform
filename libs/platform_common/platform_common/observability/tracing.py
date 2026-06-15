"""OpenTelemetry tracing setup.

Tracing is opt-in: if ``otel_traces_exporter`` is not ``otlp`` we install a
no-op-ish tracer provider that still produces spans (so ``start_span`` always
works and trace ids are real) but exports nothing. That keeps local dev free of
a collector dependency while production flips one env var to ship spans.

The platform threads its *own* ``trace_id`` (from :mod:`platform_common.utils.ids`)
through Redis messages because spans cannot cross a queue automatically — the
trace id is the correlation key that stitches gateway, scheduler and worker
spans into one logical trace.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False


def configure_tracing(
    *,
    service_name: str,
    exporter: str = "none",
    endpoint: str | None = None,
) -> None:
    global _configured
    if _configured:
        return
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    if exporter == "otlp" and endpoint:
        # Imported lazily so the OTLP exporter dep is optional at runtime.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
        )
    trace.set_tracer_provider(provider)
    _configured = True


@contextmanager
def start_span(name: str, *, trace_id: str | None = None, **attrs: object) -> Iterator[None]:
    """Start a span, attaching the platform trace id as an attribute.

    We record the platform trace id as a span attribute (``pip.trace_id``) so a
    backend search by our correlation id resolves to the OTel trace even across
    the Redis hops where W3C context isn't propagated.
    """
    tracer = trace.get_tracer("pip")
    with tracer.start_as_current_span(name) as span:
        if trace_id:
            span.set_attribute("pip.trace_id", trace_id)
        for k, v in attrs.items():
            span.set_attribute(k, v)  # type: ignore[arg-type]
        yield
