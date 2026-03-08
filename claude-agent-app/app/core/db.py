"""Lakebase connection via SQLAlchemy with OAuth token injection."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from databricks.sdk import WorkspaceClient

from core.config import AppConfig
from core.models import Base

logger = logging.getLogger(__name__)

_w: WorkspaceClient | None = None


def _get_workspace_client() -> WorkspaceClient:
    global _w
    if _w is None:
        _w = WorkspaceClient()
    return _w


def create_engine_from_config(config: AppConfig) -> Engine:
    """Create a SQLAlchemy engine for Lakebase with OAuth token injection."""
    logger.info(
        "Creating engine: host=%s database=%s instance=%s",
        config.pg_host,
        config.pg_database,
        config.lakebase_instance,
    )

    url = (
        f"postgresql+psycopg://{config.pg_host}:5432"
        f"/{config.pg_database}?sslmode=require"
    )

    engine = create_engine(
        url,
        pool_size=1,
        max_overflow=9,
        pool_pre_ping=True,
    )

    instance_name = config.lakebase_instance

    @event.listens_for(engine, "do_connect")
    def _inject_token(dialect, conn_rec, cargs, cparams):
        w = _get_workspace_client()
        credential = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[instance_name],
        )
        cparams["user"] = w.config.client_id
        cparams["password"] = credential.token
        logger.info("Injected Lakebase OAuth token for instance %s", instance_name)

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to *engine*."""
    return sessionmaker(bind=engine)
