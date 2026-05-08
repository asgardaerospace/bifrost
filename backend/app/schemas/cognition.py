"""Sprint 5 — cognition + recommendations + simulation + drafting schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.schemas.base import ORMModel, TimestampedRead
from app.schemas.memory import (
    CitationRead,
    RetrievalTraceRead,
    SynthesisResponseRead,
)


# --- cognition --------------------------------------------------------------


class CognitionCommand(ORMModel):
    command: str
    mission_id: Optional[int] = None


class CognitionResponseRead(ORMModel):
    command: str
    intent_id: Optional[str] = None
    intent_label: Optional[str] = None
    matched_keywords: list[str]
    intent_confidence: float
    synthesis: SynthesisResponseRead


class IntentDescriptor(ORMModel):
    intent_id: str
    label: str
    keywords: list[str]
    requires_mission: bool
    temporal_hours: Optional[int] = None


# --- recommendations --------------------------------------------------------


class RecommendationRead(TimestampedRead):
    recommendation_type: str
    title: str
    rationale: str
    confidence: int
    mission_id: Optional[int] = None
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[int] = None
    projected_impact: Optional[str] = None
    projected_delta: Optional[int] = None
    components: dict[str, Any]
    citations: Optional[list[dict[str, Any]]] = None
    source: str
    created_by: Optional[str] = None
    status: str
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    expires_at: Optional[datetime] = None


class RecommendationDecision(ORMModel):
    decision: str  # "accepted" | "dismissed"
    decided_by: str
    decision_note: Optional[str] = None


class RecommendationGenerationReport(ORMModel):
    created: int
    refreshed: int
    total_pending: int


# --- simulation -------------------------------------------------------------


class ImpactedMissionRead(ORMModel):
    mission_id: int
    codename: str
    name: str
    pressure_delta: int
    rationale: str


class PropagationEdgeRead(ORMModel):
    source_type: str
    source_id: int
    target_type: str
    target_id: int
    relationship_type: str
    distance: int


class SimulationResultRead(ORMModel):
    simulation_type: str
    seed: dict[str, Any]
    impacted_missions: list[ImpactedMissionRead]
    propagation_paths: list[PropagationEdgeRead]
    pressure_deltas: dict[int, int]
    confidence: float
    assumptions: list[str]
    notes: list[str]


class SupplierFailureRequest(ORMModel):
    supplier_id: int


class ApprovalDelayRequest(ORMModel):
    approval_id: int
    delay_hours: int = 48


class DependencyPropagationRequest(ORMModel):
    entity_type: str
    entity_id: int
    depth: int = 2


# --- drafting ---------------------------------------------------------------


class DraftRequest(ORMModel):
    mission_id: Optional[int] = None
    approval_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    supplier_id: Optional[int] = None
    hours: Optional[int] = None
