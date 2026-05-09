"""Sprint 8 — reliability primitives."""

from __future__ import annotations

import pytest

from app.core.reliability import (
    BreakerOpenError,
    CircuitBreaker,
    RetryPolicy,
    idempotency,
    retry,
)


def test_retry_returns_result_after_transient_failure():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    out = retry(flaky, policy=RetryPolicy(max_attempts=3, base_delay_s=0.01), label="t")
    assert out == "ok"
    assert calls["n"] == 2


def test_retry_exhausts_and_raises():
    def always_fail():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        retry(always_fail, policy=RetryPolicy(max_attempts=2, base_delay_s=0.01), label="t")


def test_circuit_breaker_opens_after_threshold():
    br = CircuitBreaker(failure_threshold=2, cool_down_s=10.0, label="test")

    def boom():
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            with br.guard("k"):
                boom()

    # Now the breaker is open — third attempt short-circuits.
    with pytest.raises(BreakerOpenError):
        with br.guard("k"):
            boom()


def test_idempotency_round_trip():
    idempotency.remember("test-key", {"v": 1})
    hit, val = idempotency.fetch("test-key")
    assert hit is True
    assert val == {"v": 1}


def test_idempotency_miss_for_unknown_key():
    hit, val = idempotency.fetch("unknown-key-xyz")
    assert hit is False
    assert val is None


def test_retry_policy_delay_is_bounded():
    p = RetryPolicy(base_delay_s=1.0, max_delay_s=2.0, jitter=0.0)
    # attempt 5 would be 16s without cap; should clamp to 2.0.
    assert p.delay(5) == 2.0
