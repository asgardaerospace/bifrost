import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
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
    try:
        yield
    finally:
        await pubsub_manager.detach_redis()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.project_name,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
