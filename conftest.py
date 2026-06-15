"""Shared pytest fixtures.

A fakeredis-backed async client lets the integration tests exercise the real
messaging code (streams, reliable lists, result mailboxes) with no external
Redis. Pure-domain tests (batcher, strategies, backends) need none of this.
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image


@pytest.fixture
async def fake_redis():
    import fakeredis.aioredis

    client = fakeredis.aioredis.FakeRedis()
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def sample_image_bytes() -> bytes:
    """A small valid PNG for upload/decoding tests."""
    arr = (np.random.default_rng(0).random((32, 32, 3)) * 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()
