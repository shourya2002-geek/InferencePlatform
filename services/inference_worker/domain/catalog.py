"""Model catalog — the source of truth for which (name, version) specs exist.

In a real platform this would be a model registry service backed by a database
or MLflow/S3. Here it is a small in-code catalog (optionally overlaid by
``models/catalog.json``) so the demo ships with v1/v2/v3 out of the box.
"""

from __future__ import annotations

import json
from pathlib import Path

from platform_common.errors import ModelNotFoundError

from services.inference_worker.domain.runtime import ModelSpec

# Built-in catalog: three versions of a "resnet"-ish classifier that grow in
# capacity. Latency should increase v1 < v2 < v3.
_BUILTIN: dict[str, ModelSpec] = {
    "resnet:v1": ModelSpec(
        name="resnet", version="v1", width=16, depth=2,
        optimizations=("eval", "no_grad"),
    ),
    "resnet:v2": ModelSpec(
        name="resnet", version="v2", width=32, depth=3,
        optimizations=("eval", "no_grad"),
    ),
    "resnet:v3": ModelSpec(
        name="resnet", version="v3", width=48, depth=4,
        optimizations=("eval", "no_grad"),
    ),
}

# Logical "latest" alias per model name (think: the version a deploy promotes).
_LATEST: dict[str, str] = {"resnet": "v3"}


class ModelCatalog:
    def __init__(self, artifact_dir: str | None = None) -> None:
        self._specs: dict[str, ModelSpec] = dict(_BUILTIN)
        self._latest: dict[str, str] = dict(_LATEST)
        if artifact_dir:
            self._overlay_from_disk(Path(artifact_dir))

    def _overlay_from_disk(self, artifact_dir: Path) -> None:
        """Optionally enrich specs with on-disk artifact paths (.ts/.onnx)."""
        catalog_file = artifact_dir / "catalog.json"
        if not catalog_file.exists():
            return
        data = json.loads(catalog_file.read_text())
        for entry in data.get("models", []):
            spec = ModelSpec(
                name=entry["name"],
                version=entry["version"],
                num_classes=entry.get("num_classes", 1000),
                input_size=entry.get("input_size", 224),
                width=entry.get("width", 32),
                depth=entry.get("depth", 3),
                artifact_path=(
                    str(artifact_dir / entry["artifact"])
                    if entry.get("artifact")
                    else None
                ),
                optimizations=tuple(entry.get("optimizations", ())),
            )
            self._specs[spec.key] = spec
        for name, version in data.get("latest", {}).items():
            self._latest[name] = version

    def resolve(self, name: str, version: str | None) -> ModelSpec:
        """Resolve (name, version|None) to a concrete spec.

        ``version=None`` means "latest" — the version a client gets when it
        doesn't pin one, which is how zero-downtime promotion works.
        """
        if version is None:
            version = self._latest.get(name)
            if version is None:
                raise ModelNotFoundError(f"no 'latest' configured for model '{name}'")
        spec = self._specs.get(f"{name}:{version}")
        if spec is None:
            raise ModelNotFoundError(f"unknown model '{name}:{version}'")
        return spec

    def set_latest(self, name: str, version: str) -> None:
        """Promote a version to 'latest' (used by hot-reload / canary cutover)."""
        if f"{name}:{version}" not in self._specs:
            raise ModelNotFoundError(f"cannot promote unknown '{name}:{version}'")
        self._latest[name] = version

    def versions(self, name: str) -> list[str]:
        return sorted(s.version for s in self._specs.values() if s.name == name)
