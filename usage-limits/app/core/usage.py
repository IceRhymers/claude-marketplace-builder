"""Query system tables for usage data and manage usage snapshots."""

from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.models import UsageSnapshot
from core.pricing import build_usage_cost_query

logger = logging.getLogger(__name__)


def _parse_query_result(
    result,
    int_columns: list[str] | None = None,
    float_columns: list[str] | None = None,
) -> list[dict]:
    """Parse SDK statement result into a list of dicts with optional type coercion."""
    state = result.status.state
    if not (state == "SUCCEEDED" or (hasattr(state, "value") and state.value == "SUCCEEDED")):
        return []

    columns = [col.name for col in result.manifest.schema.columns]
    rows = result.result.data_array
    int_cols = set(int_columns or [])
    float_cols = set(float_columns or [])

    parsed = []
    for row in rows:
        record = {}
        for col_name, value in zip(columns, row):
            if col_name in int_cols and value is not None:
                record[col_name] = int(value)
            elif col_name in float_cols and value is not None:
                record[col_name] = float(value)
            else:
                record[col_name] = value
        parsed.append(record)

    return parsed


def _execute_usage_query(client, warehouse_id: str, sql: str) -> list[dict]:
    """Execute a SQL query and parse results with type coercion."""
    logger.info("Executing usage query on warehouse %s", warehouse_id)
    try:
        result = client.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
        )
        rows = _parse_query_result(
            result,
            int_columns=["total_tokens_1d", "total_tokens_7d", "total_tokens_30d",
                         "request_count_1d", "request_count_7d", "request_count_30d",
                         "total_tokens", "request_count"],
            float_columns=["dollar_cost_1d", "dollar_cost_7d", "dollar_cost_30d"],
        )
        logger.info("Usage query returned %d rows", len(rows))
        return rows
    except Exception:
        logger.exception("Usage query failed")
        return []


def get_distinct_users(client, warehouse_id: str) -> list[str]:
    """Get distinct user emails from AI Gateway usage in the last 30 days."""
    sql = """\
SELECT DISTINCT requester
FROM system.ai_gateway.usage
WHERE requester IS NOT NULL
  AND event_time >= CURRENT_DATE - INTERVAL 30 DAY
ORDER BY requester
"""
    rows = _execute_usage_query(client, warehouse_id, sql)
    return [row["requester"] for row in rows if row.get("requester")]


def get_dollar_usage(client, warehouse_id: str) -> list[dict]:
    """Get per-user dollar costs over 1d/7d/30d windows using pricing SQL."""
    sql = build_usage_cost_query()
    return _execute_usage_query(client, warehouse_id, sql)


def upsert_usage_snapshots(session: Session, rows: list[dict]) -> None:
    """Upsert usage snapshot rows into the usage_snapshots table."""
    for row in rows:
        stmt = pg_insert(UsageSnapshot).values(
            user_id=row["requester"],
            dollar_cost_1d=row.get("dollar_cost_1d"),
            dollar_cost_7d=row.get("dollar_cost_7d"),
            dollar_cost_30d=row.get("dollar_cost_30d"),
            total_tokens_1d=row.get("total_tokens_1d"),
            total_tokens_7d=row.get("total_tokens_7d"),
            total_tokens_30d=row.get("total_tokens_30d"),
            request_count_1d=row.get("request_count_1d"),
            request_count_7d=row.get("request_count_7d"),
            request_count_30d=row.get("request_count_30d"),
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "dollar_cost_1d": stmt.excluded.dollar_cost_1d,
                "dollar_cost_7d": stmt.excluded.dollar_cost_7d,
                "dollar_cost_30d": stmt.excluded.dollar_cost_30d,
                "total_tokens_1d": stmt.excluded.total_tokens_1d,
                "total_tokens_7d": stmt.excluded.total_tokens_7d,
                "total_tokens_30d": stmt.excluded.total_tokens_30d,
                "request_count_1d": stmt.excluded.request_count_1d,
                "request_count_7d": stmt.excluded.request_count_7d,
                "request_count_30d": stmt.excluded.request_count_30d,
                "updated_at": func.now(),
            },
        )
        session.execute(stmt)
    session.commit()
    logger.info("Upserted %d usage snapshots", len(rows))


def get_usage_snapshot(session: Session, user_id: str) -> dict | None:
    """Get the cached usage snapshot for a user, or None if not found."""
    row = session.query(UsageSnapshot).filter(UsageSnapshot.user_id == user_id).first()
    if row is None:
        return None
    return row.to_dict()


def get_top_users(client, warehouse_id: str, n: int = 10) -> list[dict]:
    """Get top N users by total token usage for the current month."""
    sql = f"""\
SELECT
  requester,
  SUM(total_tokens) AS total_tokens,
  COUNT(*) AS request_count
FROM system.ai_gateway.usage
WHERE event_time >= DATE_TRUNC('MONTH', CURRENT_DATE)
GROUP BY requester
ORDER BY total_tokens DESC
LIMIT {n}
"""
    return _execute_usage_query(client, warehouse_id, sql)


def get_user_usage(client, warehouse_id: str, user_email: str, days: int = 30) -> list[dict]:
    """Get daily usage history for a specific user over the last N days."""
    sql = f"""\
SELECT
  DATE(event_time) AS usage_date,
  SUM(input_tokens) AS input_tokens,
  SUM(output_tokens) AS output_tokens,
  SUM(total_tokens) AS total_tokens,
  COUNT(*) AS request_count
FROM system.ai_gateway.usage
WHERE requester = '{user_email}'
  AND event_time >= CURRENT_DATE - INTERVAL {days} DAY
GROUP BY DATE(event_time)
ORDER BY usage_date DESC
"""
    return _execute_usage_query(client, warehouse_id, sql)


def get_endpoint_breakdown(client, warehouse_id: str) -> list[dict]:
    """Get per-endpoint token usage breakdown."""
    sql = """\
SELECT
  endpoint_name,
  SUM(total_tokens) AS total_tokens,
  COUNT(*) AS request_count
FROM system.ai_gateway.usage
WHERE event_time >= DATE_TRUNC('MONTH', CURRENT_DATE)
GROUP BY endpoint_name
ORDER BY total_tokens DESC
"""
    return _execute_usage_query(client, warehouse_id, sql)
