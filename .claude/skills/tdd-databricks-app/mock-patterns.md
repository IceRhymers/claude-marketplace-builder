# Mock Patterns

Complete mocking templates for external dependencies in Databricks apps.

## 1. Mocking Databricks WorkspaceClient

Always patch where the client is **imported**, not where it is **defined**.

### Statement Execution (SQL Warehouse Queries)

```python
from unittest.mock import patch, MagicMock

@patch("core.usage.WorkspaceClient")
def test_get_daily_usage(MockClient, make_query_result):
    """Mock SQL warehouse query for usage data."""
    mock_client = MockClient.return_value
    mock_client.statement_execution.execute_statement.return_value = make_query_result(
        columns=["requester", "input_tokens", "output_tokens", "total_tokens"],
        rows=[
            ["user@example.com", "5000", "3000", "8000"],
            ["admin@example.com", "12000", "8000", "20000"],
        ],
    )

    from core.usage import get_daily_usage
    result = get_daily_usage(mock_client, warehouse_id="test-wh")

    # Verify the SQL was called
    mock_client.statement_execution.execute_statement.assert_called_once()
    call_kwargs = mock_client.statement_execution.execute_statement.call_args
    assert "system.serving.endpoint_usage" in call_kwargs.kwargs["statement"]
    assert result[0]["requester"] == "user@example.com"
```

### Serving Endpoint Permissions

```python
from unittest.mock import patch, MagicMock

@patch("core.enforcer.WorkspaceClient")
def test_revoke_user_access(MockClient):
    """Mock SDK permission update for enforcement."""
    mock_client = MockClient.return_value

    # Mock current permissions (for snapshot)
    mock_client.serving_endpoints.get_permissions.return_value = MagicMock(
        access_control_list=[
            MagicMock(
                user_name="user@example.com",
                all_permissions=[MagicMock(permission_level="CAN_QUERY")],
            )
        ]
    )

    from core.enforcer import revoke_user_access
    revoke_user_access(mock_client, endpoint_id="ep-123", user_email="user@example.com")

    # Verify CAN_VIEW was set (downgrade from CAN_QUERY)
    mock_client.serving_endpoints.update_permissions.assert_called_once()
    call_args = mock_client.serving_endpoints.update_permissions.call_args
    acl = call_args.kwargs["access_control_list"]
    assert acl[0].permission_level == "CAN_VIEW"
```

### Handling Failed Queries

```python
def test_handles_failed_query(mock_workspace_client):
    """Test graceful handling of SQL query failure."""
    mock_workspace_client.statement_execution.execute_statement.return_value = MagicMock(
        status=MagicMock(state="FAILED"),
        result=None,
    )

    from core.usage import get_daily_usage
    result = get_daily_usage(mock_workspace_client, warehouse_id="test-wh")
    assert result == []  # or raises UsageQueryError, depending on design
```

## 2. Mocking Lakebase (psycopg ConnectionPool)

### Basic Pattern

```python
from unittest.mock import MagicMock, patch

def test_save_budget_config(mock_db_pool, mock_cursor):
    """Test Lakebase INSERT via mocked pool."""
    from core.budget import save_budget_config

    save_budget_config(
        pool=mock_db_pool,
        entity_type="user",
        entity_id="user@example.com",
        daily_limit=50000,
    )

    # Verify the SQL executed
    mock_cursor.execute.assert_called_once()
    sql = mock_cursor.execute.call_args[0][0]
    assert "INSERT INTO budget_configs" in sql or "UPSERT" in sql.upper()
```

### Reading Rows

```python
def test_get_active_blacklist(mock_db_pool, mock_cursor):
    """Test reading blacklist entries from Lakebase."""
    mock_cursor.fetchall.return_value = [
        ("user@example.com", "ep-123", "daily_limit", True),
    ]
    mock_cursor.description = [
        MagicMock(name="user_id"),
        MagicMock(name="endpoint_id"),
        MagicMock(name="reason"),
        MagicMock(name="is_active"),
    ]

    from core.enforcer import get_active_blacklist
    entries = get_active_blacklist(pool=mock_db_pool)

    assert len(entries) == 1
    assert entries[0]["user_id"] == "user@example.com"
```

### Transaction Pattern

```python
def test_enforcement_uses_transaction(mock_db_pool, mock_cursor):
    """Verify enforcement actions happen in a transaction."""
    mock_conn = mock_db_pool.connection.return_value.__enter__.return_value

    from core.enforcer import run_enforcement_cycle
    run_enforcement_cycle(pool=mock_db_pool, client=MagicMock())

    # Verify commit was called (transaction completed)
    mock_conn.commit.assert_called()
```

## 3. Mocking SQL Warehouse Query Results

Use the `make_query_result` factory fixture from conftest.py:

