"""Single FastAPI application for the usage-limits app."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from api import budget_router
from core.config import AppConfig
from core.db import create_engine_from_config, init_schema, make_session_factory
from core.evaluator import run_evaluation_cycle, run_user_sync_cycle
from routers.overview import router as overview_router
from routers.users import router as users_router
from routers.budgets import router as budgets_router
from routers.warnings import router as warnings_router
from routers.audit import router as audit_router
from routers.me import router as me_router
from routers.my_usage import router as my_usage_router

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
    logger.info("Starting usage-limits app")

    config = AppConfig.from_env()
    client = WorkspaceClient()
    engine = create_engine_from_config(config)
    init_schema(engine)
    session_factory = make_session_factory(engine)
    app.state.config = config
    app.state.client = client
    app.state.session_factory = session_factory

    def _run_cycle():
        session = session_factory()
        try:
            run_evaluation_cycle(client, session, config.sql_warehouse_id)
        finally:
            session.close()

    def _run_sync():
        session = session_factory()
        try:
            run_user_sync_cycle(client, session, config.sql_warehouse_id)
        finally:
            session.close()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_cycle,
        "interval",
        minutes=config.evaluation_interval_minutes,
        id="budget_evaluator",
    )
    scheduler.add_job(
        _run_sync,
        "interval",
        minutes=config.user_sync_interval_minutes,
        id="user_sync",
    )
    scheduler.start()
    logger.info("Budget evaluator started: every %dm", config.evaluation_interval_minutes)
    logger.info("User sync started: every %dm", config.user_sync_interval_minutes)

    yield

    scheduler.shutdown(wait=False)
    logger.info("Usage-limits app shutdown")


app = FastAPI(title="Usage Limits", lifespan=lifespan)

app.include_router(overview_router)
app.include_router(users_router)
app.include_router(budgets_router)
app.include_router(warnings_router)
app.include_router(audit_router)
app.include_router(me_router)
app.include_router(my_usage_router)
app.include_router(budget_router)

# Serve React frontend static build if available
frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"
if frontend_dist.is_dir():
    logger.info("Mounting frontend from %s", frontend_dist)
    app.mount("/", SPAStaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    logger.warning("Frontend dist not found at %s", frontend_dist)
