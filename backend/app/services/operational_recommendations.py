"""Operational recommendations engine — grounded operational suggestions.

Doctrine: AI may recommend; humans decide. The engine produces deterministic
recommendations (rule-based with retrieval grounding) for material
operational situations:

  * queue_reprioritize — overdue queue items competing for owner attention
  * escalate           — pressure spike on a mission with declining health
  * mitigate_supplier_risk — supplier_risk signal touching a mission
  * route_approval     — pending approval older than threshold
  * executive_attention — high-impact signal cluster needing leadership review
  * operational_followup — investor opportunity past next_step_due_at
  * escalate_intelligence — critical-severity signal with pressure-raising impact

Each recommendation includes:
  - rationale (human-readable, sourced)
  - confidence (0..100; engine-derived from input strength)
  - components (scoring breakdown for audit)
  - citations (retrieval chunk references)
  - projected_impact + projected_delta when applicable

Idempotency: a (recommendation_type, mission_id, target_entity_type,
target_entity_id) tuple is upserted with the latest rationale + confidence.
This prevents recommendation spam — re-running the engine refreshes existing
pending rows rather than duplicating them.

Note: this is the operational recommendation engine (Sprint 5). The legacy
graph-match `services/recommendations.py` remains untouched and serves the
graph-level program/investor recommendation flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.execution_queue import ExecutionQueueItem
from app.models.intel import IntelItem
from app.models.investor import InvestorOpportunity
from app.models.mission import Mission
from app.models.recommendation import Recommendation
from app.models.signal import SignalImpact, SignalRelevance


REC_TYPES = {
    "queue_reprioritize",
    "escalate",
    "mitigate_supplier_risk",
    "coordinate_mission",
    "route_approval",
    "executive_attention",
    "operational_followup",
    "escalate_intelligence",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite (smoke harness) returns tz-naive datetimes; coerce to UTC so
    arithmetic with `_now()` doesn't fail. No-op for tz-aware values."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class GenerationReport:
    created: int
    refreshed: int
    total_pending: int


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------


def _upsert(
    db: Session,
    *,
    recommendation_type: str,
    title: str,
    rationale: str,
    confidence: int,
    mission_id: Optional[int],
    target_entity_type: Optional[str],
    target_entity_id: Optional[int],
    components: dict[str, Any],
    citations: Optional[list[dict[str, Any]]] = None,
    projected_impact: Optional[str] = None,
    projected_delta: Optional[int] = None,
    source: str = "engine",
    expires_at: Optional[datetime] = None,
) -> tuple[Recommendation, bool]:
    """Idempotent on (type, mission, target). Returns (row, created)."""
    conds = [
        Recommendation.recommendation_type == recommendation_type,
        Recommendation.status == "pending",
    ]
    if mission_id is None:
        conds.append(Recommendation.mission_id.is_(None))
    else:
        conds.append(Recommendation.mission_id == mission_id)
    if target_entity_type is None:
        conds.append(Recommendation.target_entity_type.is_(None))
    else:
        conds.append(Recommendation.target_entity_type == target_entity_type)
    if target_entity_id is None:
        conds.append(Recommendation.target_entity_id.is_(None))
    else:
        conds.append(Recommendation.target_entity_id == target_entity_id)

    existing = db.scalars(select(Recommendation).where(and_(*conds))).first()

    if existing is not None:
        existing.title = title
        existing.rationale = rationale
        existing.confidence = confidence
        existing.components = components
        existing.citations = citations
        existing.projected_impact = projected_impact
        existing.projected_delta = projected_delta
        if expires_at is not None:
            existing.expires_at = expires_at
        db.flush()
        return existing, False

    row = Recommendation(
        recommendation_type=recommendation_type,
        title=title,
        rationale=rationale,
        confidence=confidence,
        mission_id=mission_id,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        components=components,
        citations=citations,
        projected_impact=projected_impact,
        projected_delta=projected_delta,
        source=source,
        expires_at=expires_at,
    )
    db.add(row)
    db.flush()
    return row, True


# ---------------------------------------------------------------------------
# generators (rule-based; each one is a tight scan over canonical state)
# ---------------------------------------------------------------------------


def _gen_supplier_risk(db: Session) -> list[tuple[Recommendation, bool]]:
    out: list[tuple[Recommendation, bool]] = []
    impacts = db.scalars(
        select(SignalImpact).where(SignalImpact.impact_type == "raises_pressure")
    ).all()
    for imp in impacts:
        item = db.get(IntelItem, imp.intel_item_id)
        if item is None:
            continue
        comps = imp.components if isinstance(imp.components, dict) else {}
        if comps.get("signal_type") != "supplier_risk":
            continue
        mission = db.get(Mission, imp.mission_id)
        if mission is None or mission.deleted_at is not None:
            continue
        rationale = (
            f"Signal '{item.title}' (source: {item.source}) raises pressure on "
            f"mission {mission.codename}. Recommend: identify backup suppliers, "
            f"freeze vendor-bound approvals, and trigger contingency review."
        )
        out.append(
            _upsert(
                db,
                recommendation_type="mitigate_supplier_risk",
                title=f"Mitigate supplier risk on {mission.codename}",
                rationale=rationale,
                confidence=max(40, min(90, imp.contribution * 3 + 40)),
                mission_id=mission.id,
                target_entity_type="intel_item",
                target_entity_id=item.id,
                components={
                    "signal_id": item.id,
                    "severity_band": comps.get("severity_band"),
                    "contribution": imp.contribution,
                },
                citations=[
                    {
                        "source_type": "intel_item",
                        "source_id": item.id,
                        "title": item.title,
                        "excerpt": (item.summary or "")[:280],
                    }
                ],
                projected_impact="lowers_pressure",
                projected_delta=-imp.contribution,
            )
        )
    return out


def _gen_executive_attention(db: Session) -> list[tuple[Recommendation, bool]]:
    out: list[tuple[Recommendation, bool]] = []
    rels = db.scalars(
        select(SignalRelevance)
        .where(SignalRelevance.is_relevant.is_(True))
        .where(SignalRelevance.decayed_score >= 35)
    ).all()
    by_mission: dict[int, list[SignalRelevance]] = {}
    for r in rels:
        by_mission.setdefault(r.mission_id, []).append(r)
    for mid, group in by_mission.items():
        if len(group) < 2:
            continue
        mission = db.get(Mission, mid)
        if mission is None or mission.deleted_at is not None:
            continue
        items_strs: list[str] = []
        citations: list[dict[str, Any]] = []
        for r in sorted(group, key=lambda x: -x.decayed_score)[:5]:
            it = db.get(IntelItem, r.intel_item_id)
            if it is None:
                continue
            items_strs.append(f"[{r.decayed_score}] {it.title}")
            citations.append(
                {
                    "source_type": "intel_item",
                    "source_id": it.id,
                    "title": it.title,
                    "excerpt": (it.summary or "")[:240],
                    "score": r.decayed_score,
                }
            )
        if not items_strs:
            continue
        rationale = (
            f"Mission {mission.codename} is the focus of {len(group)} concurrent "
            f"high-relevance intelligence signals. Top items: "
            + " | ".join(items_strs[:3])
        )
        out.append(
            _upsert(
                db,
                recommendation_type="executive_attention",
                title=f"Executive attention recommended for {mission.codename}",
                rationale=rationale,
                confidence=min(95, 50 + 8 * len(group)),
                mission_id=mission.id,
                target_entity_type="mission",
                target_entity_id=mission.id,
                components={"signal_count": len(group)},
                citations=citations,
                projected_impact="informational",
            )
        )
    return out


def _gen_route_approval(
    db: Session, *, age_threshold_hours: int = 24
) -> list[tuple[Recommendation, bool]]:
    out: list[tuple[Recommendation, bool]] = []
    cutoff = _now() - timedelta(hours=age_threshold_hours)
    stale = db.scalars(
        select(Approval)
        .where(Approval.status == "pending")
        .where(Approval.created_at < cutoff)
    ).all()
    for a in stale:
        created_at = _aware(a.created_at) or _now()
        age_h = int((_now() - created_at).total_seconds() / 3600)
        rationale = (
            f"Approval '{a.action}' (id #{a.id}) has been pending for {age_h}h. "
            "Recommend routing to a reviewer or escalating."
        )
        out.append(
            _upsert(
                db,
                recommendation_type="route_approval",
                title=f"Route stale approval #{a.id}",
                rationale=rationale,
                confidence=70,
                mission_id=a.mission_id,
                target_entity_type="approval",
                target_entity_id=a.id,
                components={"age_hours": age_h, "action": a.action},
                citations=[
                    {
                        "source_type": "approval",
                        "source_id": a.id,
                        "title": f"Approval: {a.action}",
                        "excerpt": (a.decision_note or "")[:200]
                        or f"Pending since {created_at.isoformat()}",
                    }
                ],
                projected_impact="lowers_pressure",
                projected_delta=-3,
            )
        )
    return out


def _gen_queue_reprioritize(db: Session) -> list[tuple[Recommendation, bool]]:
    out: list[tuple[Recommendation, bool]] = []
    now = _now()
    rows = db.scalars(
        select(ExecutionQueueItem)
        .where(ExecutionQueueItem.status == "queued")
        .where(ExecutionQueueItem.due_at.is_not(None))
        .where(ExecutionQueueItem.due_at < now)
        .where(ExecutionQueueItem.priority_score < 60)
        .where(ExecutionQueueItem.deleted_at.is_(None))
    ).all()
    for r in rows:
        rationale = (
            f"Queue item '{r.title}' is overdue (due {r.due_at.isoformat()}) "
            f"yet sits at priority {r.priority_score}. Recommend bumping to "
            "≥80 to align owner attention with operational urgency."
        )
        out.append(
            _upsert(
                db,
                recommendation_type="queue_reprioritize",
                title=f"Reprioritize overdue queue item #{r.id}",
                rationale=rationale,
                confidence=80,
                mission_id=r.mission_id,
                target_entity_type="execution_queue_item",
                target_entity_id=r.id,
                components={
                    "current_priority": r.priority_score,
                    "suggested_priority": 80,
                    "due_at": r.due_at.isoformat() if r.due_at else None,
                },
                citations=[
                    {
                        "source_type": "execution_queue_item",
                        "source_id": r.id,
                        "title": r.title,
                        "excerpt": (r.summary or "")[:200],
                    }
                ],
                projected_impact="lowers_pressure",
                projected_delta=-5,
            )
        )
    return out


def _gen_operational_followup(db: Session) -> list[tuple[Recommendation, bool]]:
    out: list[tuple[Recommendation, bool]] = []
    now = _now()
    opps = db.scalars(
        select(InvestorOpportunity)
        .where(InvestorOpportunity.next_step_due_at.is_not(None))
        .where(InvestorOpportunity.next_step_due_at < now)
        .where(InvestorOpportunity.status == "open")
        .where(InvestorOpportunity.deleted_at.is_(None))
    ).all()
    for o in opps:
        rationale = (
            f"Investor opportunity #{o.id} ({o.stage}) has an overdue next-step "
            f"({o.next_step_due_at.isoformat() if o.next_step_due_at else 'unknown'}). "
            f"Recommend operator follow-up: {o.next_step or 'review and action'}."
        )
        out.append(
            _upsert(
                db,
                recommendation_type="operational_followup",
                title=f"Follow up on investor opportunity #{o.id}",
                rationale=rationale,
                confidence=75,
                mission_id=o.mission_id,
                target_entity_type="investor_opportunity",
                target_entity_id=o.id,
                components={
                    "stage": o.stage,
                    "owner": o.owner,
                    "due_at": o.next_step_due_at.isoformat() if o.next_step_due_at else None,
                },
                citations=[
                    {
                        "source_type": "investor_opportunity",
                        "source_id": o.id,
                        "title": f"Opportunity #{o.id} · stage {o.stage}",
                        "excerpt": (o.next_step or "")[:200],
                    }
                ],
                projected_impact="lowers_pressure",
                projected_delta=-4,
            )
        )
    return out


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def regenerate_all(db: Session) -> GenerationReport:
    results: list[tuple[Recommendation, bool]] = []
    results.extend(_gen_supplier_risk(db))
    results.extend(_gen_executive_attention(db))
    results.extend(_gen_route_approval(db))
    results.extend(_gen_queue_reprioritize(db))
    results.extend(_gen_operational_followup(db))

    created = sum(1 for _, c in results if c)
    refreshed = sum(1 for _, c in results if not c)

    db.commit()
    pending = db.scalars(
        select(Recommendation).where(Recommendation.status == "pending")
    ).all()
    return GenerationReport(
        created=created, refreshed=refreshed, total_pending=len(pending)
    )


# ---------------------------------------------------------------------------
# read + decide
# ---------------------------------------------------------------------------


def list_recommendations(
    db: Session,
    *,
    mission_id: Optional[int] = None,
    status: Optional[str] = None,
    recommendation_type: Optional[str] = None,
    limit: int = 100,
) -> list[Recommendation]:
    stmt = select(Recommendation)
    if mission_id is not None:
        stmt = stmt.where(Recommendation.mission_id == mission_id)
    if status:
        stmt = stmt.where(Recommendation.status == status)
    if recommendation_type:
        stmt = stmt.where(Recommendation.recommendation_type == recommendation_type)
    stmt = (
        stmt.order_by(
            Recommendation.confidence.desc(), Recommendation.created_at.desc()
        ).limit(limit)
    )
    return list(db.scalars(stmt).all())


def decide(
    db: Session,
    rec_id: int,
    *,
    decision: str,
    decided_by: str,
    decision_note: Optional[str] = None,
) -> Recommendation:
    if decision not in ("accepted", "dismissed"):
        raise HTTPException(
            status_code=422, detail="decision must be accepted|dismissed"
        )
    rec = db.get(Recommendation, rec_id)
    if rec is None:
        raise HTTPException(
            status_code=404, detail=f"Recommendation #{rec_id} not found"
        )
    if rec.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Recommendation is not pending (current: '{rec.status}')",
        )
    rec.status = decision
    rec.decided_by = decided_by
    rec.decided_at = _now()
    if decision_note is not None:
        rec.decision_note = decision_note
    db.commit()
    db.refresh(rec)
    return rec
