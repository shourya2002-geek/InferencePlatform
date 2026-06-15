"""Message contracts shared across services.

These models are the *seams* of the system. The gateway, scheduler and workers
never share Python objects directly — they exchange instances of these models
serialized to JSON through Redis. Keeping them here (and only here) guarantees a
single source of truth for the wire format.
"""

from platform_common.schemas.inference import (
    BatchEnvelope,
    ClassPrediction,
    InferenceRequest,
    InferenceResult,
    Priority,
    RequestStatus,
)

__all__ = [
    "BatchEnvelope",
    "ClassPrediction",
    "InferenceRequest",
    "InferenceResult",
    "Priority",
    "RequestStatus",
]
