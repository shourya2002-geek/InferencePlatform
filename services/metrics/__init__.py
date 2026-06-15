"""Metrics service — platform-global telemetry exporter.

Samples queue depths and worker liveness from Redis and re-exports them as
Prometheus gauges plus a JSON snapshot. Per-service latency/throughput metrics
are exported by each service directly and scraped by Prometheus.
"""
