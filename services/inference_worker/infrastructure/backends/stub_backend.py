"""NumPy stub backend — no torch, no GPU, fully deterministic.

Why this exists: the platform's *value* is in the queueing, batching, scheduling
and observability — not in the model. The stub lets you run, test, and benchmark
the entire system (including the dynamic-batching speedup) on any laptop with no
multi-gigabyte torch install.

It deliberately models the **economics of an accelerator**: each forward pass has
a fixed per-call overhead (kernel launch / dispatch / Python boundary) plus a
small per-item cost. That fixed overhead is exactly what dynamic batching
amortizes, so `bench-concurrency` shows the real-shaped throughput curve. The
overhead is simulated with a sleep and clearly labeled — swap in the torch
backend for true numbers.
"""

from __future__ import annotations

import threading
import time

import numpy as np
from platform_common.errors import RuntimeBackendError

from services.inference_worker.domain.runtime import LoadedModel, ModelSpec

# Simulated accelerator economics (milliseconds). Scaled by model capacity.
_BASE_OVERHEAD_MS = 4.0   # per forward-pass fixed cost (the thing batching hides)
_PER_ITEM_MS = 0.35       # marginal cost per sample in the batch

# A single accelerator is a *serial* resource: one CUDA stream executes one
# kernel at a time. We model that with a process-global lock so concurrent
# callers contend for the device instead of magically parallelizing (which a
# GIL-releasing sleep would otherwise fake). This is what makes the concurrency
# benchmark honest: threads alone don't speed up one device — only batching does.
_DEVICE_LOCK = threading.Lock()


class StubBackend:
    name = "stub"

    def load(self, spec: ModelSpec, *, device: str) -> LoadedModel:
        # Deterministic projection weights seeded by the model key, so the same
        # version always yields the same outputs (reproducible tests/demos).
        rng = np.random.default_rng(abs(hash(spec.key)) % (2**32))
        feat = 3 * 32 * 32  # we downsample to 32x32 for a cheap, fast projection
        weight = rng.standard_normal((feat, spec.num_classes)).astype(np.float32)
        weight *= 0.01
        capacity = spec.width * spec.depth  # v1<v2<v3 → more sim compute
        handle = {"weight": weight, "capacity": capacity}
        return LoadedModel(
            spec=spec,
            handle=handle,
            backend=self.name,
            device="cpu",
            loaded_at=time.time(),
        )

    def warmup(self, model: LoadedModel, *, batch_size: int) -> None:
        dummy = np.zeros((batch_size, 3, model.spec.input_size, model.spec.input_size), np.float32)
        self.infer(model, dummy)

    def infer(self, model: LoadedModel, batch: np.ndarray) -> np.ndarray:
        if batch.ndim != 4:
            raise RuntimeBackendError(f"expected NCHW, got shape {batch.shape}")
        n = batch.shape[0]
        handle = model.handle
        capacity = float(handle["capacity"])  # type: ignore[index]

        # Simulated forward-pass time: fixed overhead + marginal per-item, both
        # scaled by model capacity. This is the curve batching exploits.
        scale = capacity / (32 * 3)  # normalize against v2-ish
        sim_ms = (_BASE_OVERHEAD_MS + _PER_ITEM_MS * n) * scale

        # Contend for the serial "device" for the duration of the forward pass.
        with _DEVICE_LOCK:
            time.sleep(sim_ms / 1000.0)
            # Cheap, real computation so outputs are deterministic & shape-correct:
            # downsample to 32x32 by strided slicing, flatten, project.
            s = model.spec.input_size // 32
            ds = batch[:, :, ::s, ::s][:, :, :32, :32]  # (N,3,32,32)
            flat = ds.reshape(n, -1)
            weight = handle["weight"]  # type: ignore[index]
            return (flat @ weight).astype(np.float32)

    def unload(self, model: LoadedModel) -> None:
        model.handle = {}
