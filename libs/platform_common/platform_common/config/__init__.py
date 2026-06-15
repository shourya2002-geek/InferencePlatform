"""Typed configuration loaded from the environment.

Every service constructs exactly one settings object at startup and passes it
down via dependency injection — no module ever reaches into ``os.environ``
directly. This makes configuration testable (just instantiate with overrides)
and keeps the 12-factor "config in the environment" contract.
"""

from platform_common.config.settings import (
    BaseServiceSettings,
    GatewaySettings,
    MetricsSettings,
    SchedulerSettings,
    WorkerSettings,
)

__all__ = [
    "BaseServiceSettings",
    "GatewaySettings",
    "MetricsSettings",
    "SchedulerSettings",
    "WorkerSettings",
]
