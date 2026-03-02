"""Warning management and audit logging for budget enforcement."""

from __future__ import annotations

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _row_to_dict(description, row) -> dict | None:
    """Convert a psycopg row tuple to a dict."""
    if row is None:
        return None
    columns = [desc[0] for desc in description]
    return dict(zip(columns, row))


def _rows_to_dicts(description, rows) -> list[dict]:
    """Convert psycopg rows to list of dicts."""
    if not description or not rows:
        return []
    columns = [desc[0] for desc in description]
    return [dict(zip(columns, row)) for row in rows]


def add_warning(
    pool,
    user_id: str,
    reason: str,
    token_usage: int,
    token_limit: int,
    expires_at: datetime,
) -> None:
    """Add a budget warning for a user."""
    sql = """\
INSERT INTO warnings (user_id, reason, token_usage, token_limit, expires_at)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (user_id, reason)
DO UPDATE SET
    token_usage = EXCLUDED.token_usage,
    token_limit = EXCLUDED.token_limit,
    expires_at = EXCLUDED.expires_at,
    enforced_at = NOW(),
    is_active = TRUE
"""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id, reason, token_usage, token_limit, expires_at))
        conn.commit()


def get_active_warnings(pool) -> list[dict]:
    """Get all currently active warnings."""
    sql = "SELECT * FROM warnings WHERE is_active = TRUE"
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return _rows_to_dicts(cur.description, rows)


def get_active_warnings_for_user(pool, user_id: str) -> list[dict]:
    """Get active warnings for a specific user."""
    sql = "SELECT * FROM warnings WHERE is_active = TRUE AND user_id = %s"
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id,))
            rows = cur.fetchall()
            return _rows_to_dicts(cur.description, rows)


def get_expired_warnings(pool) -> list[dict]:
    """Get active warnings that have passed their expiry time."""
    sql = "SELECT * FROM warnings WHERE is_active = TRUE AND expires_at <= NOW()"
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return _rows_to_dicts(cur.description, rows)


def mark_warning_resolved(pool, warning_id: int) -> None:
    """Mark a warning as resolved (inactive)."""
    sql = "UPDATE warnings SET is_active = FALSE, resolved_at = NOW() WHERE id = %s"
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (warning_id,))
        conn.commit()


def log_audit_entry(
    pool,
    action: str,
    user_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Log an action to the audit trail."""
    sql = """\
INSERT INTO audit_log (action, user_id, details)
VALUES (%s, %s, %s)
"""
    details_json = json.dumps(details) if details else None
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (action, user_id, details_json))
        conn.commit()
