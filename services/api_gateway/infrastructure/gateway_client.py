"""Adapter from the gateway to the Redis data plane.

Wraps the three messaging primitives the gateway touches (image store, request
stream, result bus) behind a single intention-revealing facade. The application
layer depends on *this*, not on Redis details — so the transport could be
swapped for gRPC/Kafka without touching the use-case.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from platform_common.messaging import ImageStore, RequestStream, ResultBus
from platform_common.schemas import InferenceRequest, InferenceResult


class GatewayDataPlaneClient:
    def __init__(self, redis: aioredis.Redis, *, queue_maxlen: int) -> None:
        self._images = ImageStore(redis)
        self._stream = RequestStream(redis, maxlen=queue_maxlen)
        self._results = ResultBus(redis)

    async def submit(self, request: InferenceRequest, image: bytes) -> None:
        """Store the image then publish the request.

        Order matters: the image must exist before a worker can possibly dequeue
        the request, otherwise the worker would see a missing image.
        """
        await self._images.put(request.request_id, image)
        try:
            await self._stream.publish(request)
        except Exception:
            # If enqueue fails (e.g. overflow), don't leave an orphan image.
            await self._images.delete(request.request_id)
            raise

    async def await_result(
        self, request_id: str, *, timeout_s: float
    ) -> InferenceResult | None:
        return await self._results.wait(request_id, timeout_s=timeout_s)

    async def request_stream_depth(self) -> int:
        return await self._stream.depth()
