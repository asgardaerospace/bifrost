"""Signal propagation — explainable, deterministic, reversible.

When a signal lands with high relevance for a mission, propagation translates
it into operational consequence: pressure contribution, executive escalation
flag, recommended queue surfacing.

Sprint 4 implements the simplest of these: pressure contribution. The pressure
engine reads SignalImpact rows directly when computing a mission's score.

Doctrine: every propagation is recorded as a SignalImpact row with full
component breakdown, so an operator can ask `why is this mission under
pressure right now?` and receive an auditable, reversible answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.intel import IntelItem
from app.models.signal import SignalImpact, SignalRelevance


# Propagation maps signal_type → impact_type. Negative contributions mean
# the signal RELIEVES pressure (e.g., a funding opportunity reduces capital
# pressure on a mission whose blockers were funding-bound).
SIGNAL_TYPE_TO_IMPACT: dict[str, str] = {
    "supplier_risk": "raises_pressure",
    "geopolitical": "raises_pressure",
    "regulatory": "raises_pressure",
    "acquisition": "informational",
    "market_shift": "informational",
    "manufacturing": "informational",
    "launch": "informational",
    "partnership": "opportunity",
    "funding": "opportunity",
    "procurement": "opportunity",
    "defense": "opportunity",
}


# Per-impact-type weight applied to relevance.decayed_score to derive the
# mission-pressure contribution. Capped on the signed result.
W_RAISES_PRESSURE = 0.25
W_LOWERS_PRESSURE = -0.20
W_OPPORTUNITY = -0.10  # opportunities slightly relieve mission pressure
W_INFORMATIONAL = 0.0
W_ESCALATION = 0.40

CAP_ABS_CONTRIBUTION = 30


def _clip_signed(v: float) -> int:
    if v >= 0:
        return min(CAP_ABS_CONTRIBUTION, int(round(v)))
    return max(-CAP_ABS_CONTRIBUTION, int(round(v)))


def _weight_for(impact_type: str, severity_band: str) -> float:
    if impact_type == "raises_pressure":
        # Critical severity gets an additional bump (escalation).
        return W_ESCALATION if severity_band == "critical" else W_RAISES_PRESSURE
    if impact_type == "lowers_pressure":
        return W_LOWERS_PRESSURE
    if impact_type == "opportunity":
        return W_OPPORTUNITY
    return W_INFORMATIONAL


def propagate_signal(
    db: Session, *, intel_item: IntelItem, signal_type: str
) -> list[SignalImpact]:
    """Generate SignalImpact rows for every mission the signal is relevant to.

    Idempotent — replaces prior impacts for the same (intel_item, mission)
    pair so a re-score with weaker relevance correctly downgrades the impact.
    Returns the persisted rows.
    """
    relevances = db.scalars(
        select(SignalRelevance).where(
            SignalRelevance.intel_item_id == intel_item.id,
            SignalRelevance.is_relevant.is_(True),
        )
    ).all()

    if not relevances:
        # If signal was previously relevant, clear stale impacts.
        db.execute(
            delete(SignalImpact).where(
                SignalImpact.intel_item_id == intel_item.id
            )
        )
        db.flush()
        return []

    impact_type = SIGNAL_TYPE_TO_IMPACT.get(signal_type, "informational")

    # Replace prior impacts for this signal so contributions stay current.
    db.execute(
        delete(SignalImpact).where(SignalImpact.intel_item_id == intel_item.id)
    )
    db.flush()

    impacts: list[SignalImpact] = []
    for rel in relevances:
        sev = (rel.components or {}).get("severity_band", "info")
        weight = _weight_for(impact_type, sev)
        contribution = _clip_signed(rel.decayed_score * weight)

        components: dict[str, Any] = {
            "weight": weight,
            "severity_band": sev,
            "decayed_relevance": rel.decayed_score,
            "signal_type": signal_type,
            "impact_type": impact_type,
        }

        impact = SignalImpact(
            intel_item_id=intel_item.id,
            mission_id=rel.mission_id,
            impact_type=impact_type,
            contribution=contribution,
            components=components,
            notes=(
                f"{signal_type} signal × relevance {rel.decayed_score} → "
                f"{impact_type} contribution {contribution}"
            ),
            computed_at=datetime.now(timezone.utc),
        )
        db.add(impact)
        impacts.append(impact)
    db.flush()
    return impacts


def list_impacts_for_mission(
    db: Session, mission_id: int
) -> list[SignalImpact]:
    return list(
        db.scalars(
            select(SignalImpact)
            .where(SignalImpact.mission_id == mission_id)
            .order_by(SignalImpact.contribution.desc())
        ).all()
    )


def aggregate_pressure_contribution(
    db: Session, mission_id: int
) -> tuple[int, dict[str, Any]]:
    """Net signed pressure contribution from all signal impacts on a mission.

    Used by the pressure engine. Returned components include a per-type
    breakdown so the pressure snapshot stays explainable.
    """
    impacts = list_impacts_for_mission(db, mission_id)
    if not impacts:
        return 0, {}

    by_type: dict[str, int] = {}
    sources: list[dict[str, Any]] = []
    for imp in impacts:
        by_type[imp.impact_type] = by_type.get(imp.impact_type, 0) + imp.contribution
        sources.append(
            {
                "intel_item_id": imp.intel_item_id,
                "impact_type": imp.impact_type,
                "contribution": imp.contribution,
            }
        )
    total = sum(by_type.values())
    return _clip_signed(total), {"by_type": by_type, "count": len(impacts), "sources": sources[:8]}
