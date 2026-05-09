"""Observability primitives — structured logging, request correlation,
trace metadata, and a lightweight in-process metrics registry.

Doctrine:
  * Trace continuity: every request carries a correlation id (x-request-id)
    that flows into structured log records and into emitted operational
    events as `trace_id`, so a failure can be followed across HTTP -> service
    -> event -> websocket fanout boundaries.
  * Mission-aware tracing: when a service knows the mission_id, it stamps it
    on the trace; this makes it cheap to filter logs and metrics by mission.
  * No external dependencies required. OpenTelemetry hooks are wired
    conditionally — if the `opentelemetry-api` package is installed and
    OTEL_EXPORTER_OTLP_ENDPOINT is set, spans are emitted; otherwise the
    same code path uses no-op spans and runs normally.

We deliberately avoid coupling business code to a tracing SDK — services call
`with trace.span("name", attributes=...)` and the implementation here decides
whether that becomes an OTel span or a logging breadcrumb.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Iterator, Optional


# ---------------------------------------------------------------------------
# Context vars — request-scoped trace metadata.
# ---------------------------------------------------------------------------

_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "bifrost_request_id", default=None
)
_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "bifrost_trace_id", default=None
)
_mission_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "bifrost_mission_id", default=None
)
_actor: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "bifrost_actor", default=None
)
_workflow_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "bifrost_workflow_id", default=None
)


def get_request_id() -> Optional[str]:
    return _request_id.get()


def get_trace_id() -> Optional[str]:
    return _trace_id.get()


def get_mission_id() -> Optional[int]:
    return _mission_id.get()


def get_actor() -> Optional[str]:
    return _actor.get()


def get_workflow_id() -> Optional[str]:
    return _workflow_id.get()


def current_trace() -> dict[str, Any]:
    """Snapshot of the active trace metadata — safe to attach to events."""
    out: dict[str, Any] = {}
    rid = _request_id.get()
    tid = _trace_id.get()
    mid = _mission_id.get()
    act = _actor.get()
    wf = _workflow_id.get()
    if rid:
        out["request_id"] = rid
    if tid:
        out["trace_id"] = tid
    if mid is not None:
        out["mission_id"] = mid
    if act:
        out["actor"] = act
    if wf:
        out["workflow_id"] = wf
    return out


@contextmanager
def trace_context(
    *,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    mission_id: Optional[int] = None,
    actor: Optional[str] = None,
    workflow_id: Optional[str] = None,
) -> Iterator[None]:
    """Bind trace metadata for the duration of a block. Use sparingly outside
    middleware — most services should let the request-level context flow."""
    tokens = []
    if request_id is not None:
        tokens.append(_request_id.set(request_id))
    if trace_id is not None:
        tokens.append(_trace_id.set(trace_id))
    if mission_id is not None:
        tokens.append(_mission_id.set(mission_id))
    if actor is not None:
        tokens.append(_actor.set(actor))
    if workflow_id is not None:
        tokens.append(_workflow_id.set(workflow_id))
    try:
        yield
    finally:
        for t in tokens:
            try:
                t.var.reset(t)
            except Exception:
                pass


def set_mission(mission_id: Optional[int]) -> None:
    _mission_id.set(mission_id)


def set_workflow(workflow_id: Optional[str]) -> None:
    _workflow_id.set(workflow_id)


def set_actor(actor: Optional[str]) -> None:
    _actor.set(actor)


# ---------------------------------------------------------------------------
# Logging — structured JSON formatter.
# ---------------------------------------------------------------------------


_LOG_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime",
}


class JSONFormatter(logging.Formatter):
    """Structured JSON log records with trace metadata embedded."""

    def format(self, record: logging.LogRecord) -> str:
        # Use isoformat from record.created so microseconds work cross-platform
        # (time.strftime('%f') is not supported on Windows).
        from datetime import datetime, timezone
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Pull in trace context lazily so background tasks without context don't
        # add empty fields.
        payload.update(current_trace())
        # Allow caller to attach extra fields via logger.<level>(..., extra={...}).
        for k, v in record.__dict__.items():
            if k in _LOG_RESERVED or k.startswith("_"):
                continue
            if k in payload:
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)
        try:
            return json.dumps(payload, default=str, separators=(",", ":"))
        except Exception:
            return f'{{"level":"{record.levelname}","msg":{json.dumps(record.getMessage())}}}'


def configure_logging(level: Optional[str] = None, fmt: Optional[str] = None) -> None:
    """Idempotent root-logger setup. Safe to call from app startup."""
    level = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    fmt = (fmt or os.environ.get("LOG_FORMAT") or "json").lower()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s :: %(message)s"
            )
        )

    root = logging.getLogger()
    # Drop any pre-existing default handler — common when uvicorn installs one.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    try:
        root.setLevel(getattr(logging, level))
    except AttributeError:
        root.setLevel(logging.INFO)

    # Quiet noisy third-party loggers; they can be re-raised via env.
    for noisy in ("uvicorn.access", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Lightweight metrics registry — counters/gauges/timers.
# ---------------------------------------------------------------------------


@dataclass
class _MetricSeries:
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    timers_ms: dict[str, list[float]] = field(default_factory=dict)


class MetricsRegistry:
    """In-process metrics. Designed to be cheap; not a Prometheus replacement.

    Use:
        metrics.incr("ws.frames_sent")
        metrics.gauge("pubsub.connections", 42)
        with metrics.timer("workflow.execute"): ...
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._data = _MetricSeries()
        self._timer_cap = 256  # cap timer history per key; we report p50/p95/avg

    def incr(self, key: str, by: int = 1) -> None:
        with self._lock:
            self._data.counters[key] = self._data.counters.get(key, 0) + by

    def gauge(self, key: str, value: float) -> None:
        with self._lock:
            self._data.gauges[key] = float(value)

    def observe_ms(self, key: str, value_ms: float) -> None:
        with self._lock:
            arr = self._data.timers_ms.setdefault(key, [])
            arr.append(value_ms)
            if len(arr) > self._timer_cap:
                # Keep the most recent N — simple bounded buffer.
                del arr[0 : len(arr) - self._timer_cap]

    @contextmanager
    def timer(self, key: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.observe_ms(key, (time.perf_counter() - t0) * 1000.0)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            timers = {}
            for k, arr in self._data.timers_ms.items():
                if not arr:
                    continue
                sorted_arr = sorted(arr)
                n = len(sorted_arr)
                timers[k] = {
                    "n": n,
                    "avg_ms": round(sum(sorted_arr) / n, 3),
                    "p50_ms": round(sorted_arr[n // 2], 3),
                    "p95_ms": round(sorted_arr[min(n - 1, int(n * 0.95))], 3),
                    "max_ms": round(sorted_arr[-1], 3),
                }
            return {
                "counters": dict(self._data.counters),
                "gauges": dict(self._data.gauges),
                "timers": timers,
            }

    def reset(self) -> None:
        with self._lock:
            self._data = _MetricSeries()


metrics = MetricsRegistry()


# ---------------------------------------------------------------------------
# Tracing facade — emits OTel spans if available; otherwise structured log
# breadcrumbs. The contract is the same so call sites don't change.
# ---------------------------------------------------------------------------


@dataclass
class _SpanHandle:
    name: str
    started_at: float
    attributes: dict[str, Any]


class _NullTracer:
    @contextmanager
    def span(self, name: str, attributes: Optional[dict[str, Any]] = None) -> Iterator[_SpanHandle]:
        attrs = dict(attributes or {})
        attrs.update(current_trace())
        h = _SpanHandle(name=name, started_at=time.perf_counter(), attributes=attrs)
        try:
            yield h
        finally:
            elapsed_ms = (time.perf_counter() - h.started_at) * 1000.0
            metrics.observe_ms(f"trace.{name}", elapsed_ms)
            logging.getLogger("bifrost.trace").debug(
                "span", extra={"span_name": name, "elapsed_ms": round(elapsed_ms, 3), **h.attributes}
            )


class _OtelTracer:
    def __init__(self, otel_tracer: Any) -> None:
        self._tracer = otel_tracer

    @contextmanager
    def span(self, name: str, attributes: Optional[dict[str, Any]] = None) -> Iterator[_SpanHandle]:
        attrs = dict(attributes or {})
        attrs.update(current_trace())
        with self._tracer.start_as_current_span(name, attributes=attrs) as _:
            t0 = time.perf_counter()
            try:
                yield _SpanHandle(name=name, started_at=t0, attributes=attrs)
            finally:
                metrics.observe_ms(f"trace.{name}", (time.perf_counter() - t0) * 1000.0)


def _build_tracer() -> Any:
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return _NullTracer()
    try:
        from opentelemetry import trace as ot  # type: ignore[import-not-found]

        return _OtelTracer(ot.get_tracer("bifrost"))
    except Exception:
        return _NullTracer()


tracer = _build_tracer()


def new_request_id() -> str:
    return uuid.uuid4().hex


def init_observability() -> None:
    """Single-call setup invoked from main.create_app()."""
    configure_logging()
