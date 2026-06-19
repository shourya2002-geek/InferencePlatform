# PyTorch Inference Platform — Console

An interactive, conference-grade **systems-engineering simulator** for the
PyTorch Inference Platform. It explains — visually and live — why naive inference
serving fails, why queues and dynamic batching exist, how workers scale, how
PyTorch inference behaves internally, and how the platform survives failure.

> Every number is **grounded in the real implementation**. The simulation engine
> mirrors the actual code: the dynamic-batching flush rule, the stub backend's
> inference economics `(4.0 + 0.35·N)·scale`, the circuit-breaker thresholds
> (20 failures → open, 10s reset), worker heartbeat + janitor recovery, and the
> measured benchmark numbers from `docs/BENCHMARKS.md`. See
> [`src/sim/constants.ts`](src/sim/constants.ts) for the source map.

## Run

```bash
cd web
nvm use 20            # needs Node 18+ (Vite 5)
npm install
npm run dev           # http://localhost:5173
# production build:
npm run build && npm run preview
```

## What's inside

| Section | Teaches |
|---|---|
| **Overview** | live platform health (RPS, queue, batch, p50/p95/p99, util, errors) |
| **Architecture** | clickable request lifecycle with animated tokens + per-node responsibilities/bottlenecks/scaling |
| **Traffic Simulator** | 50 → 5000 RPS; queue growth, latency evolution, worker activity |
| **Dynamic Batching** ★ | animated batch formation, MAX_BATCH_SIZE / MAX_WAIT_MS knobs, throughput-vs-batch curve |
| **Worker Pool** | 1/2/4/8 workers, per-worker utilization, queue drain, crash button |
| **PyTorch Runtime Lab** | train vs eval · autograd overhead · GPU utilization · inference pipeline · CUDA async timeline |
| **Runtime Comparison** | eager / TorchScript / compile / AMP / BF16 / INT8 / ONNX across latency, throughput, memory, size, startup |
| **Optimization Journey** ★ | naive → eval → inference_mode → batching → TorchScript → AMP → workers, with live metrics per step |
| **Failure Injection** | worker crash, queue overflow, runtime/Redis failure, traffic spike, model-load fail + circuit-breaker & backpressure demos |
| **Model Registry** | resnet v1/v2/v3 versioning, canary, zero-downtime promote/rollback |
| **Observability** | Grafana-style metric panels + animated trace-flow |
| **Replay Center** | 8 prebuilt auto-animating scenarios for talks |

★ = flagship demos.

## Architecture

```
src/
  sim/            grounded simulation core
    constants.ts  values pulled from the Python services
    engine.ts     discrete-time fluid model (queues, batching, workers, circuit)
    content.ts    static educational content (arch nodes, pipeline, opt steps)
    scenarios.ts  control-bar presets
    replays.ts    scripted replay timelines
  state/          SimulationContext — the single tick loop + replay runner
  components/
    layout/       Sidebar, TopControlBar
    primitives/   Panel, MetricCard, Bar, Badge, CodeBlock, …
    viz/          FlowDiagram (animated), TimeSeries (recharts)
  pages/          one file per sidebar section
```

Stack: React + TypeScript + Vite + TailwindCSS + Framer Motion + Recharts.
Design language: engineering-first dark (Grafana / Datadog / Primer), PyTorch
orange used sparingly as the accent — no neon, no AI-brain visuals.
