"""Locust load test for the API Gateway.

Sends multipart image-classification requests with a valid API key and a random
priority, so the scheduler's priority/weighted strategies are exercised under
load. Includes a stepped load shape that ramps through ~100 → 500 → 1000 RPS so
you can watch the latency percentiles and queue-depth dashboards move at each tier.

Usage:
    # interactive UI
    locust -f loadtest/locustfile.py --host http://localhost:8080

    # headless, fixed users, CSV report
    locust -f loadtest/locustfile.py --host http://localhost:8080 \
        --headless -u 200 -r 50 -t 2m --csv benchmarks/results/load

    # stepped shape (uses StepLoadShape below)
    locust -f loadtest/locustfile.py --host http://localhost:8080 --headless \
        --csv benchmarks/results/stepped
"""

from __future__ import annotations

import io
import os
import random

from locust import HttpUser, LoadTestShape, between, events, task

API_KEY = os.getenv("GATEWAY_API_KEY", "demo-key-staff")
MODEL = os.getenv("LOAD_MODEL", "resnet")


def _make_png(seed: int) -> bytes:
    # Build a small valid PNG without numpy/PIL dependency at runtime if possible.
    try:
        import numpy as np
        from PIL import Image

        arr = (np.random.default_rng(seed).random((64, 64, 3)) * 255).astype("uint8")
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:  # 1x1 transparent PNG fallback
        import base64

        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )


# Pre-generate a small pool of images to avoid CPU cost dominating the client.
_IMAGE_POOL = [_make_png(i) for i in range(16)]


class ClassifyUser(HttpUser):
    """Simulates a client repeatedly classifying images."""

    wait_time = between(0.0, 0.05)

    @task
    def classify(self) -> None:
        image = random.choice(_IMAGE_POOL)
        priority = random.choices([0, 1, 2], weights=[1, 6, 3])[0]
        files = {"file": ("img.png", image, "image/png")}
        data = {"model": MODEL, "priority": str(priority), "top_k": "5"}
        with self.client.post(
            "/v1/classify",
            headers={"X-API-Key": API_KEY},
            files=files,
            data=data,
            name="/v1/classify",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code in (429, 503, 504):
                # Expected under overload — record but don't count as a hard error.
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}: {resp.text[:120]}")


class StepLoadShape(LoadTestShape):
    """Ramp through three throughput tiers; each stage holds for 60s.

    User counts are rough proxies for RPS (actual RPS depends on round-trip
    latency). Tune ``users`` for your hardware to actually hit 100/500/1000 RPS.
    """

    stages = [
        {"duration": 60, "users": 50, "spawn_rate": 20},     # ~100 RPS tier
        {"duration": 120, "users": 200, "spawn_rate": 50},   # ~500 RPS tier
        {"duration": 180, "users": 400, "spawn_rate": 100},  # ~1000 RPS tier
    ]

    def tick(self):  # type: ignore[no-untyped-def]
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None


@events.test_stop.add_listener
def _summary(environment, **_kw):  # type: ignore[no-untyped-def]
    stats = environment.stats.total
    print(
        f"\n=== load summary ===\n"
        f"requests={stats.num_requests} failures={stats.num_failures}\n"
        f"p50={stats.get_response_time_percentile(0.50)}ms "
        f"p95={stats.get_response_time_percentile(0.95)}ms "
        f"p99={stats.get_response_time_percentile(0.99)}ms\n"
        f"rps={stats.total_rps:.1f}\n"
    )
