"""PyTorch runtime backend — eager and TorchScript, with optional AMP/quant.

This is where the inference-optimization techniques from the talk are applied to
a serving path (the standalone, benchmarked demos live in
``benchmarks/pytorch_optimizations.py``):

* ``model.eval()``        — disables dropout / uses running BatchNorm stats.
* ``torch.no_grad()``     — no autograd graph → less memory, faster.
* ``torch.inference_mode()`` — stronger than no_grad for pure inference.
* **TorchScript** (``torch.jit.script``/``trace`` + ``optimize_for_inference``)
  — freezes the graph, fuses ops, removes Python overhead.
* **Mixed precision** (``torch.autocast``) — fp16/bf16 matmuls on capable HW.
* **Dynamic quantization** (``quantize_dynamic``) — int8 Linear layers, smaller
  + faster on CPU.

Torch is imported lazily so the control plane never pays for it.
"""

from __future__ import annotations

import time

import numpy as np
from platform_common.errors import RuntimeBackendError
from platform_common.observability import get_logger

from services.inference_worker.domain.runtime import LoadedModel, ModelSpec
from services.inference_worker.infrastructure.backends.model_def import build_module

log = get_logger("torch_backend")


class TorchBackend:
    """Eager or scripted PyTorch backend.

    Parameters
    ----------
    scripted: compile the module with TorchScript + optimize_for_inference.
    mixed_precision: run the forward pass under autocast.
    quantize: apply dynamic int8 quantization (CPU).
    """

    def __init__(
        self,
        *,
        scripted: bool = False,
        mixed_precision: bool = False,
        quantize: bool = False,
    ) -> None:
        self.scripted = scripted
        self.mixed_precision = mixed_precision
        self.quantize = quantize
        self.name = "torchscript" if scripted else "torch_eager"

    def load(self, spec: ModelSpec, *, device: str) -> LoadedModel:
        import torch

        module = build_module(
            width=spec.width, depth=spec.depth, num_classes=spec.num_classes
        )

        # If a serialized TorchScript artifact exists, prefer it (this is how a
        # real deploy ships a frozen, version-pinned graph).
        if spec.artifact_path and spec.artifact_path.endswith(".ts"):
            module = torch.jit.load(spec.artifact_path, map_location=device)
        else:
            module.eval()  # (1) eval mode — critical before serving
            if self.quantize:
                module = torch.quantization.quantize_dynamic(
                    module, {torch.nn.Linear}, dtype=torch.qint8
                )
            module = module.to(device)
            if self.scripted:
                # (2) TorchScript freeze + inference optimization.
                example = torch.zeros(
                    1, 3, spec.input_size, spec.input_size, device=device
                )
                with torch.no_grad():
                    module = torch.jit.trace(module, example)
                module = torch.jit.optimize_for_inference(module)

        return LoadedModel(
            spec=spec,
            handle=module,
            backend=self.name,
            device=device,
            loaded_at=time.time(),
        )

    def warmup(self, model: LoadedModel, *, batch_size: int) -> None:
        dummy = np.zeros(
            (batch_size, 3, model.spec.input_size, model.spec.input_size), np.float32
        )
        # A couple of passes: trigger cudnn autotune / JIT specialization.
        for _ in range(2):
            self.infer(model, dummy)

    def infer(self, model: LoadedModel, batch: np.ndarray) -> np.ndarray:
        import torch

        if batch.ndim != 4:
            raise RuntimeBackendError(f"expected NCHW, got {batch.shape}")
        device = model.device
        module = model.handle
        x = torch.from_numpy(np.ascontiguousarray(batch)).to(device)

        # (3) inference_mode: the strongest "no autograd" context for serving.
        with torch.inference_mode():
            if self.mixed_precision and device.startswith("cuda"):
                # (4) AMP: fp16 matmuls where it's numerically safe.
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    logits = module(x)
            else:
                logits = module(x)
        return logits.detach().to("cpu", dtype=torch.float32).numpy()

    def unload(self, model: LoadedModel) -> None:
        import torch

        model.handle = None
        if model.device.startswith("cuda"):
            torch.cuda.empty_cache()
