# API Reference

Interactive docs are always live at `http://<gateway>:8080/docs` (Swagger) and
`/redoc`. This page is the human summary.

## Authentication

Every inference call requires a header:

```
X-API-Key: <one of GATEWAY_API_KEYS>
```

Missing/invalid → `401 unauthorized`. Defaults: `demo-key-staff`, `demo-key-ml`.

## Tracing

Send `X-Trace-Id` to correlate your call across services; if omitted the gateway
mints one. It is echoed in the `X-Trace-Id` response header and in every log line
and result.

---

## `POST /v1/classify`

Classify an uploaded image. `multipart/form-data`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `file` | file | — | the image (`max GATEWAY_MAX_IMAGE_BYTES`, default 5 MiB) |
| `model` | string | `resnet` | logical model name |
| `version` | string | _latest_ | pin a version (`v1`/`v2`/`v3`) or omit for latest |
| `priority` | int | `1` | `0`=low, `1`=normal, `2`=high |
| `top_k` | int | `5` | number of predictions (1–1000) |

### Example

```bash
curl -X POST http://localhost:8080/v1/classify \
  -H "X-API-Key: demo-key-staff" \
  -F "file=@cat.jpg" -F "model=resnet" -F "version=v2" \
  -F "priority=2" -F "top_k=3"
```

### 200 response

```json
{
  "request_id": "req_18f...c3",
  "trace_id": "9b1c...",
  "status": "ok",
  "model_name": "resnet",
  "model_version": "v2",
  "batch_size": 8,
  "worker_id": "inference-worker-abc",
  "predictions": [
    {"label": "tabby_cat", "index": 281, "score": 0.41},
    {"label": "egyptian_cat", "index": 285, "score": 0.22},
    {"label": "tiger_cat", "index": 282, "score": 0.10}
  ],
  "latency": {
    "queue_time_ms": 1.2,
    "batch_wait_ms": 7.8,
    "inference_time_ms": 11.4,
    "total_time_ms": 21.0
  }
}
```

The `latency` block is the per-hop attribution from
[ARCHITECTURE.md §4](ARCHITECTURE.md#4-request-lifecycle).

### Errors

| Status | `error` code | Cause |
|---|---|---|
| 401 | `unauthorized` | missing/invalid API key |
| 422 | `validation_error` | bad/oversize/undecodable image |
| 429 | `rate_limited` | token bucket exhausted (`Retry-After` header) |
| 503 | `queue_overflow` | ingest queue at capacity (backpressure) |
| 503 | `circuit_open` | data plane unhealthy, shedding load |
| 504 | `upstream_timeout` | no result within `GATEWAY_REQUEST_TIMEOUT_MS` |

Error body:

```json
{ "error": "rate_limited", "detail": "rate limit exceeded for this API key", "trace_id": "9b1c..." }
```

---

## Health & ops

| Method | Path | Service | Purpose |
|---|---|---|---|
| GET | `/healthz` | all | liveness |
| GET | `/readyz` | gateway, worker, scheduler | readiness (deps reachable) |
| GET | `/metrics` | all | Prometheus exposition |
| GET | `/v1/stats` | metrics:9000 | platform state snapshot (JSON) |
| GET | `/v1/models` | worker:8090 | resident models |
| POST | `/v1/models/{name}/promote?version=vN` | worker:8090 | hot-reload / promote a version |
