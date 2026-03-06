# Test Infrastructure

Complete test configuration and shared fixtures for Databricks APX apps (FastAPI backend + React frontend).

---

## Backend (Python / pytest / uv)

### pyproject.toml Configuration

The app's `pyproject.toml` (already configured):

```toml
[project]
name = "usage-limits-app"
version = "0.2.0"
requires-python = ">=3.11"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-randomly>=3.15",
    "pytest-mock>=3.14",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Pure unit tests with no external dependencies",
    "integration: Tests that exercise multiple modules together (still mocked at boundaries)",
]
addopts = "-v --tb=short --strict-markers"
pythonpath = ["."]
```

### Installing Backend Test Dependencies

```bash
cd usage-limits/app && uv sync --group dev
```

### conftest.py Template

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
    monkeypatch.setenv("EVALUATION_INTERVAL_MINUTES", "5")
    monkeypatch.setenv("ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("OTEL_TABLE", "")


# ---------------------------------------------------------------------------
# Databricks SDK fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_workspace_client():
    """Mock WorkspaceClient with pre-configured sub-services."""
    client = MagicMock()

    # statement_execution -- used for querying system tables
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

    # serving_endpoints -- used for permission management
    client.serving_endpoints.get_permissions.return_value = MagicMock(
        access_control_list=[]
    )
    client.serving_endpoints.update_permissions.return_value = None

    # postgres -- used for Lakebase credential generation
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
# SQLAlchemy / Lakebase fixtures
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


@pytest.fixture
def test_client(mock_session, mock_workspace_client):
    """FastAPI TestClient with mocked dependencies."""
    from fastapi.testclient import TestClient
    from main import app
    from deps import get_db, get_config, get_client

    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_config] = lambda: MagicMock(
        sql_warehouse_id="test-wh", otel_table=None,
    )
    app.dependency_overrides[get_client] = lambda: mock_workspace_client
    yield TestClient(app)
    app.dependency_overrides.clear()


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
            "daily_dollar_limit": 50.00,
            "weekly_dollar_limit": 100.00,
            "monthly_dollar_limit": 300.00,
            "is_admin": False,
        },
        {
            "id": 2,
            "entity_type": "user",
            "entity_id": "admin@example.com",
            "daily_dollar_limit": 50.00,
            "weekly_dollar_limit": 100.00,
            "monthly_dollar_limit": 300.00,
            "is_admin": True,
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
```

### Running Backend Tests Locally

```bash
# Install dev dependencies
cd usage-limits/app && uv sync --group dev

# Run all tests
cd usage-limits/app && uv run pytest tests/ -v

# Run only unit tests (fast feedback)
cd usage-limits/app && uv run pytest tests/ -m unit -v

# Run only integration tests
cd usage-limits/app && uv run pytest tests/ -m integration -v

# Run tests for a specific module
cd usage-limits/app && uv run pytest tests/unit/test_budget.py -v

# Run with coverage
cd usage-limits/app && uv run pytest tests/ --cov=core --cov-report=term-missing

# Run with coverage threshold (fails if under 80%)
cd usage-limits/app && uv run pytest tests/ --cov=core --cov-fail-under=80
```

---

## Frontend (TypeScript / Vitest / npm)

### Installing Frontend Test Dependencies

```bash
cd usage-limits/app/frontend && npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

### Vitest Configuration

Add test config to `vite.config.ts`:

```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import path from "path";

export default defineConfig({
  plugins: [TanStackRouterVite({ target: "react", autoCodeSplitting: true }), react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "dist",
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/__tests__/setup.ts"],
    include: ["src/__tests__/**/*.test.{ts,tsx}"],
    css: false,
  },
});
```

### TypeScript Configuration for Tests

Add to `tsconfig.json`:

```json
{
  "compilerOptions": {
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  }
}
```

### Test Setup File

Place at `frontend/src/__tests__/setup.ts`:

```ts
import "@testing-library/jest-dom";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Automatically cleanup after each test
afterEach(() => {
  cleanup();
});
```

### Test Providers Helper

Place at `frontend/src/__tests__/helpers/render.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function TestProviders({ children }: { children: ReactNode }) {
  const queryClient = createTestQueryClient();
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

export function renderWithProviders(ui: React.ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return render(ui, { wrapper: TestProviders, ...options });
}
```

### Running Frontend Tests Locally

```bash
# Run all tests once
cd usage-limits/app/frontend && npx vitest run

# Run in watch mode (during development)
cd usage-limits/app/frontend && npx vitest

# Run a specific test file
cd usage-limits/app/frontend && npx vitest run src/__tests__/routes/overview.test.tsx

# Run with coverage
cd usage-limits/app/frontend && npx vitest run --coverage

# Type-check (no emit)
cd usage-limits/app/frontend && npx tsc --noEmit
```

---

## Combined (Makefile from repo root)

```bash
# Run all backend tests
make test-backend

# Run all frontend tests
make test-frontend

# Run everything
make test-all

# Type-check frontend
make type-check
```
