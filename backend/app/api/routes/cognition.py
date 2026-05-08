"""Cognition + recommendations + simulation + drafting routes (Sprint 5)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.schemas.cognition import (
    ApprovalDelayRequest,
    CognitionCommand,
    CognitionResponseRead,
    DependencyPropagationRequest,
    DraftRequest,
    ImpactedMissionRead,
    IntentDescriptor,
    PropagationEdgeRead,
    RecommendationDecision,
    RecommendationGenerationReport,
    RecommendationRead,
    SimulationResultRead,
    SupplierFailureRequest,
)
from app.schemas.memory import (
    CitationRead,
    RetrievalTraceRead,
    SynthesisResponseRead,
)
from app.services import cognition as cognition_service
from app.services import drafting as drafting_service
from app.services import operational_recommendations as rec_service
from app.services import simulation as sim_service

router = APIRouter()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _synth_to_read(resp) -> SynthesisResponseRead:
    return SynthesisResponseRead(
        objective=resp.objective,
        summary=resp.summary,
        confidence=resp.confidence,
        weak_retrieval=resp.weak_retrieval,
        citations=[
            CitationRead(
                marker=c.marker,
                chunk_id=c.chunk_id,
                record_id=c.record_id,
                source_type=c.source_type,
                source_id=c.source_id,
                title=c.title,
                excerpt=c.excerpt,
            )
            for c in resp.citations
        ],
        retrieval_trace=RetrievalTraceRead(
            query=resp.retrieval_trace.query,
            candidates_considered=resp.retrieval_trace.candidates_considered,
            chunks_returned=resp.retrieval_trace.chunks_returned,
            scoped_mission_id=resp.retrieval_trace.scoped_mission_id,
            scoped_entity_type=resp.retrieval_trace.scoped_entity_type,
            scoped_entity_id=resp.retrieval_trace.scoped_entity_id,
            since=resp.retrieval_trace.since,
            embedding_model=resp.retrieval_trace.embedding_model,
            weights=resp.retrieval_trace.weights,
        ),
        model=resp.model,
    )


# ---------------------------------------------------------------------------
# cognition pipeline
# ---------------------------------------------------------------------------


@router.post("/cognition/command", response_model=CognitionResponseRead)
def cognition_command(
    payload: CognitionCommand, db: Session = Depends(get_db)
) -> CognitionResponseRead:
    response = cognition_service.execute(
        db, payload.command, mission_id=payload.mission_id
    )
    return CognitionResponseRead(
        command=response.command,
        intent_id=response.intent_id,
        intent_label=response.intent_label,
        matched_keywords=response.matched_keywords,
        intent_confidence=response.intent_confidence,
        synthesis=_synth_to_read(response.synthesis),
    )


@router.get("/cognition/intents", response_model=list[IntentDescriptor])
def cognition_intents() -> list[IntentDescriptor]:
    return [
        IntentDescriptor(
            intent_id=i.intent_id,
            label=i.label,
            keywords=list(i.keywords),
            requires_mission=i.requires_mission,
            temporal_hours=i.temporal_hours,
        )
        for i in cognition_service.INTENTS
    ]


# ---------------------------------------------------------------------------
# recommendations
# ---------------------------------------------------------------------------


@router.post(
    "/recommendations/regenerate",
    response_model=RecommendationGenerationReport,
)
def regenerate_recommendations(db: Session = Depends(get_db)):
    report = rec_service.regenerate_all(db)
    return RecommendationGenerationReport(
        created=report.created,
        refreshed=report.refreshed,
        total_pending=report.total_pending,
    )


@router.get("/recommendations", response_model=list[RecommendationRead])
def list_recommendations(
    mission_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    recommendation_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RecommendationRead]:
    rows = rec_service.list_recommendations(
        db,
        mission_id=mission_id,
        status=status_filter,
        recommendation_type=recommendation_type,
        limit=limit,
    )
    return [RecommendationRead.model_validate(r) for r in rows]


@router.get(
    "/missions/{mission_id}/recommendations",
    response_model=list[RecommendationRead],
)
def mission_recommendations(
    mission_id: int,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> list[RecommendationRead]:
    rows = rec_service.list_recommendations(
        db, mission_id=mission_id, status=status_filter, limit=200
    )
    return [RecommendationRead.model_validate(r) for r in rows]


@router.post(
    "/recommendations/{rec_id}/decide", response_model=RecommendationRead
)
def decide_recommendation(
    rec_id: int,
    payload: RecommendationDecision,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RecommendationRead:
    rec = rec_service.decide(
        db,
        rec_id,
        decision=payload.decision,
        decided_by=payload.decided_by or user.email,
        decision_note=payload.decision_note,
    )
    return RecommendationRead.model_validate(rec)


# ---------------------------------------------------------------------------
# simulation
# ---------------------------------------------------------------------------


def _sim_to_read(r) -> SimulationResultRead:
    return SimulationResultRead(
        simulation_type=r.simulation_type,
        seed=r.seed,
        impacted_missions=[ImpactedMissionRead(**vars(m)) for m in r.impacted_missions],
        propagation_paths=[PropagationEdgeRead(**vars(p)) for p in r.propagation_paths],
        pressure_deltas=r.pressure_deltas,
        confidence=r.confidence,
        assumptions=r.assumptions,
        notes=r.notes,
    )


@router.post(
    "/simulations/supplier-failure", response_model=SimulationResultRead
)
def simulate_supplier_failure(
    payload: SupplierFailureRequest, db: Session = Depends(get_db)
) -> SimulationResultRead:
    return _sim_to_read(sim_service.supplier_failure(db, payload.supplier_id))


@router.post(
    "/simulations/approval-delay", response_model=SimulationResultRead
)
def simulate_approval_delay(
    payload: ApprovalDelayRequest, db: Session = Depends(get_db)
) -> SimulationResultRead:
    return _sim_to_read(
        sim_service.approval_delay(
            db, payload.approval_id, delay_hours=payload.delay_hours
        )
    )


@router.post(
    "/simulations/dependency-propagation", response_model=SimulationResultRead
)
def simulate_dependency_propagation(
    payload: DependencyPropagationRequest, db: Session = Depends(get_db)
) -> SimulationResultRead:
    return _sim_to_read(
        sim_service.dependency_propagation(
            db,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            depth=payload.depth,
        )
    )


# ---------------------------------------------------------------------------
# drafting (read-only AI assistance — never auto-sent)
# ---------------------------------------------------------------------------


@router.post(
    "/drafting/executive-summary", response_model=SynthesisResponseRead
)
def draft_executive_summary(
    payload: DraftRequest, db: Session = Depends(get_db)
) -> SynthesisResponseRead:
    if payload.mission_id is None:
        raise HTTPException(status_code=422, detail="mission_id is required")
    return _synth_to_read(
        drafting_service.executive_summary_draft(db, payload.mission_id)
    )


@router.post(
    "/drafting/approval-summary", response_model=SynthesisResponseRead
)
def draft_approval_summary(
    payload: DraftRequest, db: Session = Depends(get_db)
) -> SynthesisResponseRead:
    if payload.approval_id is None:
        raise HTTPException(status_code=422, detail="approval_id is required")
    return _synth_to_read(
        drafting_service.approval_summary_draft(db, payload.approval_id)
    )


@router.post(
    "/drafting/escalation-brief", response_model=SynthesisResponseRead
)
def draft_escalation_brief(
    payload: DraftRequest, db: Session = Depends(get_db)
) -> SynthesisResponseRead:
    if payload.mission_id is None:
        raise HTTPException(status_code=422, detail="mission_id is required")
    return _synth_to_read(
        drafting_service.escalation_brief_draft(
            db, payload.mission_id, hours=payload.hours or 48
        )
    )


@router.post(
    "/drafting/investor-followup", response_model=SynthesisResponseRead
)
def draft_investor_followup(
    payload: DraftRequest, db: Session = Depends(get_db)
) -> SynthesisResponseRead:
    if payload.opportunity_id is None:
        raise HTTPException(status_code=422, detail="opportunity_id is required")
    return _synth_to_read(
        drafting_service.investor_followup_draft(db, payload.opportunity_id)
    )


@router.post(
    "/drafting/supplier-outreach", response_model=SynthesisResponseRead
)
def draft_supplier_outreach(
    payload: DraftRequest, db: Session = Depends(get_db)
) -> SynthesisResponseRead:
    if payload.supplier_id is None:
        raise HTTPException(status_code=422, detail="supplier_id is required")
    return _synth_to_read(
        drafting_service.supplier_outreach_draft(db, payload.supplier_id)
    )
