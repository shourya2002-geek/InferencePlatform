"""ModelRegistry — keeps the right models hot, evicts the rest.

Responsibilities (the spec's checklist):

* **versioning**   — addresses models by (name, version) via the catalog.
* **lazy loading** — a version is loaded on first request that needs it.
* **warm loading** — ``preload`` loads + warms a version ahead of traffic.
* **model cache**  — a bounded LRU of resident models (GPU memory is finite).
* **hot reload**   — ``promote`` flips 'latest' and warms the new version so the
                     cutover happens with zero dropped requests / no downtime.

Thread-safety: a single asyncio lock guards the cache. Loads can be slow
(reading an artifact, CUDA init), so we load *outside* the lock guarding only
the bookkeeping, while a per-key in-flight map prevents two concurrent loads of
the same model (the thundering-herd-on-cold-start problem).
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict

from platform_common.observability import get_logger

from services.inference_worker.domain.catalog import ModelCatalog
from services.inference_worker.domain.runtime import (
    LoadedModel,
    ModelSpec,
    RuntimeBackend,
)

log = get_logger("registry")


class ModelRegistry:
    def __init__(
        self,
        backend: RuntimeBackend,
        catalog: ModelCatalog,
        *,
        device: str = "cpu",
        cache_size: int = 4,
        warmup_batch: int = 8,
    ) -> None:
        self._backend = backend
        self._catalog = catalog
        self._device = device
        self._cache_size = cache_size
        self._warmup_batch = warmup_batch
        # LRU: most-recently-used at the end.
        self._cache: OrderedDict[str, LoadedModel] = OrderedDict()
        self._lock = asyncio.Lock()
        self._inflight: dict[str, asyncio.Event] = {}

    async def get(self, name: str, version: str | None) -> LoadedModel:
        """Return a resident model, loading it lazily if needed."""
        spec = self._catalog.resolve(name, version)
        key = spec.key

        # Fast path: already hot.
        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached
            # Is another coroutine already loading this exact model?
            event = self._inflight.get(key)
            if event is None:
                event = asyncio.Event()
                self._inflight[key] = event
                loader = True
            else:
                loader = False

        if not loader:
            # Wait for the in-flight load, then read from cache.
            await event.wait()
            async with self._lock:
                model = self._cache.get(key)
                if model is None:
                    raise RuntimeError(f"load of {key} failed in another task")
                self._cache.move_to_end(key)
                return model

        # We are the loader.
        try:
            model = await self._load_and_warm(spec)
            async with self._lock:
                self._cache[key] = model
                self._cache.move_to_end(key)
                await self._evict_if_needed_locked()
            return model
        finally:
            async with self._lock:
                self._inflight.pop(key, None)
            event.set()

    async def preload(self, name: str, version: str | None) -> LoadedModel:
        """Warm-load a version ahead of traffic (called at startup)."""
        return await self.get(name, version)

    async def promote(self, name: str, version: str) -> None:
        """Hot-reload: warm the new version, *then* flip 'latest'.

        Ordering matters — warm first so the first request after promotion does
        not eat a cold-start. This is how you change models without downtime.
        """
        await self.preload(name, version)
        self._catalog.set_latest(name, version)
        log.info("model.promoted", model=name, version=version)

    async def _load_and_warm(self, spec: ModelSpec) -> LoadedModel:
        t0 = time.perf_counter()
        # Backend load may block (disk/CUDA); run in a thread to keep the loop free.
        model = await asyncio.to_thread(self._backend.load, spec, device=self._device)
        await asyncio.to_thread(
            self._backend.warmup, model, batch_size=self._warmup_batch
        )
        model.warmup_done = True
        log.info(
            "model.loaded",
            model=spec.name,
            version=spec.version,
            backend=self._backend.name,
            device=self._device,
            load_ms=round((time.perf_counter() - t0) * 1000, 1),
        )
        return model

    async def _evict_if_needed_locked(self) -> None:
        while len(self._cache) > self._cache_size:
            key, victim = self._cache.popitem(last=False)  # LRU
            log.info("model.evicted", key=key)
            await asyncio.to_thread(self._backend.unload, victim)

    def resident(self) -> list[str]:
        return list(self._cache.keys())

    @property
    def backend(self) -> RuntimeBackend:
        """Expose the backend so the executor can run forward passes without
        re-resolving it (the model alone doesn't carry a callable handle path)."""
        return self._backend
