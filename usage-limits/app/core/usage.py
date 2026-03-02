"""Query system tables for token usage data."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Table mappings for each data source
_TABLE_MAP = {
    "ai_gateway": "system.ai_gateway.usage",
    "endpoint_usage": "system.serving.endpoint_usage",
}

# Column name mappings per source (ai_gateway uses different column names)
_TIME_COL = {
    "ai_gateway": "event_time",
    "endpoint_usage": "request_time",
}

_TOKEN_COLS = {
    "ai_gateway": {
        "input": "input_tokens",
        "output": "output_tokens",
        "total": "total_tokens",
    },
    "endpoint_usage": {
        "input": "input_token_count",
        "output": "output_token_count",
        "total": "input_token_count + output_token_count",
    },
}


def _parse_query_result(result, int_columns: list[str] | None = None) -> list[dict]:
    """Parse SDK statement result into a list of dicts with optional int coercion."""
    if result.status.state != "SUCCEEDED":
        return []

    columns = [col.name for col in result.manifest.schema.columns]
    rows = result.result.data_array
    int_cols = set(int_columns or [])

    parsed = []
    for row in rows:
        record = {}
        for col_name, value in zip(columns, row):
            if col_name in int_cols and value is not None:
                record[col_name] = int(value)
            else:
                record[col_name] = value
        parsed.append(record)

    return parsed


def _execute_usage_query(client, warehouse_id: str, sql: str) -> list[dict]:
    """Execute a SQL query and parse results with int coercion on token columns."""
    try:
        result = client.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
        )
        return _parse_query_result(
            result,
            int_columns=["input_tokens", "output_tokens", "total_tokens", "request_count"],
        )
    except Exception:
        logger.exception("Usage query failed")
        return []


def get_daily_usage(client, warehouse_id: str, source: str) -> list[dict]:
    """Get per-user daily token usage for the current day."""
    table = _TABLE_MAP[source]
    time_col = _TIME_COL[source]
    tok = _TOKEN_COLS[source]

    sql = f"""\
SELECT
  requester,
  DATE({time_col}) AS usage_date,
  SUM({tok['input']}) AS input_tokens,
  SUM({tok['output']}) AS output_tokens,
  SUM({tok['total']}) AS total_tokens,
  COUNT(*) AS request_count
FROM {table}
WHERE {time_col} >= CURRENT_DATE
GROUP BY requester, DATE({time_col})
"""
    return _execute_usage_query(client, warehouse_id, sql)


def get_weekly_usage(client, warehouse_id: str, source: str) -> list[dict]:
    """Get per-user token usage for the current week (from Monday)."""
    table = _TABLE_MAP[source]
    time_col = _TIME_COL[source]
    tok = _TOKEN_COLS[source]

    sql = f"""\
SELECT
  requester,
  SUM({tok['input']}) AS input_tokens,
  SUM({tok['output']}) AS output_tokens,
  SUM({tok['total']}) AS total_tokens,
  COUNT(*) AS request_count
FROM {table}
WHERE {time_col} >= DATE_TRUNC('WEEK', CURRENT_DATE)
GROUP BY requester
"""
    return _execute_usage_query(client, warehouse_id, sql)


def get_monthly_usage(client, warehouse_id: str, source: str) -> list[dict]:
    """Get per-user token usage for the current month."""
    table = _TABLE_MAP[source]
    time_col = _TIME_COL[source]
    tok = _TOKEN_COLS[source]

    sql = f"""\
SELECT
  requester,
  SUM({tok['input']}) AS input_tokens,
  SUM({tok['output']}) AS output_tokens,
  SUM({tok['total']}) AS total_tokens,
  COUNT(*) AS request_count
FROM {table}
WHERE {time_col} >= DATE_TRUNC('MONTH', CURRENT_DATE)
GROUP BY requester
"""
    return _execute_usage_query(client, warehouse_id, sql)


def get_top_users(client, warehouse_id: str, n: int = 10, source: str = "ai_gateway") -> list[dict]:
    """Get top N users by total token usage for the current month."""
    table = _TABLE_MAP[source]
    time_col = _TIME_COL[source]
    tok = _TOKEN_COLS[source]

    sql = f"""\
SELECT
  requester,
  SUM({tok['total']}) AS total_tokens,
  COUNT(*) AS request_count
FROM {table}
WHERE {time_col} >= DATE_TRUNC('MONTH', CURRENT_DATE)
GROUP BY requester
ORDER BY total_tokens DESC
LIMIT {n}
"""
    return _execute_usage_query(client, warehouse_id, sql)


def get_user_usage(
    client, warehouse_id: str, user_email: str, days: int = 30, source: str = "ai_gateway"
) -> list[dict]:
    """Get daily usage history for a specific user over the last N days."""
    table = _TABLE_MAP[source]
    time_col = _TIME_COL[source]
    tok = _TOKEN_COLS[source]

    sql = f"""\
SELECT
  DATE({time_col}) AS usage_date,
  SUM({tok['input']}) AS input_tokens,
  SUM({tok['output']}) AS output_tokens,
  SUM({tok['total']}) AS total_tokens,
  COUNT(*) AS request_count
FROM {table}
WHERE requester = '{user_email}'
  AND {time_col} >= CURRENT_DATE - INTERVAL {days} DAY
GROUP BY DATE({time_col})
ORDER BY usage_date DESC
"""
    return _execute_usage_query(client, warehouse_id, sql)


def get_endpoint_breakdown(
    client, warehouse_id: str, source: str = "ai_gateway"
) -> list[dict]:
    """Get per-endpoint token usage breakdown (AI Gateway only).

    Raises ValueError if source is not ai_gateway.
    """
    if source != "ai_gateway":
        raise ValueError("get_endpoint_breakdown is only available for ai_gateway source")

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
