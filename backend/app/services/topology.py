"""Spatial mission topology service — Sprint 7.

Builds a typed, spatially-renderable graph for the cockpit's topology view.

Doctrine:
    - the topology is *strategic*, not exhaustive — we filter to entities that
      participate in at least one mission edge or relationship
    - every edge carries a propagation direction and an intensity score so
      the frontend can render explainable pressure flow
    - clusters are derived from existing groupings (mission, parent_mission)
      so the layout stays mission-centric

Inputs are pulled from `relationships` and `mission_entities` tables — no
new persisted state is required.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.intel import IntelItem
from app.models.investor import InvestorFirm
from app.models.market import Account
from app.models.mission import Mission, MissionEntity
from app.models.program import Program
from app.models.relationship import Relationship
from app.models.supplier import Supplier
from app.schemas.topology import (
    PropagationPath,
    TopologyEdge,
    TopologyNode,
    TopologyView,
)


_BAND_INTENSITY = {"nominal": 15, "watch": 40, "strain": 65, "critical": 90}

# Mission-mission edges that carry pressure. Order matters for direction:
_PRESSURE_EDGES = ("depends_on", "blocks", "supports", "escalates_to", "mitigates")


def _node_id(kind: str, entity_id: int) -> str:
    return f"{kind}:{entity_id}"


def _band_for_score(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "strain"
    if score >= 35:
        return "watch"
    return "nominal"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mission_node(m: Mission) -> TopologyNode:
    score = int(m.pressure_score or 0)
    return TopologyNode(
        id=_node_id("mission", m.id),
        kind="mission",
        entity_id=m.id,
        label=m.codename,
        sublabel=m.name,
        band=_band_for_score(score),  # type: ignore[arg-type]
        pressure_score=score,
        cluster=f"mission:{m.parent_mission_id}" if m.parent_mission_id else f"mission:{m.id}",
        weight=2,
        meta={
            "priority": m.priority,
            "status": m.status,
            "health_status": m.health_status,
        },
    )


def _supplier_node(s: Supplier) -> TopologyNode:
    return TopologyNode(
        id=_node_id("supplier", s.id),
        kind="supplier",
        entity_id=s.id,
        label=s.name,
        sublabel=s.type or s.region,
        band="nominal",
        pressure_score=0,
        cluster="supplier",
        meta={"onboarding_status": s.onboarding_status},
    )


def _program_node(p: Program) -> TopologyNode:
    return TopologyNode(
        id=_node_id("program", p.id),
        kind="program",
        entity_id=p.id,
        label=p.name,
        sublabel=p.stage,
        band="nominal",
        pressure_score=0,
        cluster="program",
        meta={"stage": p.stage},
    )


def _firm_node(f: InvestorFirm) -> TopologyNode:
    return TopologyNode(
        id=_node_id("investor_firm", f.id),
        kind="investor_firm",
        entity_id=f.id,
        label=f.name,
        sublabel=f.firm_type,
        cluster="capital",
        meta={"firm_type": f.firm_type},
    )


def _account_node(a: Account) -> TopologyNode:
    return TopologyNode(
        id=_node_id("account", a.id),
        kind="account",
        entity_id=a.id,
        label=a.name,
        sublabel=a.industry,
        cluster="market",
        meta={"industry": a.industry},
    )


def _intel_node(it: IntelItem) -> TopologyNode:
    return TopologyNode(
        id=_node_id("intel_item", it.id),
        kind="intel_item",
        entity_id=it.id,
        label=it.title[:80],
        sublabel=it.category,
        band="watch" if (it.urgency_score or 0) >= 60 else "nominal",  # type: ignore[arg-type]
        pressure_score=int(it.strategic_relevance_score or 0),
        cluster="intel",
        meta={"urgency": it.urgency_score, "relevance": it.strategic_relevance_score},
    )


def _propagation_paths(
    nodes: dict[str, TopologyNode],
    edges: list[TopologyEdge],
    *,
    limit: int = 6,
) -> list[PropagationPath]:
    """Trace the strongest pressure flows: any path of length <= 3 that
    terminates in a critical/strain mission node, ranked by accumulated
    intensity. Calm visualization — we cap the count."""
    adj: dict[str, list[TopologyEdge]] = defaultdict(list)
    for e in edges:
        if e.propagation == "downstream":
            adj[e.source].append(e)
        elif e.propagation == "upstream":
            adj[e.target].append(e)
        else:
            adj[e.source].append(e)

    # Origins are nodes that aren't pure sinks — start from missions and
    # external entities (supplier/intel) that feed missions.
    origins = [
        n.id for n in nodes.values()
        if n.kind in ("mission", "supplier", "intel_item", "investor_firm")
    ]

    paths: list[PropagationPath] = []
    for origin in origins:
        # BFS up to depth 3, summing intensity
        stack: list[tuple[str, list[str], list[str], int]] = [
            (origin, [origin], [], 0)
        ]
        seen_terminals: set[str] = set()
        while stack:
            current, node_path, edge_kinds, accum = stack.pop()
            if len(node_path) > 1:
                node = nodes.get(current)
                if (
                    node is not None
                    and node.kind == "mission"
                    and node.band in ("strain", "critical")
                    and current != origin
                    and current not in seen_terminals
                ):
                    seen_terminals.add(current)
                    intensity = min(100, max(accum, _BAND_INTENSITY.get(node.band, 0)))
                    paths.append(
                        PropagationPath(
                            origin=origin,
                            terminal=current,
                            intensity=intensity,
                            band=node.band,  # type: ignore[arg-type]
                            path=node_path,
                            edge_kinds=edge_kinds,
                            explanation=(
                                f"Pressure flows {origin} → {current} via "
                                f"{', '.join(edge_kinds) or 'direct'} "
                                f"(intensity {intensity})."
                            ),
                        )
                    )
                    continue
            if len(node_path) >= 4:
                continue
            for edge in adj.get(current, []):
                nxt = edge.target if edge.source == current else edge.source
                if nxt in node_path:
                    continue
                stack.append((
                    nxt,
                    node_path + [nxt],
                    edge_kinds + [edge.kind],
                    accum + edge.intensity,
                ))

    paths.sort(key=lambda p: -p.intensity)
    return paths[:limit]


def build_topology(
    db: Session,
    *,
    mission_id: Optional[int] = None,
    include_intel: bool = True,
) -> TopologyView:
    """Build org or mission-scoped topology view."""
    nodes: dict[str, TopologyNode] = {}
    edges: list[TopologyEdge] = []

    # 1. mission nodes
    mission_stmt = select(Mission).where(Mission.deleted_at.is_(None))
    if mission_id is not None:
        # mission-scoped: focus on this mission + its dependency neighborhood
        focal = db.get(Mission, mission_id)
        if focal is None or focal.deleted_at is not None:
            return TopologyView(
                generated_at=_now(),
                scope="mission",
                mission_id=mission_id,
                nodes=[],
                edges=[],
                propagation_paths=[],
                cluster_summary={},
            )
        mission_stmt = mission_stmt.where(
            or_(
                Mission.id == mission_id,
                Mission.parent_mission_id == mission_id,
                Mission.id == focal.parent_mission_id,
            )
        )

    missions = list(db.scalars(mission_stmt).all())
    for m in missions:
        nodes[_node_id("mission", m.id)] = _mission_node(m)

    mission_id_set = {m.id for m in missions}

    # 2. parent edges
    for m in missions:
        if m.parent_mission_id and _node_id("mission", m.parent_mission_id) in nodes:
            edges.append(
                TopologyEdge(
                    id=f"parent:{m.parent_mission_id}->{m.id}",
                    source=_node_id("mission", m.parent_mission_id),
                    target=_node_id("mission", m.id),
                    kind="participates_in",
                    propagation="downstream",
                    intensity=10,
                )
            )

    # 3. mission ↔ mission relationships
    rel_stmt = (
        select(Relationship)
        .where(Relationship.deleted_at.is_(None))
        .where(Relationship.relationship_type.in_(_PRESSURE_EDGES))
        .where(Relationship.source_type == "mission")
        .where(Relationship.target_type == "mission")
        .where(Relationship.source_id.in_(mission_id_set or {-1}))
    )
    for rel in db.scalars(rel_stmt).all():
        if _node_id("mission", rel.target_id) not in nodes:
            # add the linked mission, even if outside the focal scope
            other = db.get(Mission, rel.target_id)
            if other and other.deleted_at is None:
                nodes[_node_id("mission", other.id)] = _mission_node(other)
        edges.append(
            TopologyEdge(
                id=f"rel:{rel.id}",
                source=_node_id("mission", rel.source_id),
                target=_node_id("mission", rel.target_id),
                kind=rel.relationship_type,
                propagation="downstream"
                if rel.relationship_type in ("blocks", "escalates_to", "depends_on")
                else "lateral",
                intensity=_intensity_for_target(nodes, _node_id("mission", rel.target_id)),
                weight=rel.weight or 1,
            )
        )

    # 4. mission_entities — derive cross-domain edges
    me_rows = db.scalars(
        select(MissionEntity).where(MissionEntity.mission_id.in_(mission_id_set or {-1}))
    ).all()

    supplier_ids: set[int] = set()
    program_ids: set[int] = set()
    firm_ids: set[int] = set()
    account_ids: set[int] = set()
    intel_ids: set[int] = set()

    for me in me_rows:
        if me.entity_type == "supplier":
            supplier_ids.add(me.entity_id)
        elif me.entity_type == "program":
            program_ids.add(me.entity_id)
        elif me.entity_type == "investor_firm":
            firm_ids.add(me.entity_id)
        elif me.entity_type == "account":
            account_ids.add(me.entity_id)
        elif me.entity_type == "intel_item":
            intel_ids.add(me.entity_id)

    # Hydrate
    if supplier_ids:
        for s in db.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids))).all():
            nodes[_node_id("supplier", s.id)] = _supplier_node(s)
    if program_ids:
        for p in db.scalars(select(Program).where(Program.id.in_(program_ids))).all():
            nodes[_node_id("program", p.id)] = _program_node(p)
    if firm_ids:
        for f in db.scalars(
            select(InvestorFirm).where(InvestorFirm.id.in_(firm_ids))
        ).all():
            nodes[_node_id("investor_firm", f.id)] = _firm_node(f)
    if account_ids:
        for a in db.scalars(select(Account).where(Account.id.in_(account_ids))).all():
            nodes[_node_id("account", a.id)] = _account_node(a)
    if include_intel:
        # Intel items linked directly via mission_id (no MissionEntity required)
        intel_q = select(IntelItem).where(
            IntelItem.mission_id.in_(mission_id_set or {-1})
        )
        for it in db.scalars(intel_q).all():
            nodes[_node_id("intel_item", it.id)] = _intel_node(it)
        # Plus any explicitly linked
        if intel_ids:
            for it in db.scalars(
                select(IntelItem).where(IntelItem.id.in_(intel_ids))
            ).all():
                nodes[_node_id("intel_item", it.id)] = _intel_node(it)

    # Edges from mission_entities — typed per relationship_type
    for me in me_rows:
        target_id = _node_id(me.entity_type, me.entity_id)
        source_id = _node_id("mission", me.mission_id)
        if target_id not in nodes:
            continue
        kind = me.relationship_type or "linked"
        # Suppliers/programs feed mission delivery — mark as upstream pressure
        propagation = "upstream" if me.entity_type in ("supplier", "program") else "lateral"
        edges.append(
            TopologyEdge(
                id=f"me:{me.id}",
                source=source_id,
                target=target_id,
                kind=kind,
                propagation=propagation,  # type: ignore[arg-type]
                intensity=_intensity_for_target(nodes, source_id),
                weight=me.weight or 1,
            )
        )

    # Intel items with mission_id → mission edges (high-relevance only)
    if include_intel:
        intel_with_mission = db.scalars(
            select(IntelItem)
            .where(IntelItem.mission_id.in_(mission_id_set or {-1}))
            .where(IntelItem.strategic_relevance_score >= 60)
        ).all()
        for it in intel_with_mission:
            tgt = _node_id("intel_item", it.id)
            if tgt not in nodes:
                continue
            edges.append(
                TopologyEdge(
                    id=f"intel:{it.id}->m{it.mission_id}",
                    source=tgt,
                    target=_node_id("mission", it.mission_id),
                    kind="signals",
                    propagation="downstream",
                    intensity=int(it.strategic_relevance_score or 0),
                )
            )

    # propagation paths
    paths = _propagation_paths(nodes, edges)

    # cluster counts
    cluster_summary: dict[str, int] = defaultdict(int)
    for n in nodes.values():
        cluster_summary[n.cluster or "unclustered"] += 1

    return TopologyView(
        generated_at=_now(),
        scope="mission" if mission_id is not None else "org",
        mission_id=mission_id,
        nodes=list(nodes.values()),
        edges=edges,
        propagation_paths=paths,
        cluster_summary=dict(cluster_summary),
    )


def _intensity_for_target(nodes: dict[str, TopologyNode], target_id: str) -> int:
    n = nodes.get(target_id)
    if n is None:
        return 10
    return _BAND_INTENSITY.get(n.band, 10)
