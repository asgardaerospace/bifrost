from datetime import datetime
from typing import Any, Literal, Optional, Union

from pydantic import Field

from app.schemas.base import ORMModel
from app.schemas.communication import CommunicationRead
from app.schemas.executive import (
    ActionItem,
    ActionQueue,
    Alert,
    AlertBundle,
    DailyBriefing,
)
from app.schemas.graph import (
    AccountProgramMatches,
    InvestorProgramMatches,
    ProgramInvestorMatches,
    ProgramSupplierMatches,
    RecommendationBundle,
)
from app.schemas.intel import IntelItemRead
from app.schemas.investor_agent import (
    AgentPipelineSummary,
    InvestorBrief,
    PrioritizedOpportunity,
)
from app.schemas.pipeline import OpportunitySummary
from app.schemas.workflow import WorkflowRunRead


CommandClass = Literal["read", "analyze", "draft", "plan", "execute", "review"]
CommandStatus = Literal[
    "completed", "clarification_needed", "unsupported", "failed"
]


class EntityRef(ORMModel):
    entity_type: str
    entity_id: int
    label: Optional[str] = None


class CommandClassification(ORMModel):
    command_class: CommandClass
    intent: str
    confidence: Literal["high", "medium", "low"]
    domain: Literal[
        "investor",
        "market",
        "program",
        "supplier",
        "executive",
        "graph",
        "intel",
    ]
    referenced_entity: Optional[EntityRef] = None
    matched_keywords: list[str] = []


# ---------------------------------------------------------------------------
# output variants
# ---------------------------------------------------------------------------

class SummaryOutput(ORMModel):
    output_type: Literal["summary"] = "summary"
    headline: str
    key_insights: list[str] = []
    supporting_data: dict[str, Any] = {}
    next_actions: list[str] = []
    pipeline_summary: Optional[AgentPipelineSummary] = None
    investor_brief: Optional[InvestorBrief] = None


class RankedOutput(ORMModel):
    output_type: Literal["ranked"] = "ranked"
    headline: str
    scoring_logic: str
    items: list[PrioritizedOpportunity] = []
    opportunities: list[OpportunitySummary] = []


class DraftOutput(ORMModel):
    output_type: Literal["draft"] = "draft"
    headline: str
    communication: CommunicationRead
    rationale: str
    missing_context: list[str] = []
    workflow_run: Optional[WorkflowRunRead] = None


class WorkflowOutput(ORMModel):
    output_type: Literal["workflow"] = "workflow"
    headline: str
    workflow_key: str
    workflow_run: WorkflowRunRead
    approval_required: bool
    actions_created: list[str] = []


class ReviewItem(ORMModel):
    entity_type: str
    entity_id: int
    summary: str
    status: str
    link_hint: Optional[str] = None


class ReviewOutput(ORMModel):
    output_type: Literal["review"] = "review"
    headline: str
    pending_approvals: list[ReviewItem] = []
    blocked_items: list[ReviewItem] = []


class EngineInvestorRow(ORMModel):
    """Trimmed investor-engine record for command console rendering.

    Mirrors the fields that the list/detail UIs surface so the renderer
    does not need the full NormalizedInvestor shape.
    """

    external_id: str
    firm_name: str
    stage: Optional[str] = None
    owner: Optional[str] = None
    follow_up_status: Optional[str] = None
    last_touch_at: Optional[datetime] = None
    next_follow_up_at: Optional[datetime] = None
    next_step: Optional[str] = None


class EngineListOutput(ORMModel):
    output_type: Literal["engine_list"] = "engine_list"
    headline: str
    source: Literal["investor_engine"] = "investor_engine"
    rationale: Optional[str] = None
    investors: list[EngineInvestorRow] = []
    counts: dict[str, int] = {}


class MarketAccountRow(ORMModel):
    id: int
    name: str
    sector: Optional[str] = None
    region: Optional[str] = None
    type: Optional[str] = None


class MarketCampaignRow(ORMModel):
    id: int
    name: str
    sector: Optional[str] = None
    region: Optional[str] = None
    status: str


class MarketOpportunityRow(ORMModel):
    id: int
    account_id: int
    account_name: Optional[str] = None
    name: str
    stage: str
    sector: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due_at: Optional[datetime] = None
    estimated_value: Optional[float] = None


class MarketFollowUpRow(ORMModel):
    link_id: int
    account_id: int
    account_name: Optional[str] = None
    campaign_id: int
    campaign_name: Optional[str] = None
    status: str
    next_follow_up_at: Optional[datetime] = None
    last_contacted_at: Optional[datetime] = None


class MarketListOutput(ORMModel):
    output_type: Literal["market_list"] = "market_list"
    headline: str
    kind: Literal[
        "accounts", "campaigns", "opportunities", "follow_ups", "by_sector"
    ]
    rationale: Optional[str] = None
    accounts: list[MarketAccountRow] = []
    campaigns: list[MarketCampaignRow] = []
    opportunities: list[MarketOpportunityRow] = []
    follow_ups: list[MarketFollowUpRow] = []
    counts: dict[str, int] = {}
    by_sector: dict[str, list[MarketOpportunityRow]] = {}


class ProgramRow(ORMModel):
    id: int
    name: str
    account_id: int
    account_name: Optional[str] = None
    stage: str
    owner: Optional[str] = None
    estimated_value: Optional[float] = None
    probability_score: Optional[int] = None
    strategic_value_score: Optional[int] = None
    next_step: Optional[str] = None
    next_step_due_at: Optional[datetime] = None


