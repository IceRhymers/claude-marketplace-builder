"""Pre-flight access validation for app data sources."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_TABLE_MAP = {
    "ai_gateway": "system.ai_gateway.usage",
    "endpoint_usage": "system.serving.endpoint_usage",
}


def validate_system_table_access(client, warehouse_id: str, source: str) -> bool:
    """Check if the app can query the specified system table."""
    table = _TABLE_MAP.get(source)
    if not table:
        return False

    try:
        result = client.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=f"SELECT 1 FROM {table} LIMIT 1",
        )
        ok = result.status.state == "SUCCEEDED"
        logger.info("System table access validation for %s: %s", source, "passed" if ok else "failed")
        return ok
    except Exception:
        logger.exception("System table access validation failed for %s", source)
        return False


def validate_lakebase_access(session) -> bool:
    """Check if the app can connect to Lakebase."""
    try:
        from sqlalchemy import text
        session.execute(text("SELECT 1"))
        logger.info("Lakebase access validation: passed")
        return True
    except Exception:
        logger.exception("Lakebase access validation failed")
        return False
