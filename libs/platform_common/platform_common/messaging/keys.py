"""Centralized Redis key naming.

One place to see every key the platform touches. Consistent prefixes make it
trivial to inspect (`redis-cli --scan --pattern 'pip:*'`) and to set up
key-space eviction policies in production.
"""

from __future__ import annotations

PREFIX = "pip"  # pytorch inference platform


class Keys:
    # gateway -> scheduler: durable request stream + its consumer group
    REQUEST_STREAM = f"{PREFIX}:requests"
    SCHEDULER_GROUP = "schedulers"

    # scheduler -> worker: reliable batch work queue
    BATCH_QUEUE = f"{PREFIX}:batches"

    @staticmethod
    def batch_processing(worker_id: str) -> str:
        """Per-worker in-flight list used for at-least-once + crash recovery."""
        return f"{PREFIX}:batches:processing:{worker_id}"

    WORKER_HEARTBEAT = f"{PREFIX}:workers:heartbeat"  # hash worker_id -> ts

    @staticmethod
    def image(request_id: str) -> str:
        return f"{PREFIX}:image:{request_id}"

    @staticmethod
    def result(request_id: str) -> str:
        return f"{PREFIX}:result:{request_id}"

    # metrics service reads aggregate counters published by the data plane
    METRICS_SNAPSHOT = f"{PREFIX}:metrics:snapshot"
