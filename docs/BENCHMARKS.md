# Benchmarks & Results

This is a **results template** plus a real example run. Re-run on your hardware
and paste the tables — the scripts print them in this exact Markdown format.

```bash
make bench-concurrency      # concurrency models (works on the stub, no torch)
make bench-pytorch          # pytorch optimization techniques (needs .[ml])
make load-test              # Locust against a running gateway
```

---

## 1. Concurrency model comparison

`python benchmarks/concurrency_comparison.py`

> **Thesis:** on a single serial accelerator, concurrency *alone* does not add
> throughput and destroys latency; **dynamic batching** is what scales.

### Example run (stub backend, simulated accelerator, M-series laptop)

```
backend=stub model=resnet:v2 requests=256 max_batch=32
```

| Strategy                     |  req/s   |  p50ms  |  p95ms  |  p99ms  |  mean   |
|------------------------------|----------|---------|---------|---------|---------|
| naive sync (batch=1)         |    148.3 |    6.84 |    7.53 |    7.74 |    6.74 |
| async (batch=1, concurrent)  |    147.0 |  437.61 |  444.97 |  446.09 |  381.64 |
| worker pool x8 (batch=1)     |    142.9 |   55.58 |   60.65 |   62.31 |   55.16 |
| dynamic batching (<= 32)     |    659.1 |   23.60 |   24.32 |   24.32 |   22.78 |

**Reading it:** all the batch-of-1 strategies plateau at ~145 req/s (the device
is serial); concurrency just deepens the queue and inflates latency. Batching
lifts throughput **~4.4×** while keeping latency bounded. On a real GPU the gap is
typically far larger (10–30×) because the per-call overhead is relatively bigger.

---

## 2. PyTorch optimization techniques

`python benchmarks/pytorch_optimizations.py` (requires `pip install -e ".[ml]"`)

Fill in after running on your target hardware:

| Strategy                  |  req/s  |  p50ms  |  p95ms  |  p99ms  | Notes |
|---------------------------|---------|---------|---------|---------|-------|
| 1. baseline train()+grad  |         |         |         |         | autograd tape + train-mode BN: worst |
| 2. eval()                 |         |         |         |         | correctness fix (BN/dropout) |
| 3. eval()+no_grad         |         |         |         |         | drops autograd → less mem/time |
| 4. inference_mode         |         |         |         |         | strongest no-autograd context |
| 5. torchscript            |         |         |         |         | op fusion, no Python overhead |
| 6. amp fp16 (cuda)        |         |         |         |         | ~2× matmul on tensor cores |
| 7. dynamic int8 (cpu)     |         |         |         |         | smaller + faster Linear on CPU |
| 8. onnxruntime (cpu)      |         |         |         |         | aggressive graph opt; often CPU-fastest |

### Expected qualitative impact

| Technique | Latency | Throughput | Memory |
|---|---|---|---|
| `eval()` | – (correctness) | – | – |
| `no_grad` / `inference_mode` | ↓ | ↑ | ↓↓ (no tape) |
| TorchScript | ↓ | ↑ | ~ |
| AMP (fp16) | ↓↓ (GPU) | ↑↑ (GPU) | ↓ |
| Dynamic quantization | ↓ (CPU) | ↑ (CPU) | ↓↓ |
| ONNX Runtime | ↓ (CPU) | ↑ (CPU) | ~ |

---

## 3. Load test (Locust)

`locust -f loadtest/locustfile.py --host http://localhost:8080`

Run each tier headless and record the result:

| Tier | Users | req/s achieved | p50 | p95 | p99 | error % |
|---|---|---|---|---|---|---|
| 100 RPS  | 50  |  |  |  |  |  |
| 500 RPS  | 200 |  |  |  |  |  |
| 1000 RPS | 400 |  |  |  |  |  |

Compare across configurations (the four axes the spec asks for):

| Config | req/s | p99 | Notes |
|---|---|---|---|
| single request (MAX_BATCH_SIZE=1) |  |  | batching disabled |
| batched (MAX_BATCH_SIZE=32) |  |  | default |
| multiple workers (×3) |  |  | `--scale inference-worker=3` |
| optimized runtime (torchscript+amp) |  |  | GPU image |

Headless example that writes CSVs into `benchmarks/results/`:

```bash
locust -f loadtest/locustfile.py --host http://localhost:8080 \
  --headless -u 200 -r 50 -t 2m --csv benchmarks/results/batched_500
```

---

## 4. Method notes

- Latencies are measured client-/caller-side and reported as percentiles from the
  sorted sample (no interpolation) — see `_bench_common.summarize`.
- The stub backend **simulates** accelerator economics (fixed per-call overhead +
  per-item cost, behind a device lock). It is for shape/relative comparison; use
  the torch backend for absolute numbers.
- Always warm up before measuring (the scripts do): the first forward pass pays
  lazy CUDA init / cudnn autotune / JIT specialization.
