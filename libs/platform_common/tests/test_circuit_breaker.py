"""Circuit breaker state-machine tests."""

from __future__ import annotations

import time

import pytest
from platform_common.errors import CircuitOpenError
from platform_common.utils.circuit_breaker import CircuitBreaker, CircuitState


def test_opens_after_threshold():
    cb = CircuitBreaker(fail_threshold=3, reset_timeout=10)
    for _ in range(3):
        cb.record_failure()
    assert cb.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        cb.allow()


def test_success_resets_failures():
    cb = CircuitBreaker(fail_threshold=3, reset_timeout=10)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.state is CircuitState.CLOSED
    cb.allow()  # does not raise


def test_half_open_after_timeout_then_closes_on_success():
    cb = CircuitBreaker(fail_threshold=1, reset_timeout=0.05)
    cb.record_failure()
    assert cb.state is CircuitState.OPEN
    time.sleep(0.06)
    assert cb.state is CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state is CircuitState.CLOSED


def test_half_open_reopens_on_failure():
    cb = CircuitBreaker(fail_threshold=1, reset_timeout=0.05)
    cb.record_failure()
    time.sleep(0.06)
    assert cb.state is CircuitState.HALF_OPEN
    cb.record_failure()
    assert cb.state is CircuitState.OPEN
