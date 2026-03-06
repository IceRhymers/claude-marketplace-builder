# Mock Patterns

Complete mocking templates for external dependencies in Databricks APX apps (FastAPI backend + React frontend).

---

## Backend Mock Patterns (Python / pytest)

### 1. Mocking Databricks WorkspaceClient

Always patch where the client is **imported**, not where it is **defined**.

#### Statement Execution (SQL Warehouse Queries)

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

    mock_client.statement_execution.execute_statement.assert_called_once()
    call_kwargs = mock_client.statement_execution.execute_statement.call_args
    assert "system.serving.endpoint_usage" in call_kwargs.kwargs["statement"]
    assert result[0]["requester"] == "user@example.com"
```

#### Serving Endpoint Permissions

```python
from unittest.mock import patch, MagicMock

@patch("core.enforcer.WorkspaceClient")
def test_revoke_user_access(MockClient):
    """Mock SDK permission update for enforcement."""
    mock_client = MockClient.return_value

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

    mock_client.serving_endpoints.update_permissions.assert_called_once()
    call_args = mock_client.serving_endpoints.update_permissions.call_args
    acl = call_args.kwargs["access_control_list"]
    assert acl[0].permission_level == "CAN_VIEW"
```

#### Handling Failed Queries

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

### 2. Mocking SQLAlchemy Session (Lakebase)

The app uses SQLAlchemy ORM via `deps.get_db`, so mock `Session` methods:

```python
from unittest.mock import MagicMock
from core.models import BudgetConfig

@pytest.fixture
def mock_session():
    """Mock SQLAlchemy Session for unit tests."""
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.order_by.return_value.first.return_value = None
    session.get.return_value = None
    return session

def test_save_budget_config(mock_session):
    """Test saving budget via ORM."""
    from core.budget import save_budget_config

    save_budget_config(
        session=mock_session,
        entity_type="user",
        entity_id="user@example.com",
        daily_limit=50.00,
    )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
```

#### Reading Rows via ORM

```python
def test_get_active_warnings(mock_session):
    """Test reading warnings from Lakebase via SQLAlchemy."""
    mock_warning = MagicMock()
    mock_warning.to_dict.return_value = {"id": 1, "user_id": "u@e.com", "reason": "daily_limit"}
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_warning]

    from core.warnings import get_active_warnings
    result = get_active_warnings(mock_session)

    assert len(result) == 1
    assert result[0]["user_id"] == "u@e.com"
```

### 3. Mocking SQL Warehouse Query Results

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

### 4. Mocking APScheduler

```python
from unittest.mock import patch, MagicMock

@patch("core.evaluator.BackgroundScheduler")
def test_starts_evaluation_timer(MockScheduler):
    """Test that evaluation timer is registered correctly."""
    mock_scheduler = MockScheduler.return_value

    from core.evaluator import start_evaluation_timer
    start_evaluation_timer(interval_minutes=5)

    mock_scheduler.add_job.assert_called_once()
    mock_scheduler.start.assert_called_once()
```

### 5. Mocking Environment Variables

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

### 6. Mocking FastAPI Dependencies (TestClient)

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
    mock_session.query.return_value.count.return_value = 5

    response = test_client.get("/api/overview/metrics")
    assert response.status_code == 200
```

---

## Frontend Mock Patterns (TypeScript / Vitest)

### 7. Mocking the API Client

Mock the entire `@/lib/api` module to isolate components from HTTP:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import * as api from "@/lib/api";

vi.mock("@/lib/api");
const mockGetOverviewMetrics = vi.mocked(api.getOverviewMetrics);
const mockGetTopUsers = vi.mocked(api.getTopUsers);

beforeEach(() => {
  vi.clearAllMocks();
});

