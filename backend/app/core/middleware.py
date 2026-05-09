"""HTTP middleware — request correlation, structured access logs, in-process
rate limiting, and operational metrics.

All middleware here is additive and safe to disable individually via env vars.
None of them block requests by default in development.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from threading import RLock
from typing import Deque, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.observability import (
    current_trace,
    metrics,
    new_request_id,
    set_actor,
    trace_context,
)

logger = logging.getLogger("bifrost.http")


REQUEST_ID_HEADER = "x-request-id"
TRACE_ID_HEADER = "x-trace-id"


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Bind a request id + trace id into context vars for the request scope.

    Honors inbound x-request-id / x-trace-id headers when present (so a
    correlation id flows from the frontend or a calling service); otherwise
    generates a fresh id. Always echoes both back on the response.
    """

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        tid = request.headers.get(TRACE_ID_HEADER) or rid
        # Best-effort actor attribution — bearer token email if present, else
        # remote ip. The full user resolution happens later in get_current_user;
        # this is for logging.
        actor = _peek_actor(request)
        with trace_context(request_id=rid, trace_id=tid, actor=actor):
            t0 = time.perf_counter()
            status_code = 500
            try:
                response = await call_next(request)
                status_code = response.status_code
                response.headers[REQUEST_ID_HEADER] = rid
                response.headers[TRACE_ID_HEADER] = tid
                return response
            finally:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                metrics.incr("http.requests")
                metrics.incr(f"http.status.{status_code // 100}xx")
                metrics.observe_ms("http.latency", elapsed_ms)
                # Skip access logs for /health to avoid noise.
                if not request.url.path.endswith("/health"):
                    logger.info(
                        "http",
                        extra={
                            "method": request.method,
                            "path": request.url.path,
                            "status": status_code,
                            "elapsed_ms": round(elapsed_ms, 2),
                        },
                    )


def _peek_actor(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        # Don't decode here — just mark as authenticated.
        return "bearer"
    client = request.client.host if request.client else None
    return client


# ---------------------------------------------------------------------------
# Rate limiting — token bucket per (client_ip, route_prefix).
# ---------------------------------------------------------------------------


class _Bucket:
    __slots__ = ("hits",)

    def __init__(self) -> None:
        self.hits: Deque[float] = deque()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window-ish rate limiter (per-IP, per-route-prefix, per-window).

    Designed to defend against cheap abuse — not a substitute for a proper
    edge limiter. Disabled by default; enable with RATE_LIMIT_ENABLED=true.

    Skipped paths: health checks, websocket upgrade requests.
    """

    EXEMPT_PREFIXES = ("/api/v1/health", "/api/v1/ws")

    def __init__(self, app, *, rpm: int = 600, burst: int = 120) -> None:
        super().__init__(app)
        self.rpm = max(1, rpm)
        self.burst = max(1, burst)
        self._buckets: dict[str, _Bucket] = {}
        self._lock = RLock()
        self._window = 60.0  # seconds

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        key = self._key(request)
        if not self._allow(key):
            metrics.incr("http.rate_limited")
            return Response(
                status_code=429,
                content='{"detail":"rate limit exceeded"}',
                media_type="application/json",
                headers={"retry-after": "1", **{REQUEST_ID_HEADER: current_trace().get("request_id", "")}},
            )
        return await call_next(request)

    def _key(self, request: Request) -> str:
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ip and request.client:
            ip = request.client.host
        prefix = "/".join(request.url.path.split("/")[:4])  # /api/v1/<area>
        return f"{ip}::{prefix}"

    def _allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket()
                self._buckets[key] = bucket
            # Drop old hits outside the window.
            cutoff = now - self._window
            while bucket.hits and bucket.hits[0] < cutoff:
                bucket.hits.popleft()
            if len(bucket.hits) >= self.rpm:
                return False
            # Burst control over a 1-second sub-window.
            recent = sum(1 for t in bucket.hits if t > now - 1.0)
            if recent >= self.burst:
                return False
            bucket.hits.append(now)
            return True


def install_middlewares(app) -> None:
    """Attach correlation + (optionally) rate-limit middleware."""
    if os.environ.get("RATE_LIMIT_ENABLED", "false").lower() in ("true", "1", "yes"):
        rpm = int(os.environ.get("RATE_LIMIT_RPM", "600") or "600")
        burst = int(os.environ.get("RATE_LIMIT_BURST", "120") or "120")
        app.add_middleware(RateLimitMiddleware, rpm=rpm, burst=burst)
    app.add_middleware(CorrelationMiddleware)
