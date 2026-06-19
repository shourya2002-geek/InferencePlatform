"""Pydantic-settings models, one per service plus a shared base.

Field names map to UPPER_SNAKE env vars (pydantic-settings is case-insensitive).
Prefixes namespace each service's settings so a single ``.env`` can configure
the whole stack without collisions.
"""

from __future__ import annotations

import socket
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Settings every service shares: infra endpoints + observability."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    redis_url: str = "redis://localhost:6379/0"
    otel_exporter_otlp_endpoint: str | None = None
    otel_traces_exporter: str = "none"  # "otlp" to actually export, "none" for local
    log_level: str = "INFO"
    environment: str = "local"
    service_name: str = "service"


class GatewaySettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_", env_file=".env", extra="ignore"
    )

    service_name: str = "api-gateway"
    host: str = "0.0.0.0"
    port: int = 8080
    # NoDecode: keep pydantic-settings from JSON-parsing the env value so the
    # comma-splitting validator below can accept "k1,k2,k3".
    api_keys: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["demo-key-staff"]
    )
    rate_limit_rps: float = 200.0
    rate_limit_burst: int = 400
    request_timeout_ms: int = 2000
    max_image_bytes: int = 5 * 1024 * 1024
    circuit_fail_threshold: int = 20
    circuit_reset_seconds: float = 10.0
    # Each in-flight request holds one Redis connection for its blocking result
    # wait (BLPOP), so the connection-pool size *is* the gateway's max concurrent
    # in-flight bound. Beyond it we shed load with 503 rather than 500.
    max_inflight_requests: int = 1024

    @field_validator("api_keys", mode="before")
    @classmethod
    def _split_keys(cls, v: object) -> object:
        # Allow a comma-separated string in the env var.
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v


class SchedulerSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCHEDULER_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,  # allow max_batch_size=... kwargs despite aliases
    )

    service_name: str = "scheduler"
    host: str = "0.0.0.0"
    port: int = 8085  # health + /metrics surface
    strategy: str = "priority"  # fifo | priority | weighted
    # Accept both the bare MAX_BATCH_SIZE/MAX_WAIT_MS (as in the spec/.env) and
    # the SCHEDULER_-prefixed forms.
    max_batch_size: int = Field(
        default=32,
        validation_alias=AliasChoices("MAX_BATCH_SIZE", "SCHEDULER_MAX_BATCH_SIZE"),
    )
    max_wait_ms: int = Field(
        default=10,
        validation_alias=AliasChoices("MAX_WAIT_MS", "SCHEDULER_MAX_WAIT_MS"),
    )
    queue_maxlen: int = 50_000
    num_priority_levels: int = 3
    class_weights: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: [8, 3, 1]
    )

    @field_validator("class_weights", mode="before")
    @classmethod
    def _split_weights(cls, v: object) -> object:
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        return v


class WorkerSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORKER_", env_file=".env", extra="ignore"
    )

    service_name: str = "inference-worker"
    # Unique per replica by default (container hostname) so heartbeats/processing
    # lists don't collide when scaling `docker compose up --scale`. WORKER_ID env
    # overrides for stable, human-friendly ids.
    worker_id: str = Field(default_factory=lambda: f"worker-{socket.gethostname()}")
    concurrency: int = 1
    batch_timeout_ms: int = 5000
    host: str = "0.0.0.0"
    port: int = 8090  # health + /metrics + model-management HTTP surface

    # Runtime/model knobs live without the WORKER_ prefix in .env, so we read
    # them explicitly here via validation_alias-free fields with defaults that
    # the bootstrap layer overrides from RuntimeSettings (below).


class RuntimeSettings(BaseServiceSettings):
    """Model-runtime configuration (kept separate from worker plumbing)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    runtime_backend: str = "stub"  # stub | torch_eager | torchscript | onnx
    device: str = "cpu"
    default_model: str = "resnet"
    default_model_version: str = "v2"
    model_artifact_dir: str = "./models/artifacts"
    model_cache_size: int = 4
    enable_mixed_precision: bool = False
    enable_quantization: bool = False


class MetricsSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        env_prefix="METRICS_", env_file=".env", extra="ignore"
    )

    service_name: str = "metrics"
    host: str = "0.0.0.0"
    port: int = 9000
