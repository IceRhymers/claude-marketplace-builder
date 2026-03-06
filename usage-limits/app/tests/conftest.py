"""Shared fixtures for all Databricks app tests."""

import os
import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager
from datetime import datetime, timezone

from core.auth import UserIdentity


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
    monkeypatch.setenv("LAKEBASE_INSTANCE", "usage-limits")
    monkeypatch.setenv("SQL_WAREHOUSE_ID", "test-warehouse-id")
    monkeypatch.setenv("EVALUATION_INTERVAL_MINUTES", "5")
    monkeypatch.setenv("USER_SYNC_INTERVAL_MINUTES", "5")



# ---------------------------------------------------------------------------
# Databricks SDK fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_workspace_client():
    """Mock WorkspaceClient with pre-configured sub-services."""
    client = MagicMock()

    # statement_execution — used for querying system tables
    col_requester = MagicMock()
    col_requester.name = "requester"
    col_dollar = MagicMock()
    col_dollar.name = "dollar_cost_1d"
    client.statement_execution.execute_statement.return_value = MagicMock(
        status=MagicMock(state="SUCCEEDED"),
        manifest=MagicMock(
            schema=MagicMock(columns=[col_requester, col_dollar])
        ),
        result=MagicMock(data_array=[]),
    )

    # serving_endpoints — used for permission management
    client.serving_endpoints.get_permissions.return_value = MagicMock(
        access_control_list=[]
    )
    client.serving_endpoints.update_permissions.return_value = None

    # database — used for Lakebase Provisioned credential generation
    client.database.generate_database_credential.return_value = MagicMock(
        token="mock-oauth-token"
    )

    return client


@pytest.fixture
def make_query_result():
    """Factory fixture to build mock SQL query results.

    Usage:
        result = make_query_result(
            columns=["requester", "dollar_cost_1d"],
            rows=[["user@example.com", "12.50"], ["admin@example.com", "30.00"]],
        )
    """
    def _make(columns: list[str], rows: list[list[str]]):
        mock_result = MagicMock()
        mock_result.status.state = "SUCCEEDED"
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
# SQLAlchemy session fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    """Mock SQLAlchemy Session for unit tests."""
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.order_by.return_value.first.return_value = None
    session.get.return_value = None
    return session


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_usage_data():
    """Realistic usage data matching dollar-based schema."""
    return [
        {
            "requester": "user1@example.com",
            "dollar_cost_1d": 12.50,
            "dollar_cost_7d": 45.00,
            "dollar_cost_30d": 120.00,
            "total_tokens_1d": 5000,
            "total_tokens_7d": 18000,
            "total_tokens_30d": 48000,
            "request_count_1d": 15,
            "request_count_7d": 60,
            "request_count_30d": 180,
        },
        {
            "requester": "user2@example.com",
            "dollar_cost_1d": 30.00,
            "dollar_cost_7d": 85.00,
            "dollar_cost_30d": 250.00,
            "total_tokens_1d": 12000,
            "total_tokens_7d": 34000,
            "total_tokens_30d": 100000,
            "request_count_1d": 42,
            "request_count_7d": 120,
            "request_count_30d": 350,
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
            "daily_dollar_limit": 50.00,
            "weekly_dollar_limit": 100.00,
            "monthly_dollar_limit": 300.00,
        },
        {
            "id": 2,
            "entity_type": "user",
            "entity_id": "unlimited@example.com",
            "daily_dollar_limit": None,
            "weekly_dollar_limit": None,
            "monthly_dollar_limit": None,
        },
    ]


@pytest.fixture
def sample_default_budget():
    """Default budget applied when no per-user config exists."""
    return {
        "daily_dollar_limit": 50.00,
        "weekly_dollar_limit": 100.00,
        "monthly_dollar_limit": 300.00,
    }


# ---------------------------------------------------------------------------
# Auth identity fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_identity():
    """An admin UserIdentity for router tests."""
    return UserIdentity(
        email="admin@example.com",
        display_name="Admin User",
        groups=["admins", "users"],
        is_admin=True,
    )


@pytest.fixture
def non_admin_identity():
    """A non-admin UserIdentity for router tests."""
    return UserIdentity(
        email="user@example.com",
        display_name="Regular User",
        groups=["users"],
        is_admin=False,
    )