```python
def test_top_users(mock_workspace_client, make_query_result):
    """Test top-N user aggregation."""
    mock_workspace_client.statement_execution.execute_statement.return_value = make_query_result(
        columns=["requester", "total_tokens", "request_count"],
        rows=[
            ["heavy@example.com", "500000", "200"],
            ["medium@example.com", "100000", "50"],
            ["light@example.com", "10000", "5"],
        ],
    )

    from core.usage import get_top_users
    result = get_top_users(mock_workspace_client, n=2, warehouse_id="test-wh")

    assert len(result) == 2
    assert result[0]["requester"] == "heavy@example.com"
```

## 4. Mocking APScheduler

```python
from unittest.mock import patch, MagicMock

@patch("core.enforcer.BackgroundScheduler")
def test_starts_enforcement_timer(MockScheduler):
    """Test that enforcement timer is registered correctly."""
    mock_scheduler = MockScheduler.return_value

    from core.enforcer import start_enforcement_timer
    start_enforcement_timer(interval_minutes=5)

    mock_scheduler.add_job.assert_called_once()
    call_kwargs = mock_scheduler.add_job.call_args
    assert call_kwargs.kwargs.get("minutes") == 5 or call_kwargs.args[0].__name__ == "run_enforcement_cycle"
    mock_scheduler.start.assert_called_once()
```

## 5. Mocking Environment Variables

Use `monkeypatch` (preferred) or the `env_vars` fixture from conftest.py:

```python
def test_config_loads_from_env(monkeypatch):
    """Test config reads from environment."""
    monkeypatch.setenv("SQL_WAREHOUSE_ID", "my-warehouse")
    monkeypatch.setenv("DATA_SOURCE", "ai_gateway")

    from core.config import AppConfig
    config = AppConfig.from_env()

    assert config.sql_warehouse_id == "my-warehouse"
    assert config.data_source == "ai_gateway"
```

## 6. Mocking FastAPI Dependencies

Use `app.dependency_overrides` to inject mocks into route handlers via `Depends()`:

```python
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from main import app
from deps import get_db, get_config, get_client

@pytest.fixture
def test_client(mock_session):
    """Create a TestClient with mocked dependencies."""
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_config] = lambda: MagicMock(
        sql_warehouse_id="test-wh", otel_table=None
    )
    app.dependency_overrides[get_client] = lambda: MagicMock()
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_get_overview_metrics(test_client, mock_session):
    """Test overview metrics endpoint with mocked session."""
    # Configure mock_session to return expected data
    mock_session.query.return_value.count.return_value = 5

    response = test_client.get("/api/overview/metrics")
    assert response.status_code == 200
```

### Mocking SQLAlchemy Session (not raw psycopg)

The app uses SQLAlchemy ORM, so mock `Session` methods:

```python
from unittest.mock import MagicMock
from core.models import BudgetConfig

@pytest.fixture
def mock_session():
    """Mock SQLAlchemy Session for unit tests."""
    session = MagicMock()
    # Chain query().filter().all() etc.
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.first.return_value = None
    session.get.return_value = None
    return session

def test_get_active_warnings(mock_session):
    from core.warnings import get_active_warnings
    mock_warning = MagicMock()
    mock_warning.to_dict.return_value = {"id": 1, "user_id": "u@e.com", "reason": "daily_limit"}
    session.query.return_value.filter.return_value.all.return_value = [mock_warning]
    result = get_active_warnings(mock_session)
    assert len(result) == 1
```

## Anti-Patterns

**Do NOT mock `datetime.now()` globally.** Instead, pass time as a parameter:

```python
# BAD
@patch("core.budget.datetime")
def test_period(mock_dt):
    mock_dt.now.return_value = datetime(2026, 3, 15)
    ...

# GOOD
def test_period():
    from core.budget import get_period_boundaries
    result = get_period_boundaries("daily", reference_date=datetime(2026, 3, 15))
    ...
```

**Do NOT mock internal functions between modules.** Test through the public interface:

```python
# BAD — mocking an internal function
@patch("core.enforcer.get_user_budget")
def test_enforcement(mock_budget):
    ...

# GOOD — mock at the boundary (DB pool), let internal modules interact
def test_enforcement(mock_db_pool, mock_workspace_client, mock_cursor):
    mock_cursor.fetchone.return_value = (50000, 200000, 500000, False)  # budget row
    ...
```

**Do NOT use `@patch.object` on the class under test:**

```python
# BAD
@patch.object(BudgetEvaluator, "_calculate_period")
def test_evaluate(mock_calc):
    ...

# GOOD — test the full function, mock only external calls
def test_evaluate():
    from core.budget import evaluate_budget
    result = evaluate_budget(usage=60000, daily_limit=50000)
    assert result.daily_exceeded is True
```
