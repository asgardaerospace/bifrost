"""Sprint 6 — agent + workflow schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.schemas.base import ORMModel, TimestampedRead


class AgentDescriptorRead(ORMModel):
    name: str
    version: str
    purpose: str
    allowed_actions: list[str]
    required_approvals: list[str]
    accessible_domains: list[str]
    confidence_threshold: int
    workflow_key: str
    stages: list[str]
    escalation_rules: list[str]


class AgentRunRequest(ORMModel):
    trigger: str = "manual"
    mission_id: Optional[int] = None
    propagate_handoffs: bool = False  # explicit opt-in for chained coordination


class AgentRunReport(ORMModel):
    operation_id: int
    agent_name: str
    workflow_key: str
    final_status: str  # proposed | weak | failed | cancelled
    confidence: int
    stage_count: int
    proposed_action_count: int
    error: Optional[str] = None
    handoff_runs: list[int] = []  # downstream operation ids if propagate=true


class AgentWorkflowStageRead(TimestampedRead):
    autonomy_operation_id: int
    stage_index: int
    stage_name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_payload: Optional[dict[str, Any]] = None
    output_payload: Optional[dict[str, Any]] = None
    retrieval_trace: Optional[dict[str, Any]] = None
    confidence: Optional[int] = None
    error: Optional[str] = None


class AutonomyOperationRead(TimestampedRead):
    agent_name: str
    operation_type: str
    mission_id: Optional[int] = None
    status: str
    confidence_score: int
    reasoning: Optional[str] = None
    retrieval_citations: Optional[dict[str, Any]] = None
    payload: Optional[dict[str, Any]] = None
    proposed_at: datetime
    decided_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    decided_by_user_id: Optional[int] = None
    trigger: Optional[str] = None
    workflow_key: Optional[str] = None


class WorkflowTraceRead(ORMModel):
    operation: AutonomyOperationRead
    stages: list[AgentWorkflowStageRead]
    proposed_action_count: int


class ProposedActionRead(TimestampedRead):
    autonomy_operation_id: int
    action_type: str
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[int] = None
    payload: Optional[dict[str, Any]] = None
    status: str
    requires_approval: bool


class ProposedActionDecisionRequest(ORMModel):
    decision: str  # approved | rejected
    decided_by: Optional[str] = None
    note: Optional[str] = None
