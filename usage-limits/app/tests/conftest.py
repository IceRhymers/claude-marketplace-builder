"""Shared fixtures for all Databricks app tests."""

import os
import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Environment fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def env_vars(monkeypatch):
    """Set all required environment variables for the app.

    Note: No DATA_SOURCE — data sources are discovered dynamically at runtime.
    """
    monkeypatch.setenv("PGHOST", "test-host.cloud.databricks.com")
    monkeypatch.setenv("PGDATABASE", "databricks_postgres")
    monkeypatch.setenv("PGUSER", "test-client-id")
    monkeypatch.setenv("LAKEBASE_ENDPOINT", "projects/test/branches/main/endpoints/ep-1")
    monkeypatch.setenv("SQL_WAREHOUSE_ID", "test-warehouse-id")
    monkeypatch.setenv("EVALUATION_INTERVAL_MINUTES", "5")
    monkeypatch.setenv("BUDGET_API_PORT", "8502")
    monkeypatch.setenv("OTEL_TABLE", "")


# ---------------------------------------------------------------------------
# Databricks SDK fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_workspace_client():
    """Mock WorkspaceClient with pre-configured sub-services."""
    client = MagicMock()

    # statement_execution — used for querying system tables
    # Note: MagicMock(name=x) sets repr, not .name attr — assign separately
    col_requester = MagicMock()
    col_requester.name = "requester"
    col_total = MagicMock()
    col_total.name = "total_tokens"
    client.statement_execution.execute_statement.return_value = MagicMock(
        status=MagicMock(state="SUCCEEDED"),
        manifest=MagicMock(
            schema=MagicMock(columns=[col_requester, col_total])
        ),
        result=MagicMock(data_array=[]),
    )

    # serving_endpoints — used for permission management and discovery
    mock_endpoint = MagicMock()
    mock_endpoint.name = "claude-code-endpoint"
    mock_ai_gateway_config = MagicMock()
    mock_ai_gateway_config.inference_table_config.catalog_name = "claude_code"
    mock_ai_gateway_config.inference_table_config.schema_name = "default"
    mock_ai_gateway_config.inference_table_config.table_name_prefix = "claude-code-endpoint"
    mock_ai_gateway_config.inference_table_config.enabled = True
    mock_endpoint.ai_gateway = mock_ai_gateway_config
    mock_endpoint.config = MagicMock()
    mock_endpoint.config.auto_capture_config = None

    client.serving_endpoints.get.return_value = mock_endpoint
    client.serving_endpoints.list.return_value = [mock_endpoint]

    client.serving_endpoints.get_permissions.return_value = MagicMock(
        access_control_list=[]
    )
    client.serving_endpoints.update_permissions.return_value = None

    # postgres — used for Lakebase credential generation
    client.postgres.generate_database_credential.return_value = MagicMock(
        token="mock-oauth-token"
    )

    return client


@pytest.fixture
def make_query_result():
    """Factory fixture to build mock SQL query results.

    Usage:
        result = make_query_result(
            columns=["requester", "total_tokens"],
            rows=[["user@example.com", "1500"], ["admin@example.com", "3000"]],
        )
    """
    def _make(columns: list[str], rows: list[list[str]]):
        mock_result = MagicMock()
        mock_result.status.state = "SUCCEEDED"
        # Note: MagicMock(name=x) sets the mock's repr name, NOT .name attr.
        # We must assign .name separately.
        col_mocks = []
        for col in columns:
            m = MagicMock()
            m.name = col
            col_mocks.append(m)
        mock_result.manifest.schema.columns = col_mocks
        mock_result.result.data_array = rows
        return mock_result
    return _make


# ---------------------------------------------------------------------------
# Lakebase / psycopg fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cursor():
    """Mock psycopg cursor with configurable return values."""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    cursor.rowcount = 0
    cursor.description = None
    return cursor


@pytest.fixture
def mock_db_pool(mock_cursor):
    """Mock Lakebase ConnectionPool with context-manager support."""
    pool = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
    pool.connection.return_value.__exit__ = MagicMock(return_value=False)

    return pool


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_usage_data():
    """Realistic usage data matching system table schema."""
    return [
        {
            "requester": "user1@example.com",
            "input_tokens": 5000,
            "output_tokens": 3000,
            "total_tokens": 8000,
            "request_count": 15,
            "usage_date": "2026-03-01",
        },
        {
            "requester": "user2@example.com",
            "input_tokens": 12000,
            "output_tokens": 8000,
            "total_tokens": 20000,
            "request_count": 42,
            "usage_date": "2026-03-01",
        },
    ]


@pytest.fixture
def sample_budget_config():
    """Budget configuration rows as returned from Lakebase."""
    return [
        {
            "id": 1,
            "entity_type": "user",
            "entity_id": "user1@example.com",
            "daily_token_limit": 50000,
            "weekly_token_limit": 200000,
            "monthly_token_limit": 500000,
            "is_admin": False,
        },
        {
            "id": 2,
            "entity_type": "user",
            "entity_id": "admin@example.com",
            "daily_token_limit": 50000,
            "weekly_token_limit": 200000,
            "monthly_token_limit": 500000,
            "is_admin": True,
        },
    ]


@pytest.fixture
def sample_default_budget():
    """Default budget applied when no per-user config exists."""
    return {
        "daily_token_limit": 100000,
        "weekly_token_limit": 400000,
        "monthly_token_limit": 1000000,
    }
