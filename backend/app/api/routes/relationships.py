"""Relationship + propagation HTTP routes (additive — coexists with /graph/*)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.relationship import (
    PropagationView,
    RelationshipCreate,
    RelationshipRead,
)
from app.services import relationship as relationship_service

router = APIRouter()


@router.get("/graph/relationships", response_model=list[RelationshipRead])
def list_relationships(
    source_type: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id: Optional[int] = Query(None),
    relationship_type: Optional[str] = Query(None),
    either_side: bool = Query(False),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> list[RelationshipRead]:
    rows = relationship_service.list_edges(
        db,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        relationship_type=relationship_type,
        include_either_side=either_side,
        limit=limit,
    )
    return [RelationshipRead.model_validate(r) for r in rows]


@router.post(
    "/graph/relationships",
    response_model=RelationshipRead,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    payload: RelationshipCreate, db: Session = Depends(get_db)
) -> RelationshipRead:
    edge = relationship_service.create_edge(db, payload)
    return RelationshipRead.model_validate(edge)


@router.delete(
    "/graph/relationships/{edge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_relationship(edge_id: int, db: Session = Depends(get_db)) -> None:
    relationship_service.soft_delete_edge(db, edge_id)


@router.get("/graph/propagation", response_model=PropagationView)
def propagation(
    source_type: str = Query(...),
    source_id: int = Query(...),
    direction: str = Query("downstream"),
    depth: int = Query(2, ge=1, le=5),
    relationship_type: Optional[list[str]] = Query(None),
    db: Session = Depends(get_db),
) -> PropagationView:
    return relationship_service.propagate(
        db,
        source_type=source_type,
        source_id=source_id,
        direction=direction,
        depth=depth,
        relationship_types=relationship_type,
    )
