"""Tests for the worker domain: stub backend, registry (LRU/lazy/hot-reload),
and the batch executor — all without torch or Redis."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image
from platform_common.schemas import BatchEnvelope, InferenceRequest, Priority

from services.inference_worker.domain.catalog import ModelCatalog
from services.inference_worker.domain.executor import BatchExecutor
from services.inference_worker.domain.registry import ModelRegistry
from services.inference_worker.infrastructure.backends.stub_backend import StubBackend


def _png(seed: int = 0) -> bytes:
    arr = (np.random.default_rng(seed).random((40, 40, 3)) * 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_stub_backend_shape_and_determinism():
    backend = StubBackend()
    catalog = ModelCatalog()
    spec = catalog.resolve("resnet", "v2")
    model = backend.load(spec, device="cpu")
    batch = np.zeros((3, 3, spec.input_size, spec.input_size), np.float32)
    out1 = backend.infer(model, batch)
    out2 = backend.infer(model, batch)
    assert out1.shape == (3, spec.num_classes)
    assert np.allclose(out1, out2)  # deterministic


async def test_registry_lazy_load_and_cache():
    registry = ModelRegistry(StubBackend(), ModelCatalog(), cache_size=2)
    assert registry.resident() == []
    m = await registry.get("resnet", "v2")
    assert m.spec.version == "v2"
    assert "resnet:v2" in registry.resident()
    # second get is a cache hit (same object)
    again = await registry.get("resnet", "v2")
    assert again is m


async def test_registry_lru_eviction():
    registry = ModelRegistry(StubBackend(), ModelCatalog(), cache_size=2)
    await registry.get("resnet", "v1")
    await registry.get("resnet", "v2")
    await registry.get("resnet", "v3")  # evicts the LRU (v1)
    assert "resnet:v1" not in registry.resident()
    assert len(registry.resident()) == 2


async def test_registry_hot_reload_promotion():
    catalog = ModelCatalog()
    registry = ModelRegistry(StubBackend(), catalog, cache_size=4)
    # default latest is v3; promote v1 to latest with no downtime.
    await registry.promote("resnet", "v1")
    latest = await registry.get("resnet", None)
    assert latest.spec.version == "v1"


async def test_executor_produces_topk_predictions():
    registry = ModelRegistry(StubBackend(), ModelCatalog(), cache_size=2)
    executor = BatchExecutor(registry, worker_id="w-test")
    reqs = [
        InferenceRequest(
            request_id=f"r{i}",
            trace_id="t",
            model_name="resnet",
            model_version="v2",
            priority=Priority.NORMAL,
            image_ref=f"r{i}",
            top_k=5,
        )
        for i in range(3)
    ]
    batch = BatchEnvelope(
        batch_id="b1", model_name="resnet", model_version="v2", requests=reqs
    )
    images = {r.request_id: _png(i) for i, r in enumerate(reqs)}
    results = await executor.execute(batch, images)
    assert len(results) == 3
    for res in results:
        assert res.status.value == "ok"
        assert len(res.predictions) == 5
        assert res.batch_size == 3
        assert res.inference_time_ms >= 0


async def test_executor_isolates_bad_image():
    registry = ModelRegistry(StubBackend(), ModelCatalog(), cache_size=2)
    executor = BatchExecutor(registry, worker_id="w-test")
    good = InferenceRequest(
        request_id="good", trace_id="t", model_name="resnet",
        model_version="v2", image_ref="good",
    )
    bad = InferenceRequest(
        request_id="bad", trace_id="t", model_name="resnet",
        model_version="v2", image_ref="bad",
    )
    batch = BatchEnvelope(
        batch_id="b1", model_name="resnet", model_version="v2", requests=[good, bad]
    )
    images = {"good": _png(1), "bad": b"not-an-image"}
    results = await executor.execute(batch, images)
    by_id = {r.request_id: r for r in results}
    assert by_id["good"].status.value == "ok"
    assert by_id["bad"].status.value == "error"
