"""RelationshipService — first-class typed graph edges.

Sits alongside the existing `services/graph.py` (which derives rule-based
matches from FKs). This service stores explicit edges in `relationships`
and walks them for /graph/relationships and /graph/propagation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.relationship import RELATIONSHIP_TYPES, Relationship
from app.schemas.operational_event import OperationalEventCreate
from app.schemas.relationship import (
    PropagationNode,
    PropagationView,
    RelationshipCreate,
)
from app.services import events as events_service


def list_edges(
    db: Session,
    *,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    relationship_type: Optional[str] = None,
    include_either_side: bool = False,
    limit: int = 500,
) -> list[Relationship]:
    """List edges. If `include_either_side` is True, source filters apply to
    either end of the edge (useful for "all edges touching this entity")."""
    stmt = select(Relationship).where(Relationship.deleted_at.is_(None))
    if relationship_type:
        stmt = stmt.where(Relationship.relationship_type == relationship_type)
    if include_either_side and source_type and source_id is not None:
        stmt = stmt.where(
            or_(
                (Relationship.source_type == source_type)
                & (Relationship.source_id == source_id),
                (Relationship.target_type == source_type)
                & (Relationship.target_id == source_id),
            )
        )
    else:
        if source_type:
            stmt = stmt.where(Relationship.source_type == source_type)
        if source_id is not None:
            stmt = stmt.where(Relationship.source_id == source_id)
        if target_type:
            stmt = stmt.where(Relationship.target_type == target_type)
        if target_id is not None:
            stmt = stmt.where(Relationship.target_id == target_id)
    stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def create_edge(
    db: Session, payload: RelationshipCreate, *, actor: str = "system"
) -> Relationship:
    if payload.relationship_type not in RELATIONSHIP_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown relationship_type '{payload.relationship_type}'. "
                f"Allowed: {', '.join(RELATIONSHIP_TYPES)}"
            ),
        )
    if (
        payload.source_type == payload.target_type
        and payload.source_id == payload.target_id
    ):
        raise HTTPException(status_code=422, detail="self-edge not allowed")

    existing = db.scalars(
        select(Relationship).where(
            Relationship.source_type == payload.source_type,
            Relationship.source_id == payload.source_id,
            Relationship.target_type == payload.target_type,
            Relationship.target_id == payload.target_id,
            Relationship.relationship_type == payload.relationship_type,
        )
    ).first()
    if existing is not None:
        if existing.deleted_at is not None:
            existing.deleted_at = None
            existing.weight = payload.weight
            existing.meta = payload.meta
            db.commit()
            db.refresh(existing)
        return existing

    edge = Relationship(**payload.model_dump())
    db.add(edge)
    db.flush()
    events_service.publish(
        db,
        OperationalEventCreate(
            topic="graph",
            event_type="relationship.created",
            entity_type=edge.source_type,
            entity_id=edge.source_id,
            actor=actor,
            payload={
                "edge_id": edge.id,
                "source_type": edge.source_type,
                "source_id": edge.source_id,
                "target_type": edge.target_type,
                "target_id": edge.target_id,
                "relationship_type": edge.relationship_type,
            },
        ),
    )
    db.commit()
    db.refresh(edge)
    return edge


def soft_delete_edge(
    db: Session, edge_id: int, *, actor: str = "system"
) -> None:
    edge = db.get(Relationship, edge_id)
    if edge is None or edge.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    edge.deleted_at = datetime.now(timezone.utc)
    db.flush()
    events_service.publish(
        db,
        OperationalEventCreate(
            topic="graph",
            event_type="relationship.deleted",
            entity_type=edge.source_type,
            entity_id=edge.source_id,
            actor=actor,
            severity="warning",
            payload={"edge_id": edge_id},
        ),
    )
    db.commit()


def propagate(
    db: Session,
    *,
    source_type: str,
    source_id: int,
    direction: str = "downstream",
    depth: int = 2,
    relationship_types: Optional[list[str]] = None,
) -> PropagationView:
    """Walk explicit relationships outward from (source_type, source_id).

    `direction='downstream'` follows source→target edges; `'upstream'` follows
    target→source; `'both'` follows either. Sprint 0 BFS — no cycle handling
    beyond visited set, no weighting; richer propagation arrives in Sprint 2.
    """
    if direction not in ("downstream", "upstream", "both"):
        raise HTTPException(
            status_code=422, detail="direction must be downstream|upstream|both"
        )
    depth = max(1, min(5, depth))

    visited: set[tuple[str, int]] = {(source_type, source_id)}
    nodes: list[PropagationNode] = []
    frontier: list[tuple[str, int, list[str]]] = [(source_type, source_id, [])]

    for distance in range(1, depth + 1):
        next_frontier: list[tuple[str, int, list[str]]] = []
        for cur_type, cur_id, path in frontier:
            stmt = select(Relationship).where(
                Relationship.deleted_at.is_(None)
            )
            if relationship_types:
                stmt = stmt.where(
                    Relationship.relationship_type.in_(relationship_types)
                )
            if direction == "downstream":
                stmt = stmt.where(
                    Relationship.source_type == cur_type,
                    Relationship.source_id == cur_id,
                )
            elif direction == "upstream":
                stmt = stmt.where(
                    Relationship.target_type == cur_type,
                    Relationship.target_id == cur_id,
                )
            else:  # both
                stmt = stmt.where(
                    or_(
                        (Relationship.source_type == cur_type)
                        & (Relationship.source_id == cur_id),
                        (Relationship.target_type == cur_type)
                        & (Relationship.target_id == cur_id),
                    )
                )
            for edge in db.scalars(stmt).all():
                if edge.source_type == cur_type and edge.source_id == cur_id:
                    other = (edge.target_type, edge.target_id)
                else:
                    other = (edge.source_type, edge.source_id)
                if other in visited:
                    continue
                visited.add(other)
                new_path = path + [edge.relationship_type]
                nodes.append(
                    PropagationNode(
                        entity_type=other[0],
                        entity_id=other[1],
                        distance=distance,
                        path=new_path,  # type: ignore[arg-type]
                    )
                )
                next_frontier.append((other[0], other[1], new_path))
        frontier = next_frontier
        if not frontier:
            break

    return PropagationView(
        source_type=source_type,
        source_id=source_id,
        direction=direction,  # type: ignore[arg-type]
        depth=depth,
        nodes=nodes,
    )
