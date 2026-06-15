"""Shared helpers for the benchmark scripts: latency stats + synthetic inputs."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class LatencyStats:
    label: str
    count: int
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float

    def as_row(self) -> str:
        return (
            f"| {self.label:<28} | {self.rps:>8.1f} | {self.p50_ms:>7.2f} | "
            f"{self.p95_ms:>7.2f} | {self.p99_ms:>7.2f} | {self.mean_ms:>7.2f} |"
        )


def summarize(label: str, latencies_ms: list[float], wall_seconds: float) -> LatencyStats:
    n = len(latencies_ms)
    s = sorted(latencies_ms)

    def pct(p: float) -> float:
        if not s:
            return 0.0
        k = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
        return s[k]

    return LatencyStats(
        label=label,
        count=n,
        rps=(n / wall_seconds) if wall_seconds > 0 else 0.0,
        p50_ms=pct(50),
        p95_ms=pct(95),
        p99_ms=pct(99),
        mean_ms=statistics.fmean(latencies_ms) if latencies_ms else 0.0,
    )


def table_header() -> str:
    head = (
        "| Strategy                     |  req/s   |  p50ms  |  p95ms  |  p99ms  |  mean   |\n"
        "|------------------------------|----------|---------|---------|---------|---------|"
    )
    return head


def synthetic_nchw(batch: int, size: int = 224, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((batch, 3, size, size)).astype(np.float32)
