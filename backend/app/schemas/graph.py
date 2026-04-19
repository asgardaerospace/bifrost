"""Graph Intelligence Layer schemas.

Everything here is read-side output. The graph service does not mint new
persistent entities — it derives rule-based edges from existing domain
tables. All scoring fields are deterministic and inspectable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from app.schemas.base import ORMModel


# ---------------------------------------------------------------------------
# entity refs (graph-local, independent of command_console.EntityRef)
# ---------------------------------------------------------------------------

GraphEntityType = Literal[
    "program", "investor_firm", "account", "supplier"
]


class GraphEntity(ORMModel):
    type: GraphEntityType
    id: int
    name: str


# ---------------------------------------------------------------------------
# matches (one edge with score + reasoning)
# ---------------------------------------------------------------------------


class InvestorMatch(ORMModel):
    investor_id: int
    investor_name: str
    stage_focus: Optional[str] = None
    location: Optional[str] = None
    score: int  # 0..100
    factors: list[str]  # e.g. ["sector: defense", "stage: growth"]
    already_linked: bool = False
    relevance_type: Optional[str] = None  # if already_linked


class SupplierMatch(ORMModel):
    supplier_id: int
    supplier_name: str
    type: Optional[str] = None
    region: Optional[str] = None
    onboarding_status: str
    preferred_partner_score: Optional[int] = None
    capabilities: list[str] = []
    certifications: list[str] = []
    score: int  # 0..100
    factors: list[str]
    already_linked: bool = False
    role: Optional[str] = None
    status: Optional[str] = None


class ProgramMatch(ORMModel):
    """Edge from an investor or account to a program."""

    program_id: int
    program_name: str
    account_id: int
    account_name: Optional[str] = None
    stage: str
    estimated_value: Optional[float] = None
    strategic_value_score: Optional[int] = None
    score: int
    factors: list[str]
    already_linked: bool = False
    link_role: Optional[str] = None  # for account→program: prime/partner/customer
    relevance_type: Optional[str] = None  # for investor→program


# ---------------------------------------------------------------------------
# envelopes
# ---------------------------------------------------------------------------


class ProgramInvestorMatches(ORMModel):
    program_id: int
    program_name: str
    generated_at: datetime
    scoring_logic: str
    matches: list[InvestorMatch]


class ProgramSupplierMatches(ORMModel):
    program_id: int
    program_name: str
    generated_at: datetime
    scoring_logic: str
    matches: list[SupplierMatch]


class AccountProgramMatches(ORMModel):
    account_id: int
    account_name: str
    generated_at: datetime
    scoring_logic: str
    matches: list[ProgramMatch]


class InvestorProgramMatches(ORMModel):
    investor_id: int
    investor_name: str
    generated_at: datetime
    scoring_logic: str
    matches: list[ProgramMatch]


# ---------------------------------------------------------------------------
# recommendations
# ---------------------------------------------------------------------------

RecommendationType = Literal[
    "investor_for_program",
    "supplier_for_program",
    "account_to_pursue",
    "program_at_risk_no_supplier",
    "program_at_risk_no_investor",
    "cross_domain_opportunity",
]


class Recommendation(ORMModel):
    id: str  # deterministic, e.g. "rec.investor_for_program.12.7"
    type: RecommendationType
    headline: str
    reasoning: str
    confidence_score: int  # 0..100
    recommended_action: str
    related_entities: list[GraphEntity]
    link_hint: Optional[str] = None


class RecommendationBundle(ORMModel):
    generated_at: datetime
    total: int
    counts_by_type: dict[str, int]
    recommendations: list[Recommendation]
