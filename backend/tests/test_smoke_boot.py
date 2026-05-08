"""Smoke 1 — app boots and the canonical Sprint 0 routes are registered."""

from __future__ import annotations


def test_app_boots(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_advertises_canonical_routes(client):
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    paths = set(r.json()["paths"].keys())

    # Canonical Sprint 0 endpoints must all be present.
    expected = {
        "/api/v1/missions",
        "/api/v1/missions/{mission_id}",
        "/api/v1/missions/{mission_id}/pressure",
        "/api/v1/missions/{mission_id}/dependencies",
        "/api/v1/missions/{mission_id}/timeline",
        "/api/v1/missions/{mission_id}/entities",
        "/api/v1/missions/{mission_id}/entities/{link_id}",
        "/api/v1/execution/queue",
        "/api/v1/execution/blockers",
        "/api/v1/execution/approvals",
        "/api/v1/execution/actions",
        "/api/v1/execution/actions/{item_id}",
        "/api/v1/events",
        "/api/v1/graph/relationships",
        "/api/v1/graph/relationships/{edge_id}",
        "/api/v1/graph/propagation",
    }
    missing = expected - paths
    assert not missing, f"Missing canonical Sprint 0 routes: {missing}"


def test_existing_routes_unchanged(client):
    """Existing CRM/domain routes must still respond — additive-only invariant."""
    r = client.get("/api/v1/openapi.json")
    paths = set(r.json()["paths"].keys())
    legacy = {
        "/api/v1/health",
        "/api/v1/health/db",
        "/api/v1/investors/firms",
        "/api/v1/approvals/",
        "/api/v1/intel",
        "/api/v1/command-console/commands",
        "/api/v1/graph/recommendations",
    }
    missing = legacy - paths
    assert not missing, f"Sprint 0 broke existing routes: {missing}"
