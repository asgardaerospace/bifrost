"""HTTP endpoints for the Graph Intelligence Layer."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.graph import (
    AccountProgramMatches,
    InvestorProgramMatches,
    ProgramInvestorMatches,
    ProgramSupplierMatches,
    RecommendationBundle,
)
from app.services import graph as graph_service
from app.services import recommendations as recommendations_service

router = APIRouter()


@router.get(
    "/graph/program/{program_id}/investors",
    response_model=ProgramInvestorMatches,
)
def program_investor_matches(
    program_id: int,
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ProgramInvestorMatches:
    return graph_service.match_investors_for_program(db, program_id, limit=limit)


@router.get(
    "/graph/program/{program_id}/suppliers",
    response_model=ProgramSupplierMatches,
)
def program_supplier_matches(
    program_id: int,
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ProgramSupplierMatches:
    return graph_service.match_suppliers_for_program(db, program_id, limit=limit)


@router.get(
    "/graph/account/{account_id}/programs",
    response_model=AccountProgramMatches,
)
def account_program_matches(
    account_id: int,
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AccountProgramMatches:
    return graph_service.match_programs_for_account(db, account_id, limit=limit)


@router.get(
    "/graph/investor/{investor_id}/programs",
    response_model=InvestorProgramMatches,
)
def investor_program_matches(
    investor_id: int,
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> InvestorProgramMatches:
    return graph_service.match_programs_for_investor(db, investor_id, limit=limit)


@router.get("/graph/recommendations", response_model=RecommendationBundle)
def recommendations(
    type: Optional[list[str]] = Query(
        None,
        description=(
            "Optional filter by recommendation type. Repeat query param to "
            "request multiple types."
        ),
    ),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> RecommendationBundle:
    return recommendations_service.build_recommendations(
        db, types=type, limit=limit
    )
