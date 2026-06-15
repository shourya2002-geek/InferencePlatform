"""Redis-backed transports for each hop of the request lifecycle.

Design choices worth calling out for reviewers:

* **Streams for ingest, lists for dispatch.** The gateway->scheduler hop uses a
  Redis Stream with a consumer group: it gives at-least-once semantics, a
  bounded MAXLEN for backpressure, and replay if the scheduler dies mid-batch.
  The scheduler->worker hop uses a *reliable list* (``BLMOVE`` into a per-worker
  processing list) because batches are short-lived units of work that want
  cheap work-stealing across a worker pool, plus explicit crash recovery.

* **Result delivery via a per-request list.** The gateway blocks on
  ``BLPOP pip:result:{id}``. This is a one-shot mailbox: O(1), self-cleaning via
  TTL, and avoids pub/sub's "no subscriber == lost message" race.

* **Images live in a content store**, keyed by request id, never inside queue
  messages. Queues stay small and the scheduler can hold tens of thousands of
  pending requests in memory.
"""

from __future__ import annotations

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from platform_common.errors import QueueOverflowError
from platform_common.messaging.keys import Keys
from platform_common.schemas import BatchEnvelope, InferenceRequest, InferenceResult

# TTLs (seconds). Generous enough to absorb retries, short enough to self-clean.
_IMAGE_TTL = 60
_RESULT_TTL = 60


class ImageStore:
    """Content-addressed-ish store for raw upload bytes."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def put(self, request_id: str, data: bytes, ttl: int = _IMAGE_TTL) -> str:
        key = Keys.image(request_id)
        await self._redis.set(key, data, ex=ttl)
        return key

    async def get(self, request_id: str) -> bytes | None:
        return await self._redis.get(Keys.image(request_id))

    async def delete(self, request_id: str) -> None:
        await self._redis.delete(Keys.image(request_id))


class RequestStream:
    """Durable gateway -> scheduler ingest queue (Redis Stream + group)."""

    def __init__(self, redis: aioredis.Redis, *, maxlen: int = 50_000) -> None:
        self._redis = redis
        self._maxlen = maxlen

    async def ensure_group(self) -> None:
        """Create the consumer group if it does not exist (idempotent)."""
        try:
            await self._redis.xgroup_create(
                Keys.REQUEST_STREAM, Keys.SCHEDULER_GROUP, id="0", mkstream=True
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, request: InferenceRequest) -> str:
        """Append a request. Enforces backpressure via approximate MAXLEN.

        If the stream is already at/over capacity we reject *new* work rather
        than let the queue grow unbounded — shedding load is how you keep tail
        latency bounded under overload.
        """
        depth = await self._redis.xlen(Keys.REQUEST_STREAM)
        if depth >= self._maxlen:
            raise QueueOverflowError(
                f"request queue full ({depth} >= {self._maxlen})"
            )
        msg_id = await self._redis.xadd(
            Keys.REQUEST_STREAM,
            {"payload": request.model_dump_json()},
            maxlen=self._maxlen,
            approximate=True,
        )
        return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)

    async def consume(
        self, consumer: str, *, count: int, block_ms: int
    ) -> list[tuple[str, InferenceRequest]]:
        """Read a batch of pending requests for this consumer.

        Returns ``(stream_msg_id, request)`` pairs. The caller must
        :meth:`ack` each id once it has been durably handed to a worker batch.
        """
        resp = await self._redis.xreadgroup(
            Keys.SCHEDULER_GROUP,
            consumer,
            {Keys.REQUEST_STREAM: ">"},
            count=count,
            block=block_ms,
        )
        out: list[tuple[str, InferenceRequest]] = []
        if not resp:
            return out
        for _stream, entries in resp:
            for msg_id, fields in entries:
                raw = fields[b"payload"]
                req = InferenceRequest.model_validate_json(raw)
                mid = msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                out.append((mid, req))
        return out

    async def ack(self, *msg_ids: str) -> None:
        if msg_ids:
            await self._redis.xack(
                Keys.REQUEST_STREAM, Keys.SCHEDULER_GROUP, *msg_ids
            )

    async def depth(self) -> int:
        return int(await self._redis.xlen(Keys.REQUEST_STREAM))


class BatchQueue:
    """Reliable scheduler -> worker dispatch queue.

    ``dispatch`` LPUSHes a batch envelope. ``reserve`` atomically moves one
    batch to a per-worker processing list (``BLMOVE``) so an in-flight batch is
    never lost if the worker crashes; ``complete`` removes it once the result is
    written. ``recover_orphans`` re-queues anything stranded in a dead worker's
    processing list.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def dispatch(self, batch: BatchEnvelope) -> None:
        await self._redis.lpush(Keys.BATCH_QUEUE, batch.model_dump_json())

    async def reserve(self, worker_id: str, *, block_s: float) -> BatchEnvelope | None:
        processing = Keys.batch_processing(worker_id)
        raw = await self._redis.blmove(
            Keys.BATCH_QUEUE, processing, timeout=block_s, src="RIGHT", dest="LEFT"
        )
        if raw is None:
            return None
        return BatchEnvelope.model_validate_json(raw)

    async def complete(self, worker_id: str, batch: BatchEnvelope) -> None:
        # Remove exactly this batch from the processing list.
        await self._redis.lrem(
            Keys.batch_processing(worker_id), 1, batch.model_dump_json()
        )

    async def recover_orphans(self, worker_id: str) -> int:
        """Re-queue every batch stranded in a worker's processing list.

        Called on worker startup (recover *own* prior crash) and by a janitor
        for workers whose heartbeat has expired.
        """
        processing = Keys.batch_processing(worker_id)
        moved = 0
        while True:
            raw = await self._redis.lmove(
                processing, Keys.BATCH_QUEUE, src="LEFT", dest="LEFT"
            )
            if raw is None:
                break
            moved += 1
        return moved

    async def depth(self) -> int:
        return int(await self._redis.llen(Keys.BATCH_QUEUE))


class ResultBus:
    """Per-request reply mailbox (worker -> gateway)."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def publish(self, result: InferenceResult) -> None:
        key = Keys.result(result.request_id)
        # RPUSH + EXPIRE in a pipeline: the gateway BLPOPs the single element.
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.rpush(key, result.model_dump_json())
            pipe.expire(key, _RESULT_TTL)
            await pipe.execute()

    async def wait(self, request_id: str, *, timeout_s: float) -> InferenceResult | None:
        item = await self._redis.blpop([Keys.result(request_id)], timeout=timeout_s)
        if item is None:
            return None
        _key, raw = item
        return InferenceResult.model_validate_json(raw)
