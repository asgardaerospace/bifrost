"""Curated aerospace seed provider — deterministic sample signals.

Sprint 4 ships a curated set of representative signals so the ingestion
pipeline + relevance engine + propagation can be exercised end-to-end
without external network calls. Real RSS / feed providers extend the same
shape — see `aerospace_rss.py` for an example skeleton.

The seed is not meant for production. It is for tests, demos, and offline
verification of the relevance engine's behavior on shaped fixtures.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from app.services.intel_ingest import IngestedEntity, IngestedSignal


def _ago(**kwargs) -> datetime:
    return datetime.now(timezone.utc) - timedelta(**kwargs)


def aerospace_seed_signals() -> List[IngestedSignal]:
    return [
        IngestedSignal(
            source="DefenseDaily",
            title="Air Force Awards $420M Propulsion Sustainment Contract",
            url="https://example.com/usaf-propulsion-2026",
            summary=(
                "USAF Life Cycle Management Center awarded a five-year propulsion "
                "sustainment contract covering F100/F110 fleet engines. Anchor "
                "supplier announced reciprocal investment in additive tooling."
            ),
            region="us-east",
            category="policy_procurement",
            published_at=_ago(days=2),
            strategic_relevance_score=82,
            urgency_score=58,
            confidence_score=85,
            entities=[
                IngestedEntity(entity_type="agency", entity_name="USAF Life Cycle Management Center"),
                IngestedEntity(entity_type="program", entity_name="F100 propulsion sustainment"),
            ],
            tags=["procurement", "propulsion", "usaf"],
        ),
        IngestedSignal(
            source="AeroIndex",
            title="Static Fire Anomaly Halts Ridgeline LV-4 Test Cadence",
            url="https://example.com/ridgeline-lv4-anomaly",
            summary=(
                "Ridgeline disclosed a static-fire anomaly during LV-4 second-stage "
                "qualification, pushing the next test window by ~6 weeks. Range-safety "
                "officer review pending."
            ),
            region="us-west",
            category="aerospace_manufacturing",
            published_at=_ago(days=1),
            strategic_relevance_score=70,
            urgency_score=72,
            confidence_score=78,
            entities=[
                IngestedEntity(entity_type="company", entity_name="Ridgeline Propulsion"),
                IngestedEntity(entity_type="program", entity_name="LV-4 second stage"),
            ],
            tags=["static_fire", "anomaly", "qualification"],
        ),
        IngestedSignal(
            source="VC Wire",
            title="Northwall Capital Closes $300M Aerospace + Defense Fund VI",
            url="https://example.com/northwall-fund-vi",
            summary=(
                "Northwall Capital closed Fund VI at $300M, mandating dual-use aerospace "
                "and defense theses with check sizes $5M–$25M and a stated focus on "
                "propulsion, RF, and additive manufacturing."
            ),
            region="us-east",
            category="vc_funding",
            published_at=_ago(days=4),
            strategic_relevance_score=68,
            urgency_score=40,
            confidence_score=90,
            entities=[
                IngestedEntity(entity_type="investor", entity_name="Northwall Capital"),
            ],
            tags=["fund", "aerospace", "defense"],
        ),
        IngestedSignal(
            source="ProcureGov",
            title="DoD Issues RFI for Long-Range Solid Rocket Motor Capacity",
            url="https://example.com/dod-srm-rfi-2026",
            summary=(
                "DoD published a request for information on long-range solid rocket motor "
                "capacity expansion through FY29. Responses due in 30 days; invited to "
                "address loaded-grain throughput and ITAR-compliant tooling supply."
            ),
            region="us-east",
            category="policy_procurement",
            published_at=_ago(days=6),
            strategic_relevance_score=88,
            urgency_score=66,
            confidence_score=82,
            entities=[
                IngestedEntity(entity_type="agency", entity_name="Department of Defense"),
            ],
            tags=["rfi", "srm", "capacity"],
        ),
        IngestedSignal(
            source="Supplier Watch",
            title="HiTemp Composites Files for Chapter 11 Reorganization",
            url="https://example.com/hitemp-chapter11",
            summary=(
                "HiTemp Composites filed for Chapter 11. Customers across propulsion "
                "primes and Tier-1 manufacturers have been notified of expected delivery "
                "delays of 8–12 weeks pending court-supervised restructuring."
            ),
            region="us-south",
            category="supply_chain",
            published_at=_ago(days=3),
            strategic_relevance_score=75,
            urgency_score=85,
            confidence_score=88,
            entities=[
                IngestedEntity(entity_type="supplier", entity_name="HiTemp Composites"),
            ],
            tags=["bankruptcy", "supplier_risk", "composites"],
        ),
    ]
