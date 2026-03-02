"""Lakebase connection pool and schema initialization."""

from __future__ import annotations

import os
import psycopg
from psycopg_pool import ConnectionPool
from databricks.sdk import WorkspaceClient

from core.config import AppConfig

_w = WorkspaceClient()


class OAuthConnection(psycopg.Connection):
    """psycopg Connection subclass that generates Lakebase OAuth tokens."""

    @classmethod
    def connect(cls, conninfo="", **kwargs):
        endpoint_name = os.environ["LAKEBASE_ENDPOINT"]
        credential = _w.postgres.generate_database_credential(endpoint=endpoint_name)
        kwargs["password"] = credential.token
        return super().connect(conninfo, **kwargs)


def create_pool(config: AppConfig) -> ConnectionPool:
    """Create a Lakebase connection pool from app config."""
    return ConnectionPool(
        conninfo=config.conninfo,
        connection_class=OAuthConnection,
        min_size=1,
        max_size=10,
        open=True,
    )


_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS budget_configs (
    id SERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('user', 'group')),
    entity_id TEXT NOT NULL,
    daily_token_limit BIGINT,
    weekly_token_limit BIGINT,
    monthly_token_limit BIGINT,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT,
    UNIQUE(entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS default_budgets (
    id SERIAL PRIMARY KEY,
    daily_token_limit BIGINT,
    weekly_token_limit BIGINT,
    monthly_token_limit BIGINT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS warnings (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    token_usage BIGINT,
    token_limit BIGINT,
    enforced_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, reason)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    action TEXT NOT NULL,
    user_id TEXT,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""


def init_schema(pool: ConnectionPool) -> None:
    """Create all application tables (idempotent)."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)
        conn.commit()
