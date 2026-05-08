from fastapi import APIRouter

from app.api.routes import (
    auth,
    health,
    investors,
    investor_agent,
    investor_engine,
    investor_engine_writes,
    market,
    programs,
    suppliers,
    executive,
    command_console,
    communications,
    meetings,
    notes,
    tasks,
    workflows,
    approvals,
    documents,
    activity,
    tags,
    graph,
    intel,
    obsidian,
    missions,
    execution,
    events,
    relationships,
    pressure,
    presence,
    ws,
    memory,
    synthesis,
    signals as sprint4_signals,
    executive_brief as sprint4_exec_brief,
    cognition as sprint5_cognition,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(investors.router, prefix="/investors", tags=["investors"])
api_router.include_router(investor_agent.router, prefix="/investor-agent", tags=["investor-agent"])
api_router.include_router(
    investor_engine.router, prefix="/investor-engine", tags=["investor-engine"]
)
api_router.include_router(
    investor_engine_writes.router,
    prefix="/investor-engine",
    tags=["investor-engine-writes"],
)
api_router.include_router(command_console.router, prefix="/command-console", tags=["command-console"])
api_router.include_router(communications.router, prefix="/communications", tags=["communications"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(activity.router, prefix="/activity", tags=["activity"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(market.router, tags=["market"])
api_router.include_router(programs.router, tags=["programs"])
api_router.include_router(suppliers.router, tags=["suppliers"])
api_router.include_router(executive.router, tags=["executive"])
api_router.include_router(graph.router, tags=["graph"])
api_router.include_router(intel.router, tags=["intel"])
api_router.include_router(obsidian.router)

# Sprint 0 — canonical operational core (additive).
api_router.include_router(missions.router, tags=["missions"])
api_router.include_router(execution.router, tags=["execution"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(relationships.router, tags=["relationships"])

# Sprint 2 — realtime + pressure + presence.
api_router.include_router(pressure.router, tags=["pressure"])
api_router.include_router(presence.router, tags=["presence"])
api_router.include_router(ws.router, tags=["ws"])

# Sprint 3 — organizational memory + retrieval + RAG synthesis.
api_router.include_router(memory.router, tags=["memory"])
api_router.include_router(synthesis.router, tags=["synthesis"])

# Sprint 4 — aerospace intelligence + relevance engine + executive brief.
api_router.include_router(sprint4_signals.router, tags=["intelligence-signals"])
api_router.include_router(sprint4_exec_brief.router, tags=["intelligence-brief"])

# Sprint 5 — cognition + recommendations + simulation + drafting.
api_router.include_router(sprint5_cognition.router, tags=["cognition"])
