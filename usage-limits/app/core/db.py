"""Lakebase connection via SQLAlchemy with OAuth token injection."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from databricks.sdk import WorkspaceClient

from core.config import AppConfig
from core.models import Base

logger = logging.getLogger(__name__)

_w = WorkspaceClient()


def create_engine_from_config(config: AppConfig) -> Engine:
    """Create a SQLAlchemy engine for Lakebase with OAuth token injection.

    Uses the ``postgresql+psycopg://`` dialect so psycopg 3 is the underlying
    driver.  An event listener on ``do_connect`` generates a fresh Lakebase
    OAuth token for every new physical connection.
    """
    logger.info("Creating engine: host=%s database=%s instance=%s",
                config.pg_host, config.pg_database, config.lakebase_instance)

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
        credential = _w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[instance_name],
        )
        cparams["user"] = _w.config.client_id
        cparams["password"] = credential.token
        logger.info("Injected Lakebase OAuth token for instance %s", instance_name)

    return engine


def _migrate_to_dollar_schema(engine: Engine) -> None:
    """Drop tables that still use the old token-based column names.

    Idempotent: no-op if old columns are already gone.
    """
    insp = inspect(engine)
    old_token_columns = {"daily_token_limit", "weekly_token_limit", "monthly_token_limit",
                         "token_usage", "token_limit"}

    for table_name in ("budget_configs", "default_budgets", "warnings"):
        if not insp.has_table(table_name):
            continue
        columns = {c["name"] for c in insp.get_columns(table_name)}
        if columns & old_token_columns:
            logger.info("Migrating table %s: dropping old token-based schema", table_name)
            Base.metadata.tables[table_name].drop(engine)


def _add_is_custom_column(engine: Engine) -> None:
    """Add is_custom column to budget_configs if it doesn't exist."""
    insp = inspect(engine)
    if not insp.has_table("budget_configs"):
        return
    columns = {c["name"] for c in insp.get_columns("budget_configs")}
    if "is_custom" not in columns:
        logger.info("Adding is_custom column to budget_configs")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE budget_configs ADD COLUMN is_custom BOOLEAN DEFAULT FALSE"))


def _drop_is_admin_column(engine: Engine) -> None:
    """Migrate is_admin=True rows to null limits, then drop the column."""
    insp = inspect(engine)
    if not insp.has_table("budget_configs"):
        return
    columns = {c["name"] for c in insp.get_columns("budget_configs")}
    if "is_admin" not in columns:
        return
    logger.info("Migrating is_admin column: converting admin rows to null limits")
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE budget_configs "
            "SET daily_dollar_limit=NULL, weekly_dollar_limit=NULL, monthly_dollar_limit=NULL, is_custom=TRUE "
            "WHERE is_admin=TRUE"
        ))
        conn.execute(text("ALTER TABLE budget_configs DROP COLUMN is_admin"))


def init_schema(engine: Engine) -> None:
    """Create all application tables (idempotent), migrating old schema if needed."""
    logger.info("Initializing database schema")
    _migrate_to_dollar_schema(engine)
    _add_is_custom_column(engine)
    _drop_is_admin_column(engine)
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to *engine*."""
    return sessionmaker(bind=engine)
