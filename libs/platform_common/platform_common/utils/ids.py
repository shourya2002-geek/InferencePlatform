"""Identifier generation.

Trace IDs are 16-byte hex (W3C trace-context compatible) so they line up with
OpenTelemetry spans. Request/batch ids are short, sortable-ish, and human
greppable in logs.
"""

from __future__ import annotations

import secrets
import time


def new_trace_id() -> str:
    """128-bit hex trace id, compatible with W3C ``traceparent``."""
    return secrets.token_hex(16)


def new_request_id() -> str:
    return f"req_{int(time.time() * 1000):x}_{secrets.token_hex(4)}"


def new_batch_id() -> str:
    return f"batch_{int(time.time() * 1000):x}_{secrets.token_hex(3)}"
