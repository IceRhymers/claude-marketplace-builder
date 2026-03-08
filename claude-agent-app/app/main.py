"""FastAPI application for the claude-agent-app."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

import core.skills as skills_module
from core.agent_pool import AgentPool, get_pool
from core.cleanup import purge_stale_conversations
from core.config import AppConfig
from core.db import create_engine_from_config, make_session_factory
from core.skills import get_current_config, load_config_from_volume, reload_if_changed
from routers.conversations import router as conversations_router
from routers.me import router as me_router
from routers.stream import router as stream_router
from routers.marketplace import router as marketplace_router
from routers.preferences import router as preferences_router

logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """Serve index.html for any path not found as a static file (SPA catch-all)."""

    async def get_response(self, path: str, scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404:
            response = await super().get_response("index.html", scope)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting claude-agent-app")

    config = AppConfig.from_env()

    # Initialize database
    try:
        engine = create_engine_from_config(config)
        session_factory = make_session_factory(engine)
        app.state.session_factory = session_factory
        logger.info("Database engine created")
    except Exception as exc:
        logger.warning("Database initialization failed (non-fatal in dev): %s", exc)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from core.models import Base
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        app.state.session_factory = sessionmaker(bind=engine)

    # Load initial skills config
    if config.skills_volume_path:
        try:
            initial_config = load_config_from_volume(config.skills_volume_path)
            with skills_module._config_lock:
                skills_module.current_config = initial_config
            loaded = get_current_config()
            logger.info(
                "Loaded skills config version=%s skills=%d",
                loaded.version,
                len(loaded.skills),
            )
        except Exception as exc:
            logger.warning("Failed to load skills config: %s", exc)
    else:
        logger.warning("SKILLS_VOLUME_PATH not set — starting with empty skills config")

    # Create agent pool
    pool = get_pool()
    app.state.agent_pool = pool

    # Start background scheduler
    scheduler = BackgroundScheduler()

    if config.skills_volume_path:
        def _reload_skills():
            try:
                reload_if_changed(config.skills_volume_path)
            except Exception as exc:
                logger.error("Skills reload error: %s", exc)

        scheduler.add_job(
            _reload_skills,
            "interval",
            seconds=config.skills_reload_interval_seconds,
            id="skills_reload",
        )

    def _evict_stale():
        pool.evict_stale(ttl_minutes=config.agent_ttl_minutes)

    scheduler.add_job(
        _evict_stale,
        "interval",
        minutes=max(1, config.agent_ttl_minutes // 2),
        id="agent_eviction",
    )

    # Set up WorkspaceClient on pool for Volume operations
    try:
        from databricks.sdk import WorkspaceClient
        ws_client = WorkspaceClient()
        pool.set_workspace_client(ws_client)
        logger.info("WorkspaceClient configured on AgentPool")
    except Exception as exc:
        logger.warning("WorkspaceClient setup failed (non-fatal in dev): %s", exc)
        ws_client = None

    # Register TTL cleanup job
    if ws_client is not None:
        def _ttl_cleanup():
            try:
                purge_stale_conversations(
                    session_factory=session_factory,
                    pool=pool,
                    workspace_client=ws_client,
                    ttl_days=config.conversation_ttl_days,
                    volume_base=config.agent_sessions_volume_path,
                )
            except Exception as exc:
                logger.error("TTL cleanup job error: %s", exc)

        from datetime import datetime as _dt
        scheduler.add_job(
            _ttl_cleanup,
            "interval",
            hours=config.conversation_ttl_check_hours,
            id="conversation_ttl_cleanup",
            next_run_time=_dt.now(),
        )

    scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    await pool.shutdown()
    logger.info("claude-agent-app shutdown complete")


app = FastAPI(title="Claude Agent App", lifespan=lifespan)

app.include_router(me_router)
app.include_router(conversations_router)
app.include_router(stream_router)
app.include_router(marketplace_router)
app.include_router(preferences_router)

# Serve React frontend static build if available
frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"
if frontend_dist.is_dir():
    logger.info("Mounting frontend from %s", frontend_dist)
    app.mount("/", SPAStaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    logger.warning("Frontend dist not found at %s", frontend_dist)
