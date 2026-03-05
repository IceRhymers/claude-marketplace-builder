"""Query OTEL metrics tables for Claude Code telemetry."""

from __future__ import annotations

import logging

from core.usage import _parse_query_result

logger = logging.getLogger(__name__)


def get_otel_metrics(
    client,
    warehouse_id: str,
    otel_table: str,
    metric_filter: str | None = None,
    days: int = 7,
) -> list[dict]:
    """Get OTEL metrics from the configured table.

    Args:
        client: WorkspaceClient
        warehouse_id: SQL warehouse ID
        otel_table: Fully qualified table name (catalog.schema.table)
        metric_filter: Optional filter on metric name (LIKE pattern)
        days: Number of days to look back
    """
    where_clause = f"WHERE from_unixtime(sum.time_unix_nano / 1000000000) >= CURRENT_DATE - INTERVAL {days} DAY"
    if metric_filter:
        where_clause += f" AND name LIKE '%{metric_filter}%'"

    sql = f"""\
SELECT
  name AS metric_name,
  sum.attributes['user.id'] AS user_id,
  sum.value AS token_count,
  from_unixtime(sum.time_unix_nano / 1000000000) AS event_time
FROM {otel_table}
{where_clause}
  AND sum IS NOT NULL
ORDER BY event_time DESC
"""
    logger.info("Executing OTEL metrics query on warehouse %s", warehouse_id)
    try:
        result = client.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
        )
        rows = _parse_query_result(result, int_columns=["token_count"])
        logger.info("OTEL metrics query returned %d rows", len(rows))
        return rows
    except Exception:
        logger.exception("OTEL query failed")
        return []


def get_otel_user_summary(
    client,
    warehouse_id: str,
    otel_table: str,
    days: int = 7,
) -> list[dict]:
    """Get per-user aggregation of OTEL metrics."""
    sql = f"""\
SELECT
  sum.attributes['user.id'] AS user_id,
  SUM(sum.value) AS total_value,
  COUNT(*) AS metric_count
FROM {otel_table}
WHERE from_unixtime(sum.time_unix_nano / 1000000000) >= CURRENT_DATE - INTERVAL {days} DAY
  AND sum IS NOT NULL
GROUP BY sum.attributes['user.id']
ORDER BY total_value DESC
"""
    logger.info("Executing OTEL user summary query on warehouse %s", warehouse_id)
    try:
        result = client.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql,
        )
        rows = _parse_query_result(result, int_columns=["total_value", "metric_count"])
        logger.info("OTEL user summary query returned %d rows", len(rows))
        return rows
    except Exception:
        logger.exception("OTEL user summary query failed")
        return []
