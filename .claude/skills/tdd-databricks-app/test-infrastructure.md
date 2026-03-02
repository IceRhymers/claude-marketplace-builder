# Test Infrastructure

Complete pytest configuration and shared fixtures for Databricks app TDD.

## pyproject.toml Configuration

Add to the app's `pyproject.toml`:

```toml
[project]
name = "usage-limits-app"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Pure unit tests with no external dependencies",
    "integration: Tests that exercise multiple modules together (still mocked at boundaries)",
]
addopts = "-v --tb=short --strict-markers"
pythonpath = ["."]
```

## test-requirements.txt

```
pytest>=8.0
pytest-cov>=5.0
pytest-randomly>=3.15
pytest-mock>=3.14
```

Install alongside app requirements:

```bash
pip install -r requirements.txt -r test-requirements.txt
```

## conftest.py Template

Place at `app/tests/conftest.py`:

```python
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
    """Set all required environment variables for the app."""
    monkeypatch.setenv("PGHOST", "test-host.cloud.databricks.com")
    monkeypatch.setenv("PGDATABASE", "databricks_postgres")
    monkeypatch.setenv("PGUSER", "test-client-id")
    monkeypatch.setenv("LAKEBASE_ENDPOINT", "projects/test/branches/main/endpoints/ep-1")
    monkeypatch.setenv("SQL_WAREHOUSE_ID", "test-warehouse-id")
    monkeypatch.setenv("DATA_SOURCE", "endpoint_usage")
    monkeypatch.setenv("ENFORCEMENT_INTERVAL_MINUTES", "5")
    monkeypatch.setenv("ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("OTEL_TABLE", "")


# ---------------------------------------------------------------------------
# Databricks SDK fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_workspace_client():
    """Mock WorkspaceClient with pre-configured sub-services."""
    client = MagicMock()

    # statement_execution — used for querying system tables
    client.statement_execution.execute_statement.return_value = MagicMock(
        status=MagicMock(state="SUCCEEDED"),
        manifest=MagicMock(
            schema=MagicMock(columns=[
                MagicMock(name="requester"),
                MagicMock(name="total_tokens"),
            ])
        ),
        result=MagicMock(data_array=[]),
    )

    # serving_endpoints — used for permission management
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
        mock_result.manifest.schema.columns = [
            MagicMock(name=col) for col in columns
        ]
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
```

## Running Tests Locally

From the app directory (e.g., `plugins/databricks-skills/skills/usage-limits/app/`):

```bash
# Install test dependencies
pip install -r test-requirements.txt

# Run all tests
python -m pytest tests/ -v

# Run only unit tests (fast feedback)
python -m pytest tests/ -m unit -v

# Run only integration tests
python -m pytest tests/ -m integration -v

# Run tests for a specific module
python -m pytest tests/unit/test_budget.py -v

# Run with coverage
python -m pytest tests/ --cov=core --cov-report=term-missing

# Run with coverage threshold (fails if under 80%)
python -m pytest tests/ --cov=core --cov-fail-under=80
```

Or use the Makefile from the repo root:

```bash
make test-app APP=usage-limits
make test-app-coverage APP=usage-limits
```
