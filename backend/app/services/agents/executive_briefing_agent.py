"""ExecutiveBriefingAgent — stages a grounded executive briefing draft.

Bounded scope:
  - reads:    intel + memory via the RAG pipeline
  - proposes: stage_executive_brief_publish
  - approves: human required
"""

from __future__ import annotations

from app.services.agents import register
from app.services.agents.base import (
    BaseAgent,
    StageContext,
    StageResult,
)
from app.services.executive_brief import daily_brief


class ExecutiveBriefingAgent(BaseAgent):
    name = "executive_briefing_agent"
    version = "0.1.0"
    purpose = (
        "Generates a grounded executive briefing draft (RAG over the last 24h). "
        "Stages a publish-proposal so leadership review is explicit."
    )
    allowed_actions = ("stage_executive_brief_publish",)
    required_approvals = ("stage_executive_brief_publish",)
    accessible_domains = ("intel_item", "operational_event", "approval", "mission")
    confidence_threshold = 50
    workflow_key = "executive.brief"

    def _pipeline(self):
        return [synthesize_brief, propose_publish]


def synthesize_brief(ctx: StageContext) -> StageResult:
    resp = daily_brief(ctx.db, hours=24)
    ctx.outputs["brief"] = {
        "objective": resp.objective,
        "summary": resp.summary,
        "confidence": resp.confidence,
        "weak_retrieval": resp.weak_retrieval,
        "citation_count": len(resp.citations),
        "embedding_model": resp.retrieval_trace.embedding_model,
    }
    return StageResult(
        output_payload={
            "weak_retrieval": resp.weak_retrieval,
            "confidence": resp.confidence,
        },
        retrieval_trace={
            "candidates": resp.retrieval_trace.candidates_considered,
            "returned": resp.retrieval_trace.chunks_returned,
            "embedding_model": resp.retrieval_trace.embedding_model,
        },
        confidence=int(resp.confidence * 100),
        skip_remaining=resp.weak_retrieval,
    )


def propose_publish(ctx: StageContext) -> StageResult:
    brief = ctx.outputs.get("brief", {})
    if brief.get("weak_retrieval"):
        return StageResult(
            output_payload={"skipped": "weak_retrieval"}, confidence=0
        )
    from app.services.agents import get as get_agent

    ag = get_agent(ctx.operation.agent_name)
    if ag is None:
        return StageResult(output_payload={}, confidence=0)
    ag.stage_action(
        ctx,
        action_type="stage_executive_brief_publish",
        target_entity_type=None,
        target_entity_id=None,
        payload={
            "objective": brief.get("objective"),
            "summary": brief.get("summary"),
            "confidence": brief.get("confidence"),
            "citation_count": brief.get("citation_count"),
            "rationale": (
                "Daily brief synthesized from grounded retrieval; "
                "publication requires leadership approval."
            ),
        },
        requires_approval=True,
    )
    ctx.outputs["reasoning"] = "Executive brief proposed; awaiting human approval."
    return StageResult(
        output_payload={"proposed": 1},
        confidence=int(brief.get("confidence", 0) * 100),
    )


register(ExecutiveBriefingAgent())
