"""Rule-based command classifier.

Deterministic keyword + regex matching drives command_class, intent, and
entity resolution. No LLM required. Intent strings are stable identifiers
consumed by the executor.

Classification is intentionally narrow — unknown commands return
``intent="unknown"`` so the executor can emit a structured unsupported
response rather than guessing.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.investor import InvestorFirm, InvestorOpportunity
from app.schemas.command_console import (
    CommandClass,
    CommandClassification,
    EntityRef,
)

INTENT_PIPELINE_SUMMARY = "investor.pipeline_summary"
INTENT_OVERDUE = "investor.overdue_follow_ups"
INTENT_STALE = "investor.stale_opportunities"
INTENT_BRIEF = "investor.opportunity_brief"
INTENT_PENDING_APPROVALS = "investor.pending_approvals"
INTENT_PRIORITIZE = "investor.prioritize_opportunities"
INTENT_PLAN_THIS_WEEK = "investor.plan_this_week"
INTENT_FOLLOW_UP_DRAFT = "investor.follow_up_draft"
INTENT_REVIEW_BLOCKED = "investor.blocked_items"

# Investor-engine intents (external system — read-only surface).
INTENT_ENGINE_SUMMARY = "investor_engine.summary"
INTENT_ENGINE_FOLLOW_UPS_DUE = "investor_engine.follow_ups_due"
INTENT_ENGINE_STALE = "investor_engine.stale"
INTENT_ENGINE_BY_OWNER = "investor_engine.by_owner"
INTENT_ENGINE_OPEN_RECORD = "investor_engine.open_record"
INTENT_ENGINE_FOLLOW_UP_DRAFT = "investor_engine.follow_up_draft"

INTENT_UNKNOWN = "unknown"

# Market OS intents
INTENT_MARKET_ACCOUNTS = "market.accounts"
INTENT_MARKET_CAMPAIGNS = "market.campaigns"
INTENT_MARKET_OPPORTUNITIES = "market.opportunities"
INTENT_MARKET_FOLLOW_UPS = "market.follow_ups"
INTENT_MARKET_BY_SECTOR = "market.opportunities_by_sector"

# Executive OS intents
INTENT_EXEC_BRIEFING = "executive.briefing"
INTENT_EXEC_QUEUE = "executive.action_queue"
INTENT_EXEC_ALERTS = "executive.alerts"
INTENT_EXEC_OVERDUE_ALL = "executive.overdue_all"
INTENT_EXEC_BLOCKED_PROGRAMS = "executive.blocked_programs"
INTENT_EXEC_SUPPLIER_ISSUES = "executive.supplier_issues"
INTENT_EXEC_INVESTOR_PRIORITIES = "executive.investor_priorities"

# Supplier OS intents
INTENT_SUPPLIER_ALL = "supplier.all"
INTENT_SUPPLIER_QUALIFIED = "supplier.qualified"
INTENT_SUPPLIER_BY_CAPABILITY = "supplier.by_capability"
INTENT_SUPPLIER_FOR_PROGRAM = "supplier.for_program"
INTENT_SUPPLIER_ONBOARDING = "supplier.onboarding"

# Graph intents
INTENT_GRAPH_INVESTORS_FOR_PROGRAM = "graph.investors_for_program"
INTENT_GRAPH_SUPPLIERS_FOR_PROGRAM = "graph.suppliers_for_program"
INTENT_GRAPH_ACCOUNTS_TO_TARGET = "graph.accounts_to_target"
INTENT_GRAPH_RECOMMENDATIONS = "graph.recommendations"

# Program OS intents
INTENT_PROGRAM_ACTIVE = "program.active"
INTENT_PROGRAM_HIGH_VALUE = "program.high_value"
INTENT_PROGRAM_BY_STAGE = "program.by_stage"
INTENT_PROGRAM_OVERDUE = "program.overdue"
INTENT_PROGRAM_PIPELINE = "program.pipeline"

# Ordering matters: more specific intents first.
INTENT_RULES: list[tuple[str, CommandClass, list[str]]] = [
    # (intent, class, keyword patterns — all terms must be present)
    # --- graph intelligence (must win over every domain rule) ---
    (INTENT_GRAPH_RECOMMENDATIONS, "analyze", ["recommended", "actions"]),
    (INTENT_GRAPH_RECOMMENDATIONS, "analyze", ["show", "recommendations"]),
    (INTENT_GRAPH_RECOMMENDATIONS, "analyze", ["recommendations"]),
    (INTENT_GRAPH_INVESTORS_FOR_PROGRAM, "analyze", ["which", "investors", "match"]),
    (INTENT_GRAPH_INVESTORS_FOR_PROGRAM, "analyze", ["investors", "match", "program"]),
    (INTENT_GRAPH_INVESTORS_FOR_PROGRAM, "analyze", ["investors", "for", "program"]),
    (INTENT_GRAPH_SUPPLIERS_FOR_PROGRAM, "analyze", ["which", "suppliers", "can", "support"]),
    (INTENT_GRAPH_SUPPLIERS_FOR_PROGRAM, "analyze", ["suppliers", "can", "support"]),
    (INTENT_GRAPH_SUPPLIERS_FOR_PROGRAM, "analyze", ["match", "suppliers", "program"]),
    (INTENT_GRAPH_ACCOUNTS_TO_TARGET, "analyze", ["what", "accounts", "should"]),
    (INTENT_GRAPH_ACCOUNTS_TO_TARGET, "analyze", ["accounts", "should", "we", "target"]),
    (INTENT_GRAPH_ACCOUNTS_TO_TARGET, "analyze", ["accounts", "to", "target"]),
    (INTENT_GRAPH_ACCOUNTS_TO_TARGET, "analyze", ["accounts", "to", "pursue"]),
    # --- executive os (must win over every domain rule) ---
    (INTENT_EXEC_BRIEFING, "read", ["matters", "most"]),
    (INTENT_EXEC_BRIEFING, "read", ["daily", "briefing"]),
    (INTENT_EXEC_BRIEFING, "read", ["executive", "briefing"]),
    (INTENT_EXEC_BRIEFING, "read", ["brief", "me"]),
    (INTENT_EXEC_QUEUE, "read", ["action", "queue"]),
    (INTENT_EXEC_QUEUE, "read", ["my", "actions"]),
    (INTENT_EXEC_QUEUE, "read", ["what", "should", "i", "do"]),
    (INTENT_EXEC_ALERTS, "read", ["top", "risks"]),
    (INTENT_EXEC_ALERTS, "read", ["show", "risks"]),
    (INTENT_EXEC_ALERTS, "read", ["show", "alerts"]),
    (INTENT_EXEC_ALERTS, "read", ["cross", "domain", "alerts"]),
    (INTENT_EXEC_OVERDUE_ALL, "read", ["overdue", "across"]),
    (INTENT_EXEC_OVERDUE_ALL, "read", ["overdue", "everything"]),
    (INTENT_EXEC_OVERDUE_ALL, "read", ["overdue", "items"]),
    (INTENT_EXEC_OVERDUE_ALL, "read", ["overdue", "system"]),
    (INTENT_EXEC_BLOCKED_PROGRAMS, "read", ["blocked", "programs"]),
    (INTENT_EXEC_SUPPLIER_ISSUES, "read", ["supplier", "issues"]),
    (INTENT_EXEC_INVESTOR_PRIORITIES, "read", ["investor", "priorities"]),
    # --- supplier os (specific phrases; must win over generic rules) ---
    (INTENT_SUPPLIER_ONBOARDING, "read", ["onboarding", "pipeline"]),
    (INTENT_SUPPLIER_ONBOARDING, "read", ["supplier", "onboarding"]),
    (INTENT_SUPPLIER_FOR_PROGRAM, "read", ["suppliers", "for", "program"]),
    (INTENT_SUPPLIER_FOR_PROGRAM, "read", ["suppliers", "for"]),
    (INTENT_SUPPLIER_BY_CAPABILITY, "read", ["suppliers", "by", "capability"]),
    (INTENT_SUPPLIER_BY_CAPABILITY, "read", ["suppliers", "capability"]),
    (INTENT_SUPPLIER_QUALIFIED, "read", ["qualified", "suppliers"]),
    (INTENT_SUPPLIER_ALL, "read", ["show", "suppliers"]),
    (INTENT_SUPPLIER_ALL, "read", ["list", "suppliers"]),
    (INTENT_SUPPLIER_ALL, "read", ["suppliers"]),
    # --- program os (specific phrases; must win over generic rules) ---
    (INTENT_PROGRAM_PIPELINE, "read", ["program", "pipeline"]),
    (INTENT_PROGRAM_PIPELINE, "read", ["programs", "pipeline"]),
    (INTENT_PROGRAM_OVERDUE, "read", ["overdue", "programs"]),
    (INTENT_PROGRAM_OVERDUE, "read", ["programs", "overdue"]),
    (INTENT_PROGRAM_BY_STAGE, "read", ["programs", "by", "stage"]),
    (INTENT_PROGRAM_BY_STAGE, "read", ["programs", "stage"]),
    (INTENT_PROGRAM_HIGH_VALUE, "read", ["high", "value", "programs"]),
    (INTENT_PROGRAM_HIGH_VALUE, "read", ["high", "value", "program"]),
    (INTENT_PROGRAM_ACTIVE, "read", ["active", "programs"]),
    (INTENT_PROGRAM_ACTIVE, "read", ["show", "programs"]),
    (INTENT_PROGRAM_ACTIVE, "read", ["list", "programs"]),
    # --- market os (must win over generic investor rules) ---
    (INTENT_MARKET_BY_SECTOR, "read", ["opportunities", "by", "sector"]),
    (INTENT_MARKET_BY_SECTOR, "read", ["opportunities", "sector"]),
    (INTENT_MARKET_FOLLOW_UPS, "read", ["accounts", "needing", "follow"]),
    (INTENT_MARKET_FOLLOW_UPS, "read", ["accounts", "follow"]),
    (INTENT_MARKET_FOLLOW_UPS, "read", ["account", "follow"]),
    (INTENT_MARKET_OPPORTUNITIES, "read", ["market", "opportunities"]),
    (INTENT_MARKET_OPPORTUNITIES, "read", ["show", "market"]),
    (INTENT_MARKET_CAMPAIGNS, "read", ["active", "campaigns"]),
    (INTENT_MARKET_CAMPAIGNS, "read", ["campaigns"]),
    (INTENT_MARKET_ACCOUNTS, "read", ["target", "accounts"]),
    (INTENT_MARKET_ACCOUNTS, "read", ["show", "accounts"]),
    (INTENT_MARKET_ACCOUNTS, "read", ["list", "accounts"]),
    # --- investor engine (must win over generic rules below) ---
    (INTENT_ENGINE_FOLLOW_UP_DRAFT, "draft", ["engine", "draft"]),
    (INTENT_ENGINE_FOLLOW_UP_DRAFT, "draft", ["engine", "follow", "up"]),
    (INTENT_ENGINE_FOLLOW_UP_DRAFT, "draft", ["draft", "engine"]),
    (INTENT_ENGINE_OPEN_RECORD, "read", ["open", "engine"]),
    (INTENT_ENGINE_BY_OWNER, "read", ["engine", "owner"]),
    (INTENT_ENGINE_BY_OWNER, "read", ["engine", "records", "for"]),
    (INTENT_ENGINE_STALE, "read", ["engine", "stale"]),
    (INTENT_ENGINE_STALE, "read", ["stale", "engine"]),
    (INTENT_ENGINE_FOLLOW_UPS_DUE, "read", ["engine", "follow"]),
    (INTENT_ENGINE_FOLLOW_UPS_DUE, "read", ["needing", "follow"]),
    (INTENT_ENGINE_FOLLOW_UPS_DUE, "read", ["follow", "ups", "due"]),
    (INTENT_ENGINE_SUMMARY, "read", ["engine", "summary"]),
    (INTENT_ENGINE_SUMMARY, "read", ["investor", "engine"]),
    # --- native bifrost intents ---
    (INTENT_FOLLOW_UP_DRAFT, "draft", ["follow", "up"]),
    (INTENT_FOLLOW_UP_DRAFT, "draft", ["draft"]),
    (INTENT_BRIEF, "read", ["brief"]),
    (INTENT_PENDING_APPROVALS, "review", ["pending", "approval"]),
    (INTENT_PENDING_APPROVALS, "review", ["approval"]),
    (INTENT_REVIEW_BLOCKED, "review", ["blocked"]),
    (INTENT_OVERDUE, "read", ["overdue"]),
    (INTENT_STALE, "read", ["stale"]),
    (INTENT_PRIORITIZE, "analyze", ["rank"]),
    (INTENT_PRIORITIZE, "analyze", ["prioritize"]),
    (INTENT_PRIORITIZE, "analyze", ["most", "likely"]),
    (INTENT_PLAN_THIS_WEEK, "plan", ["this", "week"]),
    (INTENT_PLAN_THIS_WEEK, "plan", ["focus"]),
    (INTENT_PLAN_THIS_WEEK, "plan", ["top", "priorit"]),
    (INTENT_PIPELINE_SUMMARY, "read", ["pipeline"]),
    (INTENT_PIPELINE_SUMMARY, "read", ["show", "investor"]),
]

OPPORTUNITY_ID_PATTERNS = [
    re.compile(r"\bopportunity\s+#?(\d+)\b", re.IGNORECASE),
    re.compile(r"\bopp\s+#?(\d+)\b", re.IGNORECASE),
    re.compile(r"\bopportunity[_-]?id[:= ]+(\d+)\b", re.IGNORECASE),
]

FOR_PATTERN = re.compile(
    r"\bfor\s+([A-Za-z0-9][A-Za-z0-9&'.\- ]{1,60})\b", re.IGNORECASE
)


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _classify_intent(normalized: str) -> tuple[str, CommandClass, list[str]]:
    for intent, cmd_class, terms in INTENT_RULES:
        if all(t in normalized for t in terms):
            return intent, cmd_class, terms
    return INTENT_UNKNOWN, "read", []


def _resolve_opportunity_by_id(
    db: Session, opp_id: int
) -> Optional[InvestorOpportunity]:
    opp = db.get(InvestorOpportunity, opp_id)
    if opp is None or opp.deleted_at is not None:
        return None
    return opp


def _resolve_firm_name(
    db: Session, raw: str
) -> Optional[InvestorFirm]:
    candidate = raw.strip().rstrip("?.! ").strip()
    if not candidate:
        return None

    stmt = (
        select(InvestorFirm)
        .where(InvestorFirm.deleted_at.is_(None))
        .where(func.lower(InvestorFirm.name) == candidate.lower())
    )
    firm = db.scalars(stmt).first()
    if firm is not None:
        return firm

    # Fallback: prefix match on lowercase name.
    stmt = (
        select(InvestorFirm)
        .where(InvestorFirm.deleted_at.is_(None))
        .where(func.lower(InvestorFirm.name).like(candidate.lower() + "%"))
        .limit(2)
    )
    matches = db.scalars(stmt).all()
    if len(matches) == 1:
        return matches[0]
    return None


def _firm_single_opportunity(
    db: Session, firm_id: int
) -> Optional[InvestorOpportunity]:
    stmt = (
        select(InvestorOpportunity)
        .where(InvestorOpportunity.firm_id == firm_id)
        .where(InvestorOpportunity.deleted_at.is_(None))
    )
    rows = db.scalars(stmt).all()
    if len(rows) == 1:
        return rows[0]
    return None


def _resolve_entity(
    db: Session, raw: str, normalized: str
) -> Optional[EntityRef]:
    for pattern in OPPORTUNITY_ID_PATTERNS:
        m = pattern.search(raw)
        if m:
            opp = _resolve_opportunity_by_id(db, int(m.group(1)))
            if opp is not None:
                return EntityRef(
                    entity_type="investor_opportunity",
                    entity_id=opp.id,
                    label=f"opportunity #{opp.id}",
                )

    m = FOR_PATTERN.search(raw)
    if m:
        firm = _resolve_firm_name(db, m.group(1))
        if firm is not None:
            opp = _firm_single_opportunity(db, firm.id)
            if opp is not None:
                return EntityRef(
                    entity_type="investor_opportunity",
                    entity_id=opp.id,
                    label=firm.name,
                )
            return EntityRef(
                entity_type="investor_firm",
                entity_id=firm.id,
                label=firm.name,
            )

    return None


def _confidence(intent: str, matched: list[str], entity: Optional[EntityRef]) -> str:
    if intent == INTENT_UNKNOWN:
        return "low"
    if len(matched) >= 2 or entity is not None:
        return "high"
    return "medium"


def classify(
    db: Session, raw_text: str, *, context_entity: Optional[EntityRef] = None
) -> tuple[str, CommandClassification]:
    normalized = _normalize(raw_text)
    intent, cmd_class, matched = _classify_intent(normalized)

    # Engine intents resolve their own targets (firm-by-name in the
    # snapshot cache). Skip Bifrost-side entity resolution so we don't
    # attach a native firm to an engine command.
    if (
        intent.startswith("investor_engine.")
        or intent.startswith("market.")
        or intent.startswith("program.")
        or intent.startswith("supplier.")
        or intent.startswith("executive.")
        or intent.startswith("graph.")
    ):
        entity = None
    else:
        entity = _resolve_entity(db, raw_text, normalized)
        if entity is None and context_entity is not None:
            entity = context_entity

    if intent.startswith("market."):
        domain = "market"
    elif intent.startswith("program."):
        domain = "program"
    elif intent.startswith("supplier."):
        domain = "supplier"
    elif intent.startswith("executive."):
        domain = "executive"
    elif intent.startswith("graph."):
        domain = "graph"
    else:
        domain = "investor"

    return normalized, CommandClassification(
        command_class=cmd_class,
        intent=intent,
        confidence=_confidence(intent, matched, entity),  # type: ignore[arg-type]
        domain=domain,  # type: ignore[arg-type]
        referenced_entity=entity,
        matched_keywords=matched,
    )
