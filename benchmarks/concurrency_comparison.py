"""Benchmark: naive vs async vs worker-pool vs dynamic-batching inference.

Demonstrates *the* thesis of the talk: the model forward pass has a fixed
per-call overhead, so serving requests one-at-a-time wastes the accelerator.
Each strategy processes the same total number of requests; we report throughput
and latency percentiles.

Runs on the StubBackend by default (its simulated accelerator economics make the
batching win visible on any laptop). Set ``RUNTIME_BACKEND=torch_eager`` and
install ``.[ml]`` to benchmark real PyTorch.

    python benchmarks/concurrency_comparison.py
"""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor

from _bench_common import LatencyStats, summarize, synthetic_nchw, table_header

from services.inference_worker.domain.catalog import ModelCatalog
from services.inference_worker.infrastructure.backends import build_backend

TOTAL_REQUESTS = int(os.getenv("BENCH_REQUESTS", "512"))
CONCURRENCY = int(os.getenv("BENCH_CONCURRENCY", "64"))
MAX_BATCH = int(os.getenv("MAX_BATCH_SIZE", "32"))
POOL_WORKERS = int(os.getenv("BENCH_POOL_WORKERS", "8"))
BACKEND = os.getenv("RUNTIME_BACKEND", "stub")
MODEL_VERSION = os.getenv("DEFAULT_MODEL_VERSION", "v2")


def _setup():
    backend = build_backend(BACKEND)
    spec = ModelCatalog().resolve("resnet", MODEL_VERSION)
    model = backend.load(spec, device=os.getenv("DEVICE", "cpu"))
    backend.warmup(model, batch_size=MAX_BATCH)
    return backend, model


def bench_naive_sync(backend, model) -> LatencyStats:
    """Batch-of-1, strictly sequential. The worst case (and the most common
    first implementation)."""
    one = synthetic_nchw(1)
    lat: list[float] = []
    t0 = time.perf_counter()
    for _ in range(TOTAL_REQUESTS):
        s = time.perf_counter()
        backend.infer(model, one)
        lat.append((time.perf_counter() - s) * 1000)
    return summarize("naive sync (batch=1)", lat, time.perf_counter() - t0)


async def bench_async(backend, model) -> LatencyStats:
    """Batch-of-1 but concurrent: many coroutines offload the forward pass to a
    thread pool, overlapping the (GIL-releasing) compute."""
    one = synthetic_nchw(1)
    lat: list[float] = []
    sem = asyncio.Semaphore(CONCURRENCY)
    pool = ThreadPoolExecutor(max_workers=CONCURRENCY)
    loop = asyncio.get_running_loop()

    async def one_request() -> None:
        async with sem:
            s = time.perf_counter()
            await loop.run_in_executor(pool, backend.infer, model, one)
            lat.append((time.perf_counter() - s) * 1000)

    t0 = time.perf_counter()
    await asyncio.gather(*[one_request() for _ in range(TOTAL_REQUESTS)])
    pool.shutdown(wait=True)
    return summarize("async (batch=1, concurrent)", lat, time.perf_counter() - t0)


def bench_worker_pool(backend, model) -> LatencyStats:
    """A fixed pool of threads, each doing batch-of-1 (a la a naive worker pool
    without batching)."""
    one = synthetic_nchw(1)
    lat: list[float] = []

    def task() -> float:
        s = time.perf_counter()
        backend.infer(model, one)
        return (time.perf_counter() - s) * 1000

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=POOL_WORKERS) as pool:
        for ms in pool.map(lambda _: task(), range(TOTAL_REQUESTS)):
            lat.append(ms)
    return summarize(f"worker pool x{POOL_WORKERS} (batch=1)", lat, time.perf_counter() - t0)


def bench_dynamic_batching(backend, model) -> LatencyStats:
    """Aggregate requests into batches of up to MAX_BATCH — one forward pass per
    batch. Latency is measured per *request* (all requests in a batch share the
    batch's compute time)."""
    lat: list[float] = []
    t0 = time.perf_counter()
    remaining = TOTAL_REQUESTS
    while remaining > 0:
        n = min(MAX_BATCH, remaining)
        batch = synthetic_nchw(n)
        s = time.perf_counter()
        backend.infer(model, batch)
        per_req_ms = (time.perf_counter() - s) * 1000
        lat.extend([per_req_ms] * n)  # each request in the batch waited this long
        remaining -= n
    return summarize(f"dynamic batching (<= {MAX_BATCH})", lat, time.perf_counter() - t0)


async def main() -> None:
    backend, model = _setup()
    print(
        f"\nConcurrency benchmark — backend={BACKEND} model=resnet:{MODEL_VERSION} "
        f"requests={TOTAL_REQUESTS} max_batch={MAX_BATCH}\n"
    )
    results = [
        bench_naive_sync(backend, model),
        await bench_async(backend, model),
        bench_worker_pool(backend, model),
        bench_dynamic_batching(backend, model),
    ]
    print(table_header())
    for r in results:
        print(r.as_row())

    base = results[0].rps
    best = max(results, key=lambda r: r.rps)
    print(
        f"\nThroughput: dynamic batching is {best.rps / base:.1f}x the naive baseline "
        f"({base:.0f} -> {best.rps:.0f} req/s).\n"
        "Note: stub backend simulates accelerator economics; run with "
        "RUNTIME_BACKEND=torch_eager and .[ml] for real numbers.\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
