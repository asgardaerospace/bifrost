"""Operational simulation — lightweight what-if propagation.

Doctrine: deterministic, graph-aware traversal. No speculative forecasting,
no fake prediction systems. Every output is an explainable propagation tree
rooted at the perturbation, with explicit assumptions and a confidence band
derived from data completeness.

Three simulations:
  * supplier_failure(supplier_id) — propagate via existing relationships +
    SignalImpact rows of supplier_risk type → list affected missions +
    estimated pressure delta if their existing supplier_risk impacts
    persisted at full strength.
  * approval_delay(approval_id, hours) — extend the route_approval pressure
    contribution; derive the delta from the existing pressure model.
  * dependency_propagation(entity_type, entity_id, depth) — BFS across the
    relationships table from the seed; report path + per-hop relationship
    type. Used to answer "which dependencies create the highest propagation
    risk".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.intel import IntelEntity, IntelItem
from app.models.mission import Mission, MissionEntity
from app.models.relationship import Relationship
from app.models.signal import SignalImpact


# ---------------------------------------------------------------------------
# response shapes
# ---------------------------------------------------------------------------


@dataclass
class ImpactedMission:
    mission_id: int
    codename: str
    name: str
    pressure_delta: int
    rationale: str


@dataclass
class PropagationEdge:
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    relationship_type: str
    distance: int


@dataclass
class SimulationResult:
    simulation_type: str
    seed: dict[str, Any]
    impacted_missions: list[ImpactedMission]
    propagation_paths: list[PropagationEdge]
    pressure_deltas: dict[int, int]  # mission_id → signed delta
    confidence: float
    assumptions: list[str]
    notes: list[str]


def _mission_summary(db: Session, mid: int) -> tuple[str, str]:
    m = db.get(Mission, mid)
    if m is None:
        return f"#{mid}", f"mission#{mid}"
    return m.codename, m.name


# ---------------------------------------------------------------------------
# supplier failure
# ---------------------------------------------------------------------------


def supplier_failure(db: Session, supplier_id: int) -> SimulationResult:
    """If supplier #N fails, what missions are affected and how much pressure
    each will accumulate from the existing supplier_risk impacts already in
    the system, plus mission-side links?"""
    # 1) Direct mission-side links: missions that have linked this supplier
    #    via MissionEntity.
    direct_links = db.scalars(
        select(MissionEntity).where(
            MissionEntity.entity_type == "supplier",
            MissionEntity.entity_id == supplier_id,
        )
    ).all()

    # 2) Supplier_risk SignalImpact rows where the source intel mentions this
    #    supplier in its IntelEntity rows.
    intel_ids = {
        ent.intel_item_id
        for ent in db.scalars(
            select(IntelEntity).where(
                IntelEntity.entity_type.in_(("supplier", "company")),
                IntelEntity.entity_id == supplier_id,
            )
        ).all()
    }
    impacts: list[SignalImpact] = []
    if intel_ids:
        impacts = list(
            db.scalars(
                select(SignalImpact).where(
                    SignalImpact.intel_item_id.in_(intel_ids),
                    SignalImpact.impact_type == "raises_pressure",
                )
            ).all()
        )

    pressure_deltas: dict[int, int] = {}
    rationales: dict[int, list[str]] = {}

    for link in direct_links:
        # Conservative baseline: mission directly bound to a failing supplier
        # accumulates +12 pressure (proportional to escalation weight; below
        # the propagation cap).
        mid = link.mission_id
        pressure_deltas[mid] = pressure_deltas.get(mid, 0) + 12
        rationales.setdefault(mid, []).append(
            f"direct supplier link (relationship_type={link.relationship_type})"
        )

    for imp in impacts:
        mid = imp.mission_id
        pressure_deltas[mid] = pressure_deltas.get(mid, 0) + max(0, imp.contribution)
        rationales.setdefault(mid, []).append(
            f"existing supplier_risk impact #{imp.id} contribution +{imp.contribution}"
        )

    impacted: list[ImpactedMission] = []
    for mid, delta in pressure_deltas.items():
        codename, name = _mission_summary(db, mid)
        impacted.append(
            ImpactedMission(
                mission_id=mid,
                codename=codename,
                name=name,
                pressure_delta=int(min(50, delta)),  # safety cap
                rationale="; ".join(rationales[mid]),
            )
        )

    confidence = 0.85 if (direct_links or impacts) else 0.3
    assumptions = [
        "supplier failure modeled as full operational unavailability for the simulation horizon",
        "pressure deltas are additive on top of current mission pressure",
        "downstream propagation is one hop; deeper cascades require dependency_propagation",
        "no recovery effects modeled (no contingency suppliers)",
    ]
    notes: list[str] = []
    if not direct_links and not impacts:
        notes.append(
            "No mission-side links or intelligence impacts found for this supplier "
            "— likely indicating an unmonitored vendor; pressure delta is best-effort."
        )

    return SimulationResult(
        simulation_type="supplier_failure",
        seed={"supplier_id": supplier_id},
        impacted_missions=impacted,
        propagation_paths=[],  # one-hop direct links only in this simulation
        pressure_deltas=pressure_deltas,
        confidence=confidence,
        assumptions=assumptions,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# approval delay
# ---------------------------------------------------------------------------


def approval_delay(
    db: Session, approval_id: int, *, delay_hours: int
) -> SimulationResult:
    a = db.get(Approval, approval_id)
    if a is None:
        raise HTTPException(status_code=404, detail=f"Approval #{approval_id} not found")
    # Pressure model contribution per pending approval is 3 points (capped 15
    # for the mission-wide approvals component). A delay of N hours raises
    # the chance the approval ages into the route_approval recommendation
    # bucket (24h+) → an additional pressure multiplier.
    base = 3
    extra = 1 if delay_hours >= 24 else 0
    delta = base + extra
    impacted: list[ImpactedMission] = []
    if a.mission_id is not None:
        codename, name = _mission_summary(db, a.mission_id)
        impacted.append(
            ImpactedMission(
                mission_id=a.mission_id,
                codename=codename,
                name=name,
                pressure_delta=delta,
                rationale=(
                    f"approval action='{a.action}' delayed {delay_hours}h adds "
                    f"+{delta} mission pressure (base {base}"
                    + (" +1 stale-approval bonus past 24h" if extra else "")
                    + ")"
                ),
            )
        )
    return SimulationResult(
        simulation_type="approval_delay",
        seed={"approval_id": approval_id, "delay_hours": delay_hours},
        impacted_missions=impacted,
        propagation_paths=[],
        pressure_deltas={a.mission_id: delta} if a.mission_id is not None else {},
        confidence=0.75,
        assumptions=[
            "pressure model treats each pending approval as +3 (capped at 15 across the mission)",
            "stale-approval threshold is 24h; beyond that an additional route_approval recommendation fires",
            "no compensating side effects modeled",
        ],
        notes=[],
    )


# ---------------------------------------------------------------------------
# dependency propagation
# ---------------------------------------------------------------------------


def dependency_propagation(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    depth: int = 2,
) -> SimulationResult:
    """BFS across the relationships table from a seed entity. Reports
    propagation paths and the count of mission entities reached."""
    depth = max(1, min(5, depth))
    visited: set[tuple[str, int]] = {(entity_type, entity_id)}
    paths: list[PropagationEdge] = []
    frontier: list[tuple[str, int]] = [(entity_type, entity_id)]
    impacted_mission_ids: set[int] = set()

    for d in range(1, depth + 1):
        next_frontier: list[tuple[str, int]] = []
        for cur_type, cur_id in frontier:
            edges = db.scalars(
                select(Relationship).where(
                    Relationship.deleted_at.is_(None),
                    or_(
                        (Relationship.source_type == cur_type)
                        & (Relationship.source_id == cur_id),
                        (Relationship.target_type == cur_type)
                        & (Relationship.target_id == cur_id),
                    ),
                )
            ).all()
            for edge in edges:
                if edge.source_type == cur_type and edge.source_id == cur_id:
                    other = (edge.target_type, edge.target_id)
                else:
                    other = (edge.source_type, edge.source_id)
                if other in visited:
                    continue
                visited.add(other)
                paths.append(
                    PropagationEdge(
                        source_type=cur_type,
                        source_id=cur_id,
                        target_type=other[0],
                        target_id=other[1],
                        relationship_type=edge.relationship_type,
                        distance=d,
                    )
                )
                if other[0] == "mission":
                    impacted_mission_ids.add(other[1])
                next_frontier.append(other)
        frontier = next_frontier
        if not frontier:
            break

    impacted: list[ImpactedMission] = []
    pressure_deltas: dict[int, int] = {}
    for mid in impacted_mission_ids:
        codename, name = _mission_summary(db, mid)
        # Conservative: each propagation hop reaching a mission attributes
        # +5 pressure, decayed by distance in BFS. 5 / d.
        # Use the shortest-path distance found.
        distances = [
            p.distance
            for p in paths
            if p.target_type == "mission" and p.target_id == mid
        ] + [
            p.distance
            for p in paths
            if p.source_type == "mission" and p.source_id == mid
        ]
        d_min = min(distances) if distances else depth
        delta = max(1, int(5 / d_min))
        pressure_deltas[mid] = delta
        impacted.append(
            ImpactedMission(
                mission_id=mid,
                codename=codename,
                name=name,
                pressure_delta=delta,
                rationale=f"reached at distance {d_min} via {len([p for p in paths if (p.source_type, p.source_id, p.target_type, p.target_id) == (entity_type, entity_id, 'mission', mid) or (p.target_type, p.target_id, p.source_type, p.source_id) == (entity_type, entity_id, 'mission', mid)]) or '?'} relationship edges",
            )
        )

    return SimulationResult(
        simulation_type="dependency_propagation",
        seed={"entity_type": entity_type, "entity_id": entity_id, "depth": depth},
        impacted_missions=impacted,
        propagation_paths=paths,
        pressure_deltas=pressure_deltas,
        confidence=0.7,
        assumptions=[
            "graph traversal uses only relationships rows (deleted_at IS NULL); FK-derived edges are not included",
            "pressure attribution is 5/d_min per impacted mission (heuristic, deterministic)",
            "no cycle weighting; each unique mission is counted once at its shortest distance",
        ],
        notes=([] if paths else ["no relationship edges found from this seed"]),
    )
