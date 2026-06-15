"""ONNX Runtime backend (comparison module).

ONNX Runtime is often the fastest CPU inference path and a portable target
(same graph runs on CPU/CUDA/TensorRT/CoreML execution providers). Here it loads
a ``.onnx`` artifact produced by ``scripts/build_models.py`` (which exports the
torch model via ``torch.onnx.export``).

If no artifact exists for a spec we raise a clear error rather than silently
falling back — surfacing "this version wasn't exported to ONNX" is the honest
behavior for a serving system.
"""

from __future__ import annotations

import time

import numpy as np
from platform_common.errors import ModelNotFoundError, RuntimeBackendError

from services.inference_worker.domain.runtime import LoadedModel, ModelSpec


class OnnxBackend:
    name = "onnx"

    def __init__(self, *, device: str = "cpu") -> None:
        self._providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if device.startswith("cuda")
            else ["CPUExecutionProvider"]
        )

    def load(self, spec: ModelSpec, *, device: str) -> LoadedModel:
        import onnxruntime as ort

        if not spec.artifact_path or not spec.artifact_path.endswith(".onnx"):
            raise ModelNotFoundError(
                f"no .onnx artifact for {spec.key}; run scripts/build_models.py"
            )
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )
        session = ort.InferenceSession(
            spec.artifact_path, sess_options, providers=self._providers
        )
        return LoadedModel(
            spec=spec,
            handle=session,
            backend=self.name,
            device=device,
            loaded_at=time.time(),
        )

    def warmup(self, model: LoadedModel, *, batch_size: int) -> None:
        dummy = np.zeros(
            (batch_size, 3, model.spec.input_size, model.spec.input_size), np.float32
        )
        self.infer(model, dummy)

    def infer(self, model: LoadedModel, batch: np.ndarray) -> np.ndarray:
        if batch.ndim != 4:
            raise RuntimeBackendError(f"expected NCHW, got {batch.shape}")
        session = model.handle
        input_name = session.get_inputs()[0].name  # type: ignore[union-attr]
        outputs = session.run(None, {input_name: batch.astype(np.float32)})  # type: ignore[union-attr]
        return np.asarray(outputs[0], dtype=np.float32)

    def unload(self, model: LoadedModel) -> None:
        model.handle = None
