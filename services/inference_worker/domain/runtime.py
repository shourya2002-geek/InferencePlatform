"""Runtime backend contract (domain port).

The domain defines *what* an inference runtime must do; infrastructure provides
the *how* (stub / torch-eager / torchscript / onnx). Everything flows as NumPy
NCHW float32 in and (N, num_classes) logits out, so the rest of the worker is
backend-agnostic and the benchmark harness can compare backends apples-to-apples.

This is the Dependency Inversion seam: the worker loop, registry and executor
depend only on these abstractions, never on torch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Immutable description of one (name, version) of a model.

    Versions deliberately differ in capacity (``width``/``depth``) so v1/v2/v3
    have measurably different latency — that is what makes hot-reload and
    per-version metrics interesting to demo.
    """

    name: str
    version: str
    num_classes: int = 1000
    input_size: int = 224
    width: int = 32
    depth: int = 3
    # path to a serialized artifact (.ts for TorchScript, .onnx for ONNX);
    # None means "build the model in-process from this spec" (stub / eager).
    artifact_path: str | None = None
    optimizations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass(slots=True)
class LoadedModel:
    """A model that is resident and ready to serve."""

    spec: ModelSpec
    handle: object  # backend-specific (nn.Module, ScriptModule, ort.Session, ndarray)
    backend: str
    device: str
    loaded_at: float
    warmup_done: bool = False


@runtime_checkable
class RuntimeBackend(Protocol):
    """Port implemented by every concrete runtime."""

    name: str

    def load(self, spec: ModelSpec, *, device: str) -> LoadedModel:
        """Materialize a model for serving (may read an artifact from disk)."""
        ...

    def warmup(self, model: LoadedModel, *, batch_size: int) -> None:
        """Run a throwaway forward pass to JIT/allocate/cudnn-autotune.

        The first inference is always slow (lazy CUDA init, cudnn algorithm
        search, JIT specialization). Warming up moves that cost out of the first
        real request's latency.
        """
        ...

    def infer(self, model: LoadedModel, batch: np.ndarray) -> np.ndarray:
        """Run a forward pass. ``batch`` is NCHW float32; returns (N, classes)."""
        ...

    def unload(self, model: LoadedModel) -> None:
        """Release resources (free GPU memory)."""
        ...
