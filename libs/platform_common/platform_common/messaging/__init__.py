"""Redis-backed messaging primitives shared by all services.

We deliberately use Redis for *both* queueing and result delivery so the whole
platform runs from a single, ubiquitous dependency. The abstractions here hide
the exact Redis commands behind intention-revealing methods:

* :class:`RequestStream` — durable Redis **Stream** + consumer group; the
  gateway -> scheduler hop. Gives at-least-once delivery and replay.
* :class:`BatchQueue`    — reliable list queue (BLMOVE into a per-worker
  processing list); the scheduler -> worker hop with crash recovery.
* :class:`ResultBus`     — per-request reply list; the worker -> gateway hop.
* :class:`ImageStore`    — content store for raw image bytes (referenced by id).
"""

from platform_common.messaging.keys import Keys
from platform_common.messaging.queues import (
    BatchQueue,
    ImageStore,
    RequestStream,
    ResultBus,
)
from platform_common.messaging.redis_client import create_redis, ping_redis

__all__ = [
    "BatchQueue",
    "ImageStore",
    "Keys",
    "RequestStream",
    "ResultBus",
    "create_redis",
    "ping_redis",
]
