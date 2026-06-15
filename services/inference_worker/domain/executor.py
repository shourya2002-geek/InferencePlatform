"""BatchExecutor — turns one BatchEnvelope into N InferenceResults.

This is the pure orchestration of a batch: decode → stack → infer → softmax →
top-k → split back per request, all while recording the latency breakdown that
makes the platform observable. It depends only on the registry and runtime
*abstractions*, so it runs identically on the stub or the real torch backend.
"""

from __future__ import annotations

import time

import numpy as np
from platform_common.observability import get_logger
from platform_common.schemas import (
    BatchEnvelope,
    ClassPrediction,
    InferenceRequest,
    InferenceResult,
    RequestStatus,
)
from platform_common.utils.images import decode_to_chw, stack_batch
from platform_common.utils.timing import now_ms

from services.inference_worker.domain.labels import label_for
from services.inference_worker.domain.registry import ModelRegistry

log = get_logger("executor")


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class BatchExecutor:
    def __init__(self, registry: ModelRegistry, *, worker_id: str) -> None:
        self._registry = registry
        self._worker_id = worker_id

    async def execute(
        self, batch: BatchEnvelope, images: dict[str, bytes | None]
    ) -> list[InferenceResult]:
        model = await self._registry.get(batch.model_name, batch.model_version)

        # --- preprocessing: decode each image; per-item failures are isolated.
        decoded: list[np.ndarray] = []
        kept: list[InferenceRequest] = []
        failures: list[InferenceResult] = []
        for req in batch.requests:
            raw = images.get(req.request_id)
            if raw is None:
                failures.append(
                    InferenceResult.failure(
                        req, RequestStatus.ERROR, "image missing/expired in store"
                    )
                )
                continue
            try:
                decoded.append(decode_to_chw(raw, size=model.spec.input_size))
                kept.append(req)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    InferenceResult.failure(req, RequestStatus.ERROR, str(exc))
                )

        if not kept:
            return failures

        tensor = stack_batch(decoded)  # NCHW

        # --- inference: the one forward pass shared by the whole batch.
        infer_start = now_ms()
        logits = await self._infer(model, tensor)
        infer_ms = now_ms() - infer_start

        probs = _softmax(logits)
        now = time.time()
        results: list[InferenceResult] = list(failures)
        # latency attribution is identical for every item in the batch's compute,
        # but queue/batch-wait differ per request based on when it was enqueued.
        per_item_infer_ms = infer_ms  # whole-batch cost; report as the batch cost
        for i, req in enumerate(kept):
            preds = self._topk(probs[i], req.top_k)
            queue_ms = max(0.0, (batch.formed_at - req.enqueued_at) * 1000.0)
            total_ms = max(0.0, (now - req.enqueued_at) * 1000.0)
            results.append(
                InferenceResult(
                    request_id=req.request_id,
                    trace_id=req.trace_id,
                    status=RequestStatus.OK,
                    model_name=model.spec.name,
                    model_version=model.spec.version,
                    predictions=preds,
                    batch_id=batch.batch_id,
                    batch_size=batch.size,
                    worker_id=self._worker_id,
                    queue_time_ms=queue_ms,
                    batch_wait_ms=batch.batch_wait_ms,
                    inference_time_ms=per_item_infer_ms,
                    total_time_ms=total_ms,
                )
            )
        return results

    async def _infer(self, model, tensor: np.ndarray) -> np.ndarray:  # type: ignore[no-untyped-def]
        # Backend forward passes are CPU/GPU-bound and may hold the GIL; run in a
        # worker thread so the asyncio loop stays responsive (heartbeats, etc.).
        import asyncio

        return await asyncio.to_thread(self._registry.backend.infer, model, tensor)

    @staticmethod
    def _topk(prob_row: np.ndarray, k: int) -> list[ClassPrediction]:
        k = min(k, prob_row.shape[0])
        idx = np.argpartition(prob_row, -k)[-k:]
        idx = idx[np.argsort(prob_row[idx])[::-1]]
        return [
            ClassPrediction(label=label_for(int(i)), index=int(i), score=float(prob_row[i]))
            for i in idx
        ]
