"""Sprint 8 — idempotency dedupe."""

from __future__ import annotations

from app.services import idempotency as idem


def test_remember_then_fetch_round_trip(client, db_session):
    key = "test-workflow-run-abc"
    idem.remember(db_session, key, {"status": "ok", "value": 7})
    db_session.commit()

    hit, val = idem.fetch(db_session, key)
    assert hit is True
    assert val == {"status": "ok", "value": 7}


def test_fetch_unknown_key_misses(client, db_session):
    hit, val = idem.fetch(db_session, "never-stored-zzz")
    assert hit is False
    assert val is None


def test_in_proc_cache_populates_from_db(client, db_session):
    """A second fetch (after evicting the in-proc cache) should still hit
    the persisted record in the operational_events table."""
    from app.core.reliability import idempotency as in_proc

    key = "cross-worker-key-xyz"
    idem.remember(db_session, key, "result-val")
    db_session.commit()
    # Drop the in-proc cache entry to simulate a different worker.
    in_proc._store.pop(key, None)
    hit, val = idem.fetch(db_session, key)
    assert hit is True
    assert val == "result-val"
