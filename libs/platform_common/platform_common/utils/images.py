"""Image helpers shared by the gateway (validate) and worker (decode).

Pillow + NumPy are core dependencies (small, no GPU), so both the control plane
and data plane can rely on them. Decoding to a normalized NCHW float32 array is
the *preprocessing* step — the part of inference that is pure CPU and often the
hidden latency cost people forget when they say "the model only takes 3ms".
"""

from __future__ import annotations

import io

import numpy as np

# ImageNet normalization constants (channels-first).
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)


def validate_image_bytes(data: bytes, *, max_bytes: int) -> tuple[int, int]:
    """Cheaply verify the payload is a real, in-bounds image.

    Returns ``(width, height)``. Raises ``ValueError`` on anything malformed —
    the gateway maps that to HTTP 422 *before* the request ever touches a queue.
    """
    if not data:
        raise ValueError("empty image payload")
    if len(data) > max_bytes:
        raise ValueError(f"image exceeds {max_bytes} bytes")
    from PIL import Image  # local import keeps import cost off the hot path

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()  # structural check without full decode
            return img.size  # (width, height)
    except Exception as exc:  # noqa: BLE001 - normalize to ValueError
        raise ValueError(f"undecodable image: {exc}") from exc


def decode_to_chw(data: bytes, *, size: int = 224) -> np.ndarray:
    """Decode bytes -> normalized float32 CHW array (3, size, size)."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB").resize((size, size))
        arr = np.asarray(img, dtype=np.float32) / 255.0  # HWC
    chw = np.transpose(arr, (2, 0, 1))  # CHW
    return (chw - _MEAN) / _STD


def stack_batch(arrays: list[np.ndarray]) -> np.ndarray:
    """Stack CHW arrays into an NCHW batch tensor."""
    return np.stack(arrays, axis=0).astype(np.float32)
