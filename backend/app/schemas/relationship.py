"""Relationship schemas — typed graph edges between any two entities."""

from __future__ import annotations

from typing import Any, Literal, Optional

from app.schemas.base import ORMModel, TimestampedRead


RelationshipType = Literal[
    "depends_on",
    "blocks",
    "supports",
    "funds",
    "supplies",
    "owns",
    "affects",
    "influences",
    "participates_in",
    "relates_to",
    "mitigates",
    "escalates_to",
    "connected_to",
]


class RelationshipBase(ORMModel):
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    relationship_type: RelationshipType
    weight: int = 1
    meta: Optional[dict[str, Any]] = None


class RelationshipCreate(RelationshipBase):
    pass


class RelationshipRead(RelationshipBase, TimestampedRead):
    pass


class PropagationNode(ORMModel):
    entity_type: str
    entity_id: int
    distance: int
    path: list[RelationshipType]


class PropagationView(ORMModel):
    source_type: str
    source_id: int
    direction: Literal["downstream", "upstream", "both"]
    depth: int
    nodes: list[PropagationNode]
