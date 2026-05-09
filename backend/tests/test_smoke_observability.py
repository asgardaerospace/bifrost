"""Sprint 8 — observability surface."""

from __future__ import annotations


def test_health_ready_returns_status(client):
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "checks" in body
    assert "database" in body["checks"]


def test_metrics_snapshot(client):
    # Drive at least one request so counters are populated.
    client.get("/api/v1/health")
    r = client.get("/api/v1/observability/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "counters" in body
    assert "gauges" in body
    assert "timers" in body
    assert "pubsub" in body


def test_request_id_is_echoed(client):
    r = client.get("/api/v1/health", headers={"x-request-id": "test-rid-123"})
    assert r.status_code == 200
    assert r.headers.get("x-request-id") == "test-rid-123"
    assert r.headers.get("x-trace-id") == "test-rid-123"


def test_request_id_generated_when_absent(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.headers.get("x-request-id"), "request id should be generated when absent"
