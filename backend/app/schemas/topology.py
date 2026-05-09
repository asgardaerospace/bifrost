"""Mission topology schemas — Sprint 7.

A spatial cognition surface. The topology is a typed graph of missions
and the entities that bind them — supplier dependencies, capital exposure,
program staffing, intel impact. We compute *propagation paths* (pressure
flows along relationships) so the frontend can render explainable
spatial cognition rather than an undirected node soup.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from app.schemas.base import ORMModel


NodeKind = Literal[
    "mission",
    "supplier",
    "program",
    "investor_firm",
    "account",
    "intel_item",
    "agent",
]


class TopologyNode(ORMModel):
    id: str  # f"{kind}:{entity_id}" — stable across calls
    kind: NodeKind
    entity_id: int
    label: str
    sublabel: Optional[str] = None
    band: Literal["nominal", "watch", "strain", "critical"] = "nominal"
    pressure_score: int = 0
    cluster: Optional[str] = None  # graph cluster id (for layout grouping)
    weight: int = 1
    meta: dict = {}


class TopologyEdge(ORMModel):
    id: str  # stable per source→target+type
    source: str
    target: str
    kind: str  # relationship_type or derived ("staffed_by", "exposed_to", ...)
    weight: int = 1
    propagation: Literal["upstream", "downstream", "lateral"] = "lateral"
    intensity: int = 0  # 0..100 — visual weight of pressure carried
    meta: dict = {}


class PropagationPath(ORMModel):
    """A traced pressure flow along edges (origin → ... → terminal)."""

    origin: str
    terminal: str
    intensity: int  # 0..100
    band: Literal["nominal", "watch", "strain", "critical"]
    path: list[str]  # node ids
    edge_kinds: list[str]
    explanation: str


class TopologyView(ORMModel):
    generated_at: datetime
    scope: Literal["org", "mission"]
    mission_id: Optional[int] = None
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
    propagation_paths: list[PropagationPath]
    cluster_summary: dict[str, int]