class ProgramStageBucket(ORMModel):
    stage: str
    count: int


class ProgramListOutput(ORMModel):
    output_type: Literal["program_list"] = "program_list"
    headline: str
    kind: Literal["active", "high_value", "overdue", "by_stage", "pipeline"]
    rationale: Optional[str] = None
    programs: list[ProgramRow] = []
    stage_counts: list[ProgramStageBucket] = []
    counts: dict[str, int] = {}
    totals: dict[str, float] = {}


class SupplierRow(ORMModel):
    id: int
    name: str
    type: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    onboarding_status: str
    preferred_partner_score: Optional[int] = None
    capabilities: list[str] = []
    certifications: list[str] = []


class ProgramSupplierRow(ORMModel):
    link_id: int
    program_id: int
    program_name: Optional[str] = None
    supplier_id: int
    supplier_name: Optional[str] = None
    role: str
    status: str


class SupplierListOutput(ORMModel):
    output_type: Literal["supplier_list"] = "supplier_list"
    headline: str
    kind: Literal[
        "all",
        "qualified",
        "by_capability",
        "by_region",
        "for_program",
        "onboarding",
    ]
    rationale: Optional[str] = None
    suppliers: list[SupplierRow] = []
    program_links: list[ProgramSupplierRow] = []
    by_capability: dict[str, list[SupplierRow]] = {}
    by_region: dict[str, list[SupplierRow]] = {}
    counts: dict[str, int] = {}


class ExecutiveBriefingOutput(ORMModel):
    output_type: Literal["executive_briefing"] = "executive_briefing"
    headline: str
    briefing: DailyBriefing


class ExecutiveActionQueueOutput(ORMModel):
    output_type: Literal["executive_action_queue"] = "executive_action_queue"
    headline: str
    queue: ActionQueue


class ExecutiveAlertsOutput(ORMModel):
    output_type: Literal["executive_alerts"] = "executive_alerts"
    headline: str
    alerts: AlertBundle


class GraphInvestorMatchesOutput(ORMModel):
    output_type: Literal["graph_investor_matches"] = "graph_investor_matches"
    headline: str
    matches: ProgramInvestorMatches


class GraphSupplierMatchesOutput(ORMModel):
    output_type: Literal["graph_supplier_matches"] = "graph_supplier_matches"
    headline: str
    matches: ProgramSupplierMatches


class GraphAccountProgramsOutput(ORMModel):
    output_type: Literal["graph_account_programs"] = "graph_account_programs"
    headline: str
    matches: AccountProgramMatches


class GraphInvestorProgramsOutput(ORMModel):
    output_type: Literal["graph_investor_programs"] = "graph_investor_programs"
    headline: str
    matches: InvestorProgramMatches


class GraphRecommendationsOutput(ORMModel):
    output_type: Literal["graph_recommendations"] = "graph_recommendations"
    headline: str
    recommendations: RecommendationBundle


class IntelListOutput(ORMModel):
    output_type: Literal["intel_list"] = "intel_list"
    headline: str
    kind: Literal[
        "top_signals",
        "news_today",
        "vc_activity",
        "defense_funding",
        "top_movers",
        "by_region",
        "by_category",
        "watchlist",
    ]
    rationale: Optional[str] = None
    items: list[IntelItemRead] = []
    by_category: dict[str, list[IntelItemRead]] = {}
    by_region: dict[str, list[IntelItemRead]] = {}
    counts: dict[str, int] = {}


class ClarificationOutput(ORMModel):
    output_type: Literal["clarification"] = "clarification"
    headline: str
    message: str
    candidates: list[EntityRef] = []
    suggested_inputs: list[str] = []


class UnsupportedOutput(ORMModel):
    output_type: Literal["unsupported"] = "unsupported"
    headline: str
    reason: str
    supported_examples: list[str] = []


CommandOutput = Union[
    SummaryOutput,
    RankedOutput,
    DraftOutput,
    WorkflowOutput,
    ReviewOutput,
    EngineListOutput,
    MarketListOutput,
    ProgramListOutput,
    SupplierListOutput,
    ExecutiveBriefingOutput,
    ExecutiveActionQueueOutput,
    ExecutiveAlertsOutput,
    GraphInvestorMatchesOutput,
    GraphSupplierMatchesOutput,
    GraphAccountProgramsOutput,
    GraphInvestorProgramsOutput,
    GraphRecommendationsOutput,
    IntelListOutput,
    ClarificationOutput,
    UnsupportedOutput,
]


# ---------------------------------------------------------------------------
# request / response envelopes
# ---------------------------------------------------------------------------

class CommandRequest(ORMModel):
    text: str = Field(min_length=1, max_length=2000)
    actor: Optional[str] = None
    context_entity: Optional[EntityRef] = None


class CommandResponse(ORMModel):
    command_text: str
    normalized_text: str
    classification: CommandClassification
    status: CommandStatus
    output: CommandOutput = Field(discriminator="output_type")
    records_created: list[EntityRef] = []
    duration_ms: int
    executed_at: datetime
    history_id: Optional[int] = None


class CommandHistoryItem(ORMModel):
    id: int
    command_text: str
    normalized_text: Optional[str] = None
    command_class: Optional[str] = None
    referenced_entity_type: Optional[str] = None
    referenced_entity_id: Optional[int] = None
    output_type: Optional[str] = None
    records_created: bool = False
    status: Optional[str] = None
    duration_ms: Optional[int] = None
    actor: Optional[str] = None
    created_at: datetime
