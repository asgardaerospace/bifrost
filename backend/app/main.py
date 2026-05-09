import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.middleware import install_middlewares
from app.core.observability import init_observability
from app.services.pubsub import get_redis_url, manager as pubsub_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bind the running event loop to the pubsub manager (so sync callers in
    services/events.py can schedule broadcasts) and optionally attach Redis
    fanout for multi-worker deployments."""
    pubsub_manager.bind_loop(asyncio.get_running_loop())
    redis_url = get_redis_url()
    if redis_url:
        ok = await pubsub_manager.attach_redis(redis_url)
        if not ok:
            logger.warning(
                "REDIS_URL configured but redis fanout did not attach — running in-memory"
            )
    logger.info("bifrost.boot", extra={"event": "startup", "redis": bool(redis_url)})
    try:
        yield
    finally:
        await pubsub_manager.detach_redis()
        logger.info("bifrost.boot", extra={"event": "shutdown"})


def create_app() -> FastAPI:
    init_observability()
    settings = get_settings()

    app = FastAPI(
        title=settings.project_name,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        lifespan=lifespan,
    )

    # Order matters: CORS must be outermost (added last so it wraps the rest).
    install_middlewares(app)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["x-request-id", "x-trace-id"],
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
