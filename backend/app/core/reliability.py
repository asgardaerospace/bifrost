"""Reliability primitives — retry, timeout, circuit breaker, idempotency.

Doctrine:
  * Bounded retries — never retry indefinitely.
  * Backoff with jitter — avoid synchronized retry storms.
  * Idempotency keys are first-class — duplicates resolve to the original
    result, not a fresh execution.
  * Degraded mode is observable — every fallback increments a counter and
    emits a structured log breadcrumb so operators can see when the system
    is leaning on its safety net.

Used by:
  * agent / workflow execution paths
  * external integration calls
  * websocket reconnect (server-side hardening — client side lives in
    frontend/lib/ws-client.ts)
"""

from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Callable, Iterator, Optional, TypeVar

from app.core.observability import metrics

logger = logging.getLogger("bifrost.reliability")

T = TypeVar("T")


# ---------------------------------------------------------------------------
# retry / backoff
# ---------------------------------------------------------------------------


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 0.25
    max_delay_s: float = 5.0
    jitter: float = 0.25  # +/- fraction of computed delay
    retry_on: tuple[type, ...] = (Exception,)

    def delay(self, attempt: int) -> float:
        # exponential: base * 2^(attempt-1), capped, with jitter.
        d = min(self.max_delay_s, self.base_delay_s * (2 ** max(0, attempt - 1)))
        if self.jitter > 0:
            wobble = d * self.jitter
            d = max(0.0, d + random.uniform(-wobble, wobble))
        return d


def retry(
    fn: Callable[[], T],
    *,
    policy: Optional[RetryPolicy] = None,
    label: str = "operation",
) -> T:
    """Execute fn() with bounded retries. Re-raises the final exception."""
    p = policy or RetryPolicy()
    last_exc: Optional[BaseException] = None
    for attempt in range(1, p.max_attempts + 1):
        try:
            result = fn()
            if attempt > 1:
                metrics.incr(f"reliability.retry.success.{label}")
            return result
        except p.retry_on as exc:
            last_exc = exc
            metrics.incr(f"reliability.retry.attempt.{label}")
            if attempt >= p.max_attempts:
                metrics.incr(f"reliability.retry.exhausted.{label}")
                logger.warning(
                    "retry exhausted",
                    extra={
                        "op": label,
                        "attempt": attempt,
                        "exc": exc.__class__.__name__,
                    },
                )
                raise
            delay = p.delay(attempt)
            logger.info(
                "retrying",
                extra={
                    "op": label,
                    "attempt": attempt,
                    "next_delay_s": round(delay, 3),
                    "exc": exc.__class__.__name__,
                },
            )
            time.sleep(delay)
    # Unreachable, satisfy type checker.
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# circuit breaker — open/half-open/closed
# ---------------------------------------------------------------------------


@dataclass
class _BreakerState:
    failures: int = 0
    opened_at: float = 0.0
    state: str = "closed"  # closed | open | half_open


class CircuitBreaker:
    """Per-key circuit breaker with cool-down. Use to fail fast against a
    consistently-failing dependency rather than burning retry budget."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        cool_down_s: float = 30.0,
        label: str = "default",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cool_down_s = cool_down_s
        self.label = label
        self._lock = RLock()
        self._states: dict[str, _BreakerState] = {}

    @contextmanager
    def guard(self, key: str = "default") -> Iterator[None]:
        with self._lock:
            st = self._states.setdefault(key, _BreakerState())
            now = time.monotonic()
            if st.state == "open" and (now - st.opened_at) >= self.cool_down_s:
                st.state = "half_open"
            if st.state == "open":
                metrics.incr(f"reliability.breaker.short_circuit.{self.label}")
                raise BreakerOpenError(f"{self.label}:{key} circuit open")
        try:
            yield
        except Exception:
            with self._lock:
                st = self._states[key]
                st.failures += 1
                if st.failures >= self.failure_threshold:
                    st.state = "open"
                    st.opened_at = time.monotonic()
                    metrics.incr(f"reliability.breaker.opened.{self.label}")
                    logger.warning(
                        "circuit opened",
                        extra={"breaker": self.label, "key": key, "failures": st.failures},
                    )
            raise
        else:
            with self._lock:
                st = self._states[key]
                if st.state == "half_open":
                    metrics.incr(f"reliability.breaker.recovered.{self.label}")
                    logger.info("circuit recovered", extra={"breaker": self.label, "key": key})
                st.failures = 0
                st.state = "closed"


class BreakerOpenError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# idempotency
# ---------------------------------------------------------------------------


@dataclass
class _IdempotencyEntry:
    result: Any
    expires_at: float


class IdempotencyRegistry:
    """In-process idempotency store. Bounded TTL, bounded entry count.

    For workflow/queue execution we additionally persist idempotency keys to
    the database (see services/idempotency.py); this in-memory layer fields
    fast hits within a single process.
    """

    def __init__(self, *, ttl_s: float = 300.0, max_entries: int = 4096) -> None:
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._lock = RLock()
        self._store: dict[str, _IdempotencyEntry] = {}

    def remember(self, key: str, result: Any) -> None:
        with self._lock:
            self._store[key] = _IdempotencyEntry(
                result=result, expires_at=time.monotonic() + self.ttl_s
            )
            if len(self._store) > self.max_entries:
                # Evict oldest by expiry.
                oldest = sorted(self._store.items(), key=lambda kv: kv[1].expires_at)[
                    : len(self._store) - self.max_entries
                ]
                for k, _ in oldest:
                    self._store.pop(k, None)

    def fetch(self, key: str) -> tuple[bool, Any]:
        now = time.monotonic()
        with self._lock:
            ent = self._store.get(key)
            if ent is None:
                return False, None
            if ent.expires_at < now:
                self._store.pop(key, None)
                return False, None
            metrics.incr("reliability.idempotency.hit")
            return True, ent.result


idempotency = IdempotencyRegistry()
