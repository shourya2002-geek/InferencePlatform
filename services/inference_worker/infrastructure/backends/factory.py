"""Backend factory — the Factory Pattern that decouples config from runtime.

The worker asks for a backend by name; this module knows how to build each one
and which optional dependency it needs. Adding a new runtime (e.g. TensorRT) is
a one-line registration here, with zero changes to the worker loop.
"""

from __future__ import annotations

from platform_common.errors import RuntimeBackendError

from services.inference_worker.domain.runtime import RuntimeBackend


def build_backend(
    backend: str,
    *,
    device: str = "cpu",
    mixed_precision: bool = False,
    quantize: bool = False,
) -> RuntimeBackend:
    backend = backend.lower()

    if backend == "stub":
        from services.inference_worker.infrastructure.backends.stub_backend import (
            StubBackend,
        )

        return StubBackend()

    if backend in {"torch_eager", "torch"}:
        from services.inference_worker.infrastructure.backends.torch_backend import (
            TorchBackend,
        )

        return TorchBackend(
            scripted=False, mixed_precision=mixed_precision, quantize=quantize
        )

    if backend == "torchscript":
        from services.inference_worker.infrastructure.backends.torch_backend import (
            TorchBackend,
        )

        return TorchBackend(
            scripted=True, mixed_precision=mixed_precision, quantize=quantize
        )

    if backend == "onnx":
        from services.inference_worker.infrastructure.backends.onnx_backend import (
            OnnxBackend,
        )

        return OnnxBackend(device=device)

    raise RuntimeBackendError(
        f"unknown runtime backend '{backend}' "
        "(expected: stub | torch_eager | torchscript | onnx)"
    )
