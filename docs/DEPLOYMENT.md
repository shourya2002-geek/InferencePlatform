# Production Deployment Guide

## 1. Local (Docker Compose)

```bash
cp .env.example .env            # optional; compose has sane inline defaults
docker compose up --build -d
docker compose ps
# scale the worker tier
docker compose up -d --scale inference-worker=3
```

Endpoints:

| URL | What |
|---|---|
| http://localhost:8080/docs | Gateway OpenAPI (Swagger) |
| http://localhost:8080/metrics | Gateway Prometheus metrics |
| http://localhost:9000/v1/stats | Platform state snapshot (JSON) |
| http://localhost:9090 | Prometheus |
| http://localhost:3000 | Grafana (anonymous admin; dashboard auto-provisioned) |

Smoke test:

```bash
curl -s -X POST http://localhost:8080/v1/classify \
  -H "X-API-Key: demo-key-staff" \
  -F "file=@some.jpg" -F "model=resnet" -F "priority=2" -F "top_k=5" | jq
```

## 2. Kubernetes

```bash
docker build -t pytorch-inference-platform:latest .
# (push to your registry and update kustomization images.newName)
kubectl apply -k deploy/k8s
kubectl -n inference get pods,svc,hpa
kubectl -n inference port-forward svc/api-gateway 8080:80
```

What the manifests give you:

- Gateway `Deployment` + `Service` + CPU `HPA` (3→20).
- Scheduler `Deployment` (2 active/active via the Redis consumer group).
- Worker `Deployment` + headless `Service` (for per-pod scrape) + external-metric
  `HPA` on batch-queue depth (2→12). `WORKER_ID` is injected from the pod name.
- Metrics `Deployment` + `Service`.
- Redis `Deployment` + `Service` (replace with managed Redis in production).

### GPU workers

1. Build the ML image: `docker build --build-arg INSTALL_ML=1 -t pip-worker:gpu .`
2. In [40-inference-worker.yaml](../deploy/k8s/40-inference-worker.yaml): set the
   GPU `nodeSelector`, `resources.limits["nvidia.com/gpu"]: 1`, image `pip-worker:gpu`,
   and config `DEVICE=cuda`, `RUNTIME_BACKEND=torchscript`,
   `ENABLE_MIXED_PRECISION=true`.
3. Pre-build artifacts (`python scripts/build_models.py`) into a volume / baked image.

### Autoscaling on queue depth

Install [KEDA](https://keda.sh) and add a `ScaledObject` with the Redis `listLength`
scaler on `pip:batches`, or run prometheus-adapter to expose
`pip_platform_batch_queue_depth` as the external metric the provided HPA expects.

## 3. Configuration reference

All config is environment-driven (see [.env.example](../.env.example)). Key knobs:

| Var | Default | Effect |
|---|---|---|
| `MAX_BATCH_SIZE` | 32 | throughput ceiling per forward pass |
| `MAX_WAIT_MS` | 10 | max batch-formation latency |
| `SCHEDULER_STRATEGY` | priority | `fifo` / `priority` / `weighted` |
| `RUNTIME_BACKEND` | stub | `stub` / `torch_eager` / `torchscript` / `onnx` |
| `DEVICE` | cpu | `cpu` / `cuda` |
| `WORKER_CONCURRENCY` | 1 | parallel batch slots per worker |
| `GATEWAY_REQUEST_TIMEOUT_MS` | 2000 | client wait budget (→ 504) |
| `GATEWAY_RATE_LIMIT_RPS` | 200 | per-API-key token bucket rate |

## 4. Operational runbook

| Situation | First look | Likely fix |
|---|---|---|
| p99 latency spike | Grafana latency + queue-depth panels | add workers / raise batch size |
| 503 `queue_overflow` | request-stream depth at `SCHEDULER_QUEUE_MAXLEN` | scale workers; clients back off |
| 504s + circuit open | worker liveness panel | workers crashed/OOM — check pod logs |
| low batch sizes | batch-size panel | raise `MAX_WAIT_MS`; verify traffic volume |
| one worker hot, others idle | per-worker utilization | check reservation; restart laggard |

## 5. Zero-downtime model rollout

```bash
# warm + promote v3 to "latest" on every worker (no dropped traffic)
for pod in $(kubectl -n inference get pods -l app=inference-worker -o name); do
  kubectl -n inference exec "$pod" -- \
    curl -s -X POST "localhost:8090/v1/models/resnet/promote?version=v3"
done
```

The registry warm-loads the new version *before* flipping `latest`, so the first
post-promotion request never eats a cold start. Roll back by promoting the prior
version. See [ModelRegistry.promote](../services/inference_worker/domain/registry.py).

## 6. Graceful shutdown

`SIGTERM` → FastAPI lifespan teardown → scheduler flushes buffered batches; worker
stops reserving, drains in-flight batches, deletes its heartbeat. Set the k8s
`terminationGracePeriodSeconds` ≥ your `WORKER_BATCH_TIMEOUT_MS` so in-flight
batches finish.
