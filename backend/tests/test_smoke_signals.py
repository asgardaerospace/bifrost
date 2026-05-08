"""Sprint 4 — signal helpers + ingestion pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.intel import IntelItem
from app.services import intel_ingest as ingest_service
from app.services import signals as signal_helpers


def _make_item(**kwargs) -> IntelItem:
    base = dict(
        source="Test",
        title="Title",
        url="https://example/1",
        category="uncategorized",
        published_at=datetime.now(timezone.utc),
        strategic_relevance_score=0,
        urgency_score=0,
        confidence_score=0,
        summary="Body",
    )
    base.update(kwargs)
    return IntelItem(**base)


def test_derive_signal_type_from_category():
    assert signal_helpers.derive_signal_type(_make_item(category="vc_funding")) == "funding"
    assert signal_helpers.derive_signal_type(_make_item(category="supply_chain")) == "supplier_risk"
    assert signal_helpers.derive_signal_type(_make_item(category="defense_tech")) == "defense"


def test_derive_signal_type_keyword_override_for_uncategorized():
    item = _make_item(
        category="uncategorized",
        title="DARPA Issues RFP for Autonomous Systems",
        summary="Contract award expected Q3.",
    )
    assert signal_helpers.derive_signal_type(item) == "procurement"


def test_derive_severity_bands():
    assert signal_helpers.derive_severity(_make_item(urgency_score=10, strategic_relevance_score=20)) == "info"
    assert signal_helpers.derive_severity(_make_item(urgency_score=40, strategic_relevance_score=10)) == "notice"
    assert signal_helpers.derive_severity(_make_item(urgency_score=70, strategic_relevance_score=10)) == "warning"
    assert signal_helpers.derive_severity(_make_item(urgency_score=90, strategic_relevance_score=10)) == "critical"


def test_decay_factor_recent_vs_old():
    now = datetime.now(timezone.utc)
    fresh = signal_helpers.decay_factor(now)
    old = signal_helpers.decay_factor(now - timedelta(days=14))
    older = signal_helpers.decay_factor(now - timedelta(days=28))
    assert fresh > old > older
    # Half-life is 14 days → ~0.5 at 14d, ~0.25 at 28d.
    assert 0.49 <= old <= 0.51
    assert 0.24 <= older <= 0.26


def test_deterministic_external_id_dedups_on_url():
    a = signal_helpers.deterministic_external_id(
        source="Reuters", url="https://x/y", title="A"
    )
    b = signal_helpers.deterministic_external_id(
        source="Reuters", url="https://x/y", title="DIFFERENT TITLE"
    )
    assert a == b
    c = signal_helpers.deterministic_external_id(
        source="Reuters", url="https://x/z", title="A"
    )
    assert a != c


def test_ingest_seed_signals_creates_intel_items(client, db_session):
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals

    report = ingest_service.ingest_batch(
        db_session, aerospace_seed_signals(), actor="test"
    )
    assert report.ingested == 5
    assert report.deduped == 0

    rows = db_session.query(IntelItem).all()
    assert len(rows) == 5
    sources = {r.source for r in rows}
    assert "DefenseDaily" in sources


def test_ingest_dedupes_on_repeat(client, db_session):
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals

    seed = aerospace_seed_signals()
    ingest_service.ingest_batch(db_session, seed, actor="test")
    second = ingest_service.ingest_batch(db_session, seed, actor="test")
    # Re-ingest is fully deduped.
    assert second.ingested == 0
    assert second.deduped == 5
