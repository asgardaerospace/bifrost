from fastapi import APIRouter

from app.api.routes import (
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
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
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
