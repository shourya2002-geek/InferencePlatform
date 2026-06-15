"""Generate model artifacts (TorchScript + ONNX) for v1/v2/v3 and a catalog.json.

This is the offline "model packaging" step a CI pipeline would run to promote a
trained checkpoint into a servable artifact. Requires the ML extras
(``pip install -e ".[ml]"``). Without torch it writes a stub catalog so the
platform still runs on the StubBackend.

    python scripts/build_models.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ARTIFACT_DIR = Path(os.getenv("MODEL_ARTIFACT_DIR", "models/artifacts"))
VERSIONS = {
    "v1": {"width": 16, "depth": 2},
    "v2": {"width": 32, "depth": 3},
    "v3": {"width": 48, "depth": 4},
}
NUM_CLASSES = 1000
SIZE = 224


def _write_catalog(entries: list[dict], latest: str) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = {"models": entries, "latest": {"resnet": latest}}
    (ARTIFACT_DIR / "catalog.json").write_text(json.dumps(catalog, indent=2))
    print(f"wrote {ARTIFACT_DIR / 'catalog.json'}")


def main() -> None:
    try:
        import torch

        from services.inference_worker.infrastructure.backends.model_def import (
            build_module,
        )
    except ImportError:
        print("[stub] torch not installed — writing a catalog without artifacts.")
        _write_catalog(
            [
                {"name": "resnet", "version": v, **cfg, "num_classes": NUM_CLASSES}
                for v, cfg in VERSIONS.items()
            ],
            latest="v3",
        )
        return

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for version, cfg in VERSIONS.items():
        module = build_module(width=cfg["width"], depth=cfg["depth"], num_classes=NUM_CLASSES)
        module.eval()
        example = torch.randn(1, 3, SIZE, SIZE)

        # TorchScript
        ts_path = ARTIFACT_DIR / f"resnet_{version}.ts"
        with torch.no_grad():
            traced = torch.jit.trace(module, example)
        traced = torch.jit.optimize_for_inference(traced)
        traced.save(str(ts_path))

        # ONNX
        onnx_path = ARTIFACT_DIR / f"resnet_{version}.onnx"
        torch.onnx.export(
            module, example, str(onnx_path),
            input_names=["input"], output_names=["logits"],
            dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
            opset_version=17,
        )
        print(f"built resnet:{version} -> {ts_path.name}, {onnx_path.name}")
        entries.append(
            {
                "name": "resnet", "version": version, **cfg,
                "num_classes": NUM_CLASSES, "input_size": SIZE,
                # default artifact is TorchScript; ONNX backend will look for .onnx
                "artifact": f"resnet_{version}.ts",
                "optimizations": ["eval", "no_grad", "torchscript"],
            }
        )
    _write_catalog(entries, latest="v3")


if __name__ == "__main__":
    main()
