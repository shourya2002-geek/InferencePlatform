"""Token-bucket and image-validation unit tests."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image
from platform_common.utils.images import decode_to_chw, stack_batch, validate_image_bytes

from services.api_gateway.domain.rate_limiter import TokenBucketRateLimiter


def _png() -> bytes:
    arr = (np.random.default_rng(1).random((20, 20, 3)) * 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_token_bucket_allows_burst_then_throttles():
    rl = TokenBucketRateLimiter(rate=0.0, burst=3)  # no refill, burst of 3
    assert rl.allow("k")[0]
    assert rl.allow("k")[0]
    assert rl.allow("k")[0]
    allowed, retry_after = rl.allow("k")
    assert not allowed
    assert retry_after >= 0


def test_token_bucket_isolated_per_key():
    rl = TokenBucketRateLimiter(rate=0.0, burst=1)
    assert rl.allow("a")[0]
    assert not rl.allow("a")[0]
    assert rl.allow("b")[0]  # different key has its own bucket


def test_validate_image_accepts_png():
    w, h = validate_image_bytes(_png(), max_bytes=1_000_000)
    assert (w, h) == (20, 20)


def test_validate_image_rejects_garbage():
    with pytest.raises(ValueError):
        validate_image_bytes(b"not-an-image", max_bytes=1_000_000)


def test_validate_image_rejects_oversize():
    with pytest.raises(ValueError):
        validate_image_bytes(_png(), max_bytes=10)


def test_decode_and_stack_shapes():
    chw = decode_to_chw(_png(), size=224)
    assert chw.shape == (3, 224, 224)
    batch = stack_batch([chw, chw])
    assert batch.shape == (2, 3, 224, 224)
