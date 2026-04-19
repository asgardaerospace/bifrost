"""Development seed data for Bifrost.

Run with:
    python -m app.scripts.seed_dev_data

Wipes Phase 1 tables and inserts realistic investor pipeline data covering
all dashboard, command-console, timeline, and approval flows. Safe to rerun
— it TRUNCATEs before inserting.

All data is fictional. No real firms or people.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.activity import ActivityEvent
from app.models.approval import Approval
from app.models.communication import Communication
from app.models.investor import InvestorContact, InvestorFirm, InvestorOpportunity
from app.models.meeting import Meeting
from app.models.note import Note
from app.models.task import Task
from app.models.workflow import WorkflowRun

ENTITY_OPPORTUNITY = "investor_opportunity"
ENTITY_COMMUNICATION = "communication"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> datetime:
    return _now() - timedelta(days=n)


def _days_ahead(n: int) -> datetime:
    return _now() + timedelta(days=n)


# ---------------------------------------------------------------------------
# wipe
# ---------------------------------------------------------------------------

WIPE_TABLES = [
    "activity_events",
    "entity_tags",
    "tags",
    "documents",
    "approvals",
    "workflow_runs",
    "tasks",
    "notes",
    "meetings",
    "communications",
    "investor_opportunities",
    "investor_contacts",
    "investor_firms",
]


def wipe(db) -> None:
    db.execute(
        text(
            "TRUNCATE TABLE "
            + ", ".join(WIPE_TABLES)
            + " RESTART IDENTITY CASCADE"
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# firms
# ---------------------------------------------------------------------------

FIRM_DEFS = [
    {
        "name": "Lockhart Ventures",
        "website": "https://lockhartvc.example",
        "stage_focus": "seed-to-series-a",
        "location": "Los Angeles, CA",
        "description": "Early-stage aerospace and defense specialist.",
    },
    {
        "name": "Orbital Capital Partners",
        "website": "https://orbitalcp.example",
        "stage_focus": "series-a-series-b",
        "location": "El Segundo, CA",
        "description": "Space launch, in-orbit services, and related infrastructure.",
    },
    {
        "name": "Blue Pine Defense Fund",
        "website": "https://bluepine.example",
        "stage_focus": "series-b-growth",
        "location": "Arlington, VA",
        "description": "Defense technology growth investor with DoD relationships.",
    },
    {
        "name": "Meridian Growth",
        "website": "https://meridiangrowth.example",
        "stage_focus": "growth",
        "location": "Boston, MA",
        "description": "Dual-use growth-stage fund focused on hard-tech scale-ups.",
    },
    {
        "name": "Ironforge Capital",
        "website": "https://ironforge.example",
        "stage_focus": "series-a-series-b",
        "location": "Pittsburgh, PA",
        "description": "Advanced manufacturing and industrial automation.",
    },
    {
        "name": "Stratos Aerospace Fund",
        "website": "https://stratosaf.example",
        "stage_focus": "series-a-series-b",
        "location": "Seattle, WA",
        "description": "Aviation, propulsion, and airframe-adjacent companies.",
    },
    {
        "name": "North Range Partners",
        "website": "https://northrange.example",
        "stage_focus": "series-b-growth",
        "location": "Austin, TX",
        "description": "Hypersonics, advanced materials, and thermal systems.",
    },
    {
        "name": "Vanguard Deep Tech",
        "website": "https://vanguarddt.example",
        "stage_focus": "seed-to-series-a",
        "location": "San Francisco, CA",
        "description": "Deep-tech generalist with selective defense allocation.",
    },
    {
        "name": "Polaris Strategic",
        "website": "https://polarisstrategic.example",
        "stage_focus": "multi-stage",
        "location": "Washington, DC",
        "description": "Strategic capital with government and prime relationships.",
    },
    {
        "name": "Kestrel Industrial",
        "website": "https://kestrelind.example",
        "stage_focus": "growth",
        "location": "Denver, CO",
        "description": "Industrial-scale manufacturing and supply-chain plays.",
    },
]


def seed_firms(db) -> dict[str, InvestorFirm]:
    firms: dict[str, InvestorFirm] = {}
    for d in FIRM_DEFS:
        firm = InvestorFirm(status="active", **d)
        db.add(firm)
        firms[d["name"]] = firm
    db.flush()
    return firms


# ---------------------------------------------------------------------------
# contacts
# ---------------------------------------------------------------------------

CONTACT_DEFS = [
    ("Lockhart Ventures", "Maya Patel", "Partner", "maya.patel@lockhartvc.example"),
    ("Lockhart Ventures", "Jordan Reyes", "Principal", "jordan.reyes@lockhartvc.example"),
    ("Orbital Capital Partners", "Sam Whitfield", "Managing Director", "sam.whitfield@orbitalcp.example"),
    ("Blue Pine Defense Fund", "Rebecca Holt", "Partner", "rebecca.holt@bluepine.example"),
    ("Meridian Growth", "Daniel Chen", "Principal", "daniel.chen@meridiangrowth.example"),
    ("Ironforge Capital", "Priya Shah", "Vice President", "priya.shah@ironforge.example"),
    ("Stratos Aerospace Fund", "Marcus Bell", "Partner", "marcus.bell@stratosaf.example"),
    ("North Range Partners", "Elena Morris", "Managing Partner", "elena.morris@northrange.example"),
    ("North Range Partners", "Theo Nakamura", "Associate", "theo.nakamura@northrange.example"),
    ("Vanguard Deep Tech", "Olivia Grant", "Partner", "olivia.grant@vanguarddt.example"),
    ("Polaris Strategic", "Victor Alvarez", "Senior Principal", "victor.alvarez@polarisstrategic.example"),
    ("Kestrel Industrial", "Harper Lin", "Partner", "harper.lin@kestrelind.example"),
]


def seed_contacts(
    db, firms: dict[str, InvestorFirm]
) -> dict[tuple[str, str], InvestorContact]:
    contacts: dict[tuple[str, str], InvestorContact] = {}
    for firm_name, name, title, email in CONTACT_DEFS:
        firm = firms[firm_name]
        contact = InvestorContact(
            firm_id=firm.id,
            name=name,
            title=title,
            email=email,
        )
        db.add(contact)
        contacts[(firm_name, name)] = contact
    db.flush()
    return contacts


# ---------------------------------------------------------------------------
# opportunities
# ---------------------------------------------------------------------------

# (firm_name, primary_contact_name, stage, owner, next_step, due_offset_days,
#  fit, probability, strategic_value, amount, summary, label)
OPPORTUNITY_DEFS = [
    (
        "Lockhart Ventures", "Maya Patel", "identified", "brian.cook",
        "Qualify thesis fit on initial call",
        14, 70, 35, 60, Decimal("2500000"),
        "Initial interest from Lockhart after teaser deck.",
        "lockhart",
    ),
    (
        "Orbital Capital Partners", "Sam Whitfield", "qualified", "brian.cook",
        "Send updated data room link",
        5, 85, 55, 85, Decimal("7000000"),
        "Strong thesis alignment on orbital infrastructure.",
        "orbital",
    ),
    (
        "Blue Pine Defense Fund", "Rebecca Holt", "contacted", "brian.cook",
        "Schedule intro call",
        10, 75, 45, 80, Decimal("8000000"),
        "Warm intro via DoD network; waiting to book call.",
        "bluepine",
    ),
    (
        "Meridian Growth", "Daniel Chen", "intro_call", "brian.cook",
        "Send follow-up deck with updated traction",
        -6, 65, 45, 70, Decimal("12000000"),
        "Intro call done; partner wants updated numbers.",
        "meridian",  # OVERDUE #1
    ),
    (
        "Ironforge Capital", "Priya Shah", "diligence", "brian.cook",
        "Submit manufacturing capacity model",
        7, 78, 65, 72, Decimal("9000000"),
        "Active diligence on production scale-up.",
        "ironforge",
    ),
    (
        "Stratos Aerospace Fund", "Marcus Bell", "diligence", "brian.cook",
        "Provide flight-test dataset",
        -11, 72, 50, 68, Decimal("6500000"),
        "Diligence stalled on missing flight data.",
        "stratos",  # OVERDUE #2
    ),
    (
        "North Range Partners", "Elena Morris", "partner_meeting", "brian.cook",
        "Prep partner-meeting materials",
        3, 82, 70, 88, Decimal("15000000"),
        "Late-stage; final partner pitch scheduled.",
        "northrange",
    ),
    (
        "Vanguard Deep Tech", "Olivia Grant", "qualified", "brian.cook",
        "Resume qualification after summer pause",
        20, 60, 25, 55, Decimal("4000000"),
        "Paused conversation; needs re-engagement.",
        "vanguard",  # STALE #1
    ),
    (
        "Polaris Strategic", "Victor Alvarez", "intro_call", "brian.cook",
        "Re-open dialog and confirm continued interest",
        25, 68, 30, 75, Decimal("10000000"),
        "No response for weeks; confirm status.",
        "polaris",  # STALE #2
    ),
    (
        "Kestrel Industrial", "Harper Lin", "deferred", "brian.cook",
        None,
        None, 50, 15, 45, Decimal("5000000"),
        "Deferred to next quarter per partner feedback.",
        "kestrel",
    ),
    (
        "Orbital Capital Partners", "Sam Whitfield", "term_sheet", "brian.cook",
        "Negotiate key economic terms",
        4, 90, 80, 90, Decimal("7000000"),
        "Follow-on opportunity moving to term sheet.",
        "orbital2",
    ),
    (
        "Blue Pine Defense Fund", "Rebecca Holt", "closed_won", "brian.cook",
        None,
        None, 85, 100, 85, Decimal("3000000"),
        "Historical closed-won investment — for reference only.",
        "bluepine2",
    ),
]


def seed_opportunities(
    db,
    firms: dict[str, InvestorFirm],
    contacts: dict[tuple[str, str], InvestorContact],
) -> dict[str, InvestorOpportunity]:
    opps: dict[str, InvestorOpportunity] = {}
    for (
        firm_name, contact_name, stage, owner, next_step, due_offset,
        fit, probability, strategic_value, amount, summary, label,
    ) in OPPORTUNITY_DEFS:
        status = "open"
        if stage == "deferred":
            status = "deferred"
        elif stage == "closed_won":
            status = "closed_won"

        due = _days_ahead(due_offset) if due_offset is not None else None

        opp = InvestorOpportunity(
            firm_id=firms[firm_name].id,
            primary_contact_id=contacts[(firm_name, contact_name)].id,
            stage=stage,
            status=status,
            amount=amount,
            target_close_date=(_now() + timedelta(days=120)).date(),
            summary=summary,
            owner=owner,
            next_step=next_step,
            next_step_due_at=due,
            fit_score=fit,
            probability_score=probability,
            strategic_value_score=strategic_value,
        )
        db.add(opp)
        opps[label] = opp
    db.flush()
    return opps


# ---------------------------------------------------------------------------
# meetings
# ---------------------------------------------------------------------------

def seed_meetings(db, opps: dict[str, InvestorOpportunity]) -> None:
    meetings_spec = [
        (
            "meridian",
            "Intro call — Meridian Growth",
            _days_ago(7),
            "Strong interest. Needs updated traction slide before next step.",
            "Send refreshed deck with Q-over-Q traction.",
        ),
        (
            "northrange",
            "Partner pre-brief — North Range Partners",
            _days_ago(2),
            "Partners aligned on thesis; one open question on thermal margins.",
            "Prep partner-meeting brief with thermal analysis.",
        ),
        (
            "ironforge",
            "Diligence kickoff — Ironforge Capital",
            _days_ago(9),
            "Scope agreed. Capacity model and supplier list requested.",
            "Send capacity model and supplier coverage.",
        ),
        (
            "northrange",
            "Partner meeting — North Range (upcoming)",
            _days_ahead(3),
            None,
            None,
        ),
    ]

    for label, title, starts_at, outcome, next_step in meetings_spec:
        opp = opps[label]
        m = Meeting(
            entity_type=ENTITY_OPPORTUNITY,
            entity_id=opp.id,
            title=title,
            location="Video",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=45),
            raw_notes=outcome,
            outcome=outcome,
            next_step=next_step,
        )
        db.add(m)
    db.flush()


# ---------------------------------------------------------------------------
# communications + approvals
# ---------------------------------------------------------------------------

def seed_communications_and_approvals(
    db, opps: dict[str, InvestorOpportunity]
) -> None:
    # 2 plain drafts (status=draft)
    drafts = [
        (
            "lockhart",
            "Following up — Lockhart Ventures",
            (
                "Hi Maya,\n\nThanks for the initial interest. I'd like to walk through how "
                "Asgard fits your early-stage aerospace thesis. Does next week work for "
                "a 30-minute intro?\n\nBest,\nBrian"
            ),
            "maya.patel@lockhartvc.example",
        ),
        (
            "bluepine",
            "Intro call timing — Blue Pine",
            (
                "Hi Rebecca,\n\nGreat to connect through the DoD network. Sharing a few "
                "time windows for an intro conversation next week.\n\nBest,\nBrian"
            ),
            "rebecca.holt@bluepine.example",
        ),
    ]
    for label, subject, body, to in drafts:
        opp = opps[label]
        c = Communication(
            entity_type=ENTITY_OPPORTUNITY,
            entity_id=opp.id,
            channel="email",
            direction="outbound",
            status="draft",
            subject=subject,
            body=body,
            from_address="brian.cook@asgardaerospace.example",
            to_address=to,
        )
        db.add(c)

    # 1 sent (previously approved) + 1 rejected (reopened as draft)
    historical = [
        (
            "orbital",
            "Refreshed data room — Orbital",
            (
                "Hi Sam,\n\nThe data room is refreshed with the latest financials and "
                "customer pipeline. Let me know if anything is missing.\n\nBest,\nBrian"
            ),
            "sam.whitfield@orbitalcp.example",
            "approved",
        ),
        (
            "meridian",
            "Initial follow-up — Meridian (rejected)",
            (
                "Hi Daniel,\n\nEarly follow-up draft that was pulled before send for a "
                "tone rewrite.\n\nBest,\nBrian"
            ),
            "daniel.chen@meridiangrowth.example",
            "rejected",
        ),
    ]
    for label, subject, body, to, decision in historical:
        opp = opps[label]
        is_approved = decision == "approved"
        run_status = "completed"
        comm = Communication(
            entity_type=ENTITY_OPPORTUNITY,
            entity_id=opp.id,
            channel="email",
            direction="outbound",
            status="sent" if is_approved else "draft",
            subject=subject,
            body=body,
            from_address="brian.cook@asgardaerospace.example",
            to_address=to,
            sent_at=_days_ago(3) if is_approved else None,
        )
        db.add(comm)
        db.flush()
        run = WorkflowRun(
            workflow_key="investor.send_approval",
            entity_type=ENTITY_COMMUNICATION,
            entity_id=comm.id,
            status=run_status,
            triggered_by="brian.cook",
            started_at=_days_ago(4),
            completed_at=_days_ago(3),
            input_payload={"communication_id": comm.id},
            result_payload={"decision": decision},
        )
        db.add(run)
        db.flush()
        db.add(
            Approval(
                entity_type=ENTITY_COMMUNICATION,
                entity_id=comm.id,
                workflow_run_id=run.id,
                action="send_communication",
                status=decision,
                requested_by="brian.cook",
                reviewer="brian.cook",
                reviewed_at=_days_ago(3),
                decision_note=(
                    "Approved and sent." if is_approved
                    else "Rewrite tone; softer opener."
                ),
            )
        )

    # 2 pending-approval drafts (with Approval rows)
    pending = [
        (
            "ironforge",
            "Diligence follow-up — capacity model",
            (
                "Hi Priya,\n\nAttaching the updated capacity model alongside the supplier "
                "coverage sheet we discussed.\n\nBest,\nBrian"
            ),
            "priya.shah@ironforge.example",
        ),
        (
            "northrange",
            "Partner-meeting brief — North Range",
            (
                "Hi Elena,\n\nAhead of the partner meeting, here's the brief covering "
                "thermal analysis, unit economics, and the decision timeline.\n\nBest,\nBrian"
            ),
            "elena.morris@northrange.example",
        ),
    ]
    for label, subject, body, to in pending:
        opp = opps[label]
        run = WorkflowRun(
            workflow_key="investor.send_approval",
            entity_type=ENTITY_COMMUNICATION,
            entity_id=0,  # set after comm.id known
            status="pending",
            triggered_by="brian.cook",
            started_at=_now(),
        )
        c = Communication(
            entity_type=ENTITY_OPPORTUNITY,
            entity_id=opp.id,
            channel="email",
            direction="outbound",
            status="pending_approval",
            subject=subject,
            body=body,
            from_address="brian.cook@asgardaerospace.example",
            to_address=to,
        )
        db.add(c)
        db.add(run)
        db.flush()
        run.entity_id = c.id
        run.input_payload = {"communication_id": c.id}

        approval = Approval(
            entity_type=ENTITY_COMMUNICATION,
            entity_id=c.id,
            workflow_run_id=run.id,
            action="send_communication",
            status="pending",
            requested_by="brian.cook",
        )
        db.add(approval)
    db.flush()


# ---------------------------------------------------------------------------
# tasks
# ---------------------------------------------------------------------------

def seed_tasks(db, opps: dict[str, InvestorOpportunity]) -> None:
    specs = [
        ("ironforge", "Send capacity model to Ironforge", "open", _days_ahead(2), None),
        ("northrange", "Finalize partner-meeting brief", "open", _days_ahead(1), None),
        ("meridian", "Refresh Q-over-Q traction slide", "open", _days_ago(3), None),
        ("stratos", "Collect flight-test dataset", "open", _days_ago(8), None),
        ("orbital", "Refresh data room permissions", "completed", _days_ago(6), _days_ago(5)),
    ]
    for label, title, status, due_at, completed_at in specs:
        opp = opps[label]
        t = Task(
            entity_type=ENTITY_OPPORTUNITY,
            entity_id=opp.id,
            title=title,
            description=None,
            status=status,
            priority="high" if status == "open" and due_at < _now() else "normal",
            assignee="brian.cook",
            due_at=due_at,
            completed_at=completed_at,
        )
        db.add(t)
    db.flush()


# ---------------------------------------------------------------------------
# notes
# ---------------------------------------------------------------------------

def seed_notes(db, opps: dict[str, InvestorOpportunity]) -> None:
    specs = [
        ("orbital", "Partner is strongly aligned on launch-cadence thesis."),
        ("northrange", "Thermal-margin question is the only remaining technical gate."),
        ("meridian", "Follow-up deck should lead with traction, not technology."),
    ]
    for label, body in specs:
        opp = opps[label]
        db.add(
            Note(
                entity_type=ENTITY_OPPORTUNITY,
                entity_id=opp.id,
                author="brian.cook",
                body=body,
            )
        )
    db.flush()


# ---------------------------------------------------------------------------
# activity events
# ---------------------------------------------------------------------------

def _event(
    opp: InvestorOpportunity,
    event_type: str,
    summary: str,
    when: datetime,
    actor: str = "brian.cook",
    source: str = "user",
    details: Optional[dict] = None,
) -> ActivityEvent:
    payload: dict = {"summary": summary}
    if details:
        payload["details"] = details
    return ActivityEvent(
        entity_type=ENTITY_OPPORTUNITY,
        entity_id=opp.id,
        event_type=event_type,
        actor=actor,
        source=source,
        payload=payload,
        created_at=when,
    )


def seed_activity(db, opps: dict[str, InvestorOpportunity]) -> None:
    # recent activity for active, non-stale opps
    recent_active_specs = [
        ("lockhart", "investor_opportunity.created", "Created opportunity — Lockhart Ventures", _days_ago(4)),
        ("lockhart", "investor_opportunity.updated", "Set next step: qualify thesis fit", _days_ago(3)),
        ("orbital", "investor_opportunity.created", "Created opportunity — Orbital Capital Partners", _days_ago(10)),
        ("orbital", "investor_opportunity.updated", "Stage -> qualified", _days_ago(4)),
        ("orbital", "investor_opportunity.updated", "Fit score -> 85", _days_ago(2)),
        ("bluepine", "investor_opportunity.created", "Created opportunity — Blue Pine", _days_ago(8)),
        ("bluepine", "investor_opportunity.follow_up_drafted", "Follow-up draft created for 'Blue Pine Defense Fund'", _days_ago(1)),
        ("meridian", "investor_opportunity.created", "Created opportunity — Meridian Growth", _days_ago(16)),
        ("meridian", "investor_opportunity.updated", "Intro call held; next step defined", _days_ago(7)),
        ("ironforge", "investor_opportunity.created", "Created opportunity — Ironforge Capital", _days_ago(14)),
        ("ironforge", "investor_opportunity.updated", "Stage -> diligence", _days_ago(9)),
        ("ironforge", "investor_opportunity.follow_up_drafted", "Follow-up draft created for 'Ironforge Capital'", _days_ago(1)),
        ("stratos", "investor_opportunity.created", "Created opportunity — Stratos Aerospace", _days_ago(19)),
        ("stratos", "investor_opportunity.updated", "Diligence blocked: missing flight-test data", _days_ago(13)),
        ("northrange", "investor_opportunity.created", "Created opportunity — North Range Partners", _days_ago(18)),
        ("northrange", "investor_opportunity.updated", "Stage -> partner_meeting", _days_ago(5)),
        ("northrange", "investor_opportunity.follow_up_drafted", "Follow-up draft created for 'North Range Partners'", _days_ago(2)),
        ("orbital2", "investor_opportunity.created", "Created follow-on opportunity — Orbital", _days_ago(6)),
        ("orbital2", "investor_opportunity.updated", "Stage -> term_sheet", _days_ago(1)),
    ]

    # stale: only old activity (>21 days)
    stale_specs = [
        ("vanguard", "investor_opportunity.created", "Created opportunity — Vanguard Deep Tech", _days_ago(45)),
        ("vanguard", "investor_opportunity.updated", "Stage -> qualified", _days_ago(30)),
        ("polaris", "investor_opportunity.created", "Created opportunity — Polaris Strategic", _days_ago(55)),
        ("polaris", "investor_opportunity.updated", "Intro call scheduled", _days_ago(35)),
    ]

    # deferred / closed
    other_specs = [
        ("kestrel", "investor_opportunity.created", "Created opportunity — Kestrel Industrial", _days_ago(40)),
        ("kestrel", "investor_opportunity.updated", "Deferred to next quarter", _days_ago(12)),
        ("bluepine2", "investor_opportunity.created", "Historical Blue Pine investment closed won", _days_ago(200)),
    ]

    for specs in (recent_active_specs, stale_specs, other_specs):
        for label, event_type, summary, when in specs:
            db.add(_event(opps[label], event_type, summary, when))
    db.flush()


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------

def run() -> None:
    with SessionLocal() as db:
        print("Wiping Phase 1 tables…")
        wipe(db)

        print("Seeding investor firms…")
        firms = seed_firms(db)

        print("Seeding investor contacts…")
        contacts = seed_contacts(db, firms)

        print("Seeding investor opportunities…")
        opps = seed_opportunities(db, firms, contacts)

        print("Seeding meetings…")
        seed_meetings(db, opps)

        print("Seeding communications + approvals…")
        seed_communications_and_approvals(db, opps)

        print("Seeding tasks…")
        seed_tasks(db, opps)

        print("Seeding notes…")
        seed_notes(db, opps)

        print("Seeding activity events…")
        seed_activity(db, opps)

        db.commit()

    print("\nDone.")
    print(f"  Firms:          {len(FIRM_DEFS)}")
    print(f"  Contacts:       {len(CONTACT_DEFS)}")
    print(f"  Opportunities:  {len(OPPORTUNITY_DEFS)}")
    print(
        "  Scenarios: 2 overdue (meridian, stratos), "
        "2 stale (vanguard, polaris), 2 pending approvals "
        "(ironforge, northrange), 2 drafts (lockhart, bluepine), "
        "3 completed meetings, 5 tasks."
    )


if __name__ == "__main__":
    run()
