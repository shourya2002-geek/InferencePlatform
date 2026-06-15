"""Benchmark: PyTorch inference-optimization techniques.

Measures latency (and, where cheap to obtain, parameter/memory footprint) for:

    1. baseline    — train() mode, autograd ON (the accidental worst case)
    2. eval()      — eval mode, autograd still on
    3. no_grad     — eval + torch.no_grad()
    4. inference_mode — eval + torch.inference_mode() (strongest)
    5. torchscript — traced + optimize_for_inference
    6. amp (cuda)  — autocast fp16 (only meaningful on GPU)
    7. quantized   — dynamic int8 (CPU)
    8. onnx        — exported graph on ONNX Runtime

Requires the ML extras: ``pip install -e ".[ml]"``. Without torch it prints a
clear message and exits 0 (so CI without GPUs stays green).

    python benchmarks/pytorch_optimizations.py
"""

from __future__ import annotations

import os
import time

from _bench_common import summarize, table_header

BATCH = int(os.getenv("BENCH_BATCH", "16"))
ITERS = int(os.getenv("BENCH_ITERS", "50"))
SIZE = 224


def _require_torch():
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        print(
            "\n[skip] PyTorch is not installed. Install the ML extras to run this "
            'benchmark:\n    pip install -e ".[ml]"\n'
        )
        return False


def _time_iters(label: str, fn, warmup: int = 5):  # type: ignore[no-untyped-def]
    for _ in range(warmup):
        fn()
    lat: list[float] = []
    t0 = time.perf_counter()
    for _ in range(ITERS):
        s = time.perf_counter()
        fn()
        lat.append((time.perf_counter() - s) * 1000)
    return summarize(label, lat, time.perf_counter() - t0)


def main() -> None:
    if not _require_torch():
        return
    import numpy as np
    import torch

    from services.inference_worker.domain.catalog import ModelCatalog
    from services.inference_worker.infrastructure.backends.model_def import build_module

    device = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    spec = ModelCatalog().resolve("resnet", os.getenv("DEFAULT_MODEL_VERSION", "v2"))
    x = torch.randn(BATCH, 3, SIZE, SIZE, device=device)

    def fresh():  # build a model with the spec's capacity
        module = build_module(
            width=spec.width, depth=spec.depth, num_classes=spec.num_classes
        )
        return module.to(device)

    results = []

    # 1. baseline: train mode, grad on
    m = fresh()
    m.train()
    results.append(_time_iters("1. baseline train()+grad", lambda: m(x).sum().backward()))

    # 2. eval, grad on
    m2 = fresh()
    m2.eval()
    results.append(_time_iters("2. eval()", lambda: m2(x)))

    # 3. eval + no_grad
    def f3():
        with torch.no_grad():
            m2(x)
    results.append(_time_iters("3. eval()+no_grad", f3))

    # 4. inference_mode
    def f4():
        with torch.inference_mode():
            m2(x)
    results.append(_time_iters("4. inference_mode", f4))

    # 5. torchscript
    with torch.no_grad():
        traced = torch.jit.trace(m2, torch.randn(BATCH, 3, SIZE, SIZE, device=device))
        traced = torch.jit.optimize_for_inference(traced)

    def f5():
        with torch.inference_mode():
            traced(x)
    results.append(_time_iters("5. torchscript", f5))

    # 6. AMP (cuda only)
    if device.startswith("cuda"):
        def f6():
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.float16):
                m2(x)
        results.append(_time_iters("6. amp fp16 (cuda)", f6))
    else:
        print("[note] skipping AMP — no CUDA device.")

    # 7. dynamic quantization (CPU)
    if device == "cpu":
        qm = torch.quantization.quantize_dynamic(
            fresh().eval(), {torch.nn.Linear}, dtype=torch.qint8
        )

        def f7():
            with torch.inference_mode():
                qm(x)
        results.append(_time_iters("7. dynamic int8 (cpu)", f7))

    # 8. ONNX Runtime
    try:
        import onnxruntime as ort  # noqa: F401

        onnx_path = "/tmp/pip_bench_model.onnx"
        torch.onnx.export(
            m2, torch.randn(1, 3, SIZE, SIZE, device=device), onnx_path,
            input_names=["input"], output_names=["logits"],
            dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
            opset_version=17,
        )
        sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        xn = x.detach().cpu().numpy().astype(np.float32)
        results.append(_time_iters("8. onnxruntime (cpu)", lambda: sess.run(None, {"input": xn})))
    except ImportError:
        print("[note] skipping ONNX — onnxruntime not installed.")

    print(f"\nPyTorch optimization benchmark — device={device} batch={BATCH} iters={ITERS}\n")
    print(table_header())
    for r in results:
        print(r.as_row())
    print(
        "\nReading the table: each step removes overhead the previous left in.\n"
        "eval() fixes correctness (BatchNorm/dropout); no_grad/inference_mode drop\n"
        "the autograd tape (memory + time); TorchScript fuses ops; AMP halves matmul\n"
        "cost on GPU; quantization shrinks + speeds CPU Linear layers; ONNX RT often\n"
        "wins on CPU via aggressive graph optimization.\n"
    )


if __name__ == "__main__":
    main()