it("displays overview metrics", async () => {
  mockGetOverviewMetrics.mockResolvedValue({
    cost_today: 42.5,
    requests_today: 150,
    active_users: 8,
  });
  mockGetTopUsers.mockResolvedValue([]);

  render(<OverviewPage />, { wrapper: TestProviders });

  await waitFor(() => {
    expect(screen.getByText("$42.50")).toBeInTheDocument();
  });
});
```

### 8. Mocking TanStack Query (useQuery)

Option A -- Mock the API layer (preferred, tests the real hook wiring):

```tsx
vi.mock("@/lib/api", () => ({
  listBudgets: vi.fn().mockResolvedValue([
    { id: 1, entity_id: "user@example.com", daily_dollar_limit: 50 },
  ]),
}));
```

Option B -- Mock the hook directly (when testing component rendering in isolation):

```tsx
vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual("@tanstack/react-query");
  return {
    ...actual,
    useQuery: vi.fn().mockReturnValue({
      data: [{ id: 1, entity_id: "user@example.com", daily_dollar_limit: 50 }],
      isLoading: false,
      isError: false,
    }),
  };
});
```

### 9. Testing Loading and Error States

```tsx
it("shows skeletons while loading", () => {
  mockGetOverviewMetrics.mockReturnValue(new Promise(() => {})); // never resolves
  mockGetTopUsers.mockReturnValue(new Promise(() => {}));

  render(<OverviewPage />, { wrapper: TestProviders });

  // Skeleton elements should be visible
  expect(document.querySelectorAll("[data-slot='skeleton']").length).toBeGreaterThan(0);
});

it("shows error state on API failure", async () => {
  mockGetOverviewMetrics.mockRejectedValue(new Error("Server error"));
  mockGetTopUsers.mockResolvedValue([]);

  render(<OverviewPage />, { wrapper: TestProviders });

  await waitFor(() => {
    expect(screen.getByText(/error/i)).toBeInTheDocument();
  });
});
```

### 10. Testing User Interactions

```tsx
import userEvent from "@testing-library/user-event";

it("saves budget on form submit", async () => {
  const mockSaveBudget = vi.mocked(api.saveBudget);
  mockSaveBudget.mockResolvedValue({ id: 1, entity_id: "u@e.com", daily_dollar_limit: 50 } as any);

  const user = userEvent.setup();
  render(<BudgetsPage />, { wrapper: TestProviders });

  await user.type(screen.getByLabelText(/email/i), "u@e.com");
  await user.type(screen.getByLabelText(/daily/i), "50");
  await user.click(screen.getByRole("button", { name: /save/i }));

  await waitFor(() => {
    expect(mockSaveBudget).toHaveBeenCalledWith(
      expect.objectContaining({ entity_id: "u@e.com", daily_dollar_limit: 50 })
    );
  });
});
```

### 11. Wrapping Components with Providers

Components using TanStack Query or Router need providers in tests:

```tsx
// __tests__/helpers/render.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";

export function TestProviders({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
```

---

## Anti-Patterns

### Backend

**Do NOT mock `datetime.now()` globally.** Instead, pass time as a parameter:

```python
# BAD
@patch("core.budget.datetime")
def test_period(mock_dt):
    mock_dt.now.return_value = datetime(2026, 3, 15)

# GOOD
def test_period():
    from core.budget import get_period_boundaries
    result = get_period_boundaries("daily", reference_date=datetime(2026, 3, 15))
```

**Do NOT mock internal functions between modules:**

```python
# BAD
@patch("core.evaluator.get_user_budget")
def test_evaluation(mock_budget): ...

# GOOD -- mock at the boundary (DB session), let internal modules interact
def test_evaluation(mock_session, mock_workspace_client):
    mock_session.query.return_value.filter.return_value.first.return_value = MagicMock(daily_dollar_limit=50)
```

### Frontend

**Do NOT mock React component children to test parent:**

```tsx
// BAD
vi.mock("@/components/ui/card", () => ({ Card: ({ children }) => <div>{children}</div> }));

// GOOD -- render the real component tree, assert on visible output
render(<OverviewPage />, { wrapper: TestProviders });
expect(screen.getByText("Cost Today")).toBeInTheDocument();
```

**Do NOT test CSS classes or DOM structure -- test behavior and visible text:**

```tsx
// BAD
expect(container.querySelector(".text-2xl")).toHaveTextContent("$42.50");

// GOOD
expect(screen.getByText("$42.50")).toBeInTheDocument();
```
