---
name: tdd-databricks-app
description: >
  Enforces test-driven development workflow when building or modifying Databricks
  APX apps (FastAPI backend + React frontend). Auto-triggers when creating Python
  modules under any app/ directory (FastAPI routers, core modules) or React
  components/routes under app/frontend/. Requires writing failing tests before
  implementation. Provides mocking patterns for Databricks SDK, Lakebase/SQLAlchemy,
  FastAPI TestClient, React Testing Library, and TanStack Query. Use when writing
  app code, adding new modules, or implementing features in a Databricks APX app.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# TDD for Databricks APX Apps

Enforce test-driven development when building Databricks APX applications (FastAPI + React).

**Announce at start:** "Using tdd-databricks-app skill -- enforcing test-first development for APX apps."

## Critical Rules (always follow)

1. **NEVER write implementation code before its test exists and fails** -- the test file must be created and run (showing FAIL or ImportError) before the source file
2. **NEVER skip the red-green-refactor cycle** -- every module goes through: write test -> see it fail -> implement -> see it pass -> refactor
3. **NEVER mock what you own** -- mock external boundaries (Databricks SDK, Lakebase pool, SQL warehouse, HTTP APIs), not internal modules
4. **NEVER commit code with failing tests** -- all tests must pass before any commit
5. **ALWAYS create `conftest.py` (backend) or `setup.ts` (frontend) before any test files** in a new test directory
6. **ALWAYS use fixtures (backend) or factory helpers (frontend) for shared test state** -- no global variables in test files
7. **ALWAYS separate unit tests from integration tests** using pytest markers (backend) or file organization (frontend)

## APX App Architecture

APX apps have two independently testable layers:

```
app/
  main.py              # FastAPI entrypoint with lifespan
  api.py               # Additional API routers
  deps.py              # FastAPI dependency injection (get_db, get_config, get_client)
  core/                # Business logic (pure Python, no HTTP)
  routers/             # FastAPI route handlers
  schemas/             # Pydantic response models
  setup/               # DB schema init, access validation
  tests/               # Backend tests (pytest)
  pyproject.toml       # Backend deps (managed by uv)
  frontend/
    src/
      routes/          # TanStack Router pages
      components/      # React components (ui/, apx/)
      lib/api.ts       # Axios API client
    package.json       # Frontend deps (managed by npm)
    vite.config.ts     # Vite + TanStack Router + Tailwind CSS v4
```

## Required Steps

Copy the appropriate checklist when starting work:

### Backend Module Checklist
```
- [ ] Test file created at app/tests/{unit|integration}/test_<module>.py
- [ ] conftest.py exists with required fixtures
- [ ] Test runs and FAILS (red phase confirmed)
- [ ] Source file created at app/core/<module>.py (or routers/, schemas/)
- [ ] Minimal implementation makes test PASS (green phase confirmed)
- [ ] Code refactored with tests still passing (refactor phase)
- [ ] Coverage check: all public functions have at least one test
- [ ] pytest markers applied (@pytest.mark.unit or @pytest.mark.integration)
```

### Frontend Module Checklist
```
- [ ] Test file created at app/frontend/src/__tests__/<module>.test.tsx
- [ ] Test runs and FAILS (red phase confirmed)
- [ ] Component/route created in app/frontend/src/
- [ ] Minimal implementation makes test PASS (green phase confirmed)
- [ ] Code refactored with tests still passing (refactor phase)
- [ ] Coverage check: component renders, user interactions, loading/error states tested
```

## Backend Workflow

### Step 0: Verify Test Infrastructure

```bash
ls usage-limits/app/tests/conftest.py usage-limits/app/tests/__init__.py usage-limits/app/pyproject.toml 2>/dev/null
```

If missing, create the test infrastructure first. See [test-infrastructure.md](test-infrastructure.md) for the complete conftest.py template and pytest configuration.

### Step 1: RED -- Write a Failing Test

```python
# app/tests/unit/test_<module>.py
import pytest
from unittest.mock import MagicMock, patch

@pytest.mark.unit
class TestMyFunction:
    """Tests for my_function in core/<module>.py"""

    def test_basic_behavior(self, <fixture_name>):
        from core.<module> import my_function
        result = my_function(<args>)
        assert result == <expected>

    def test_edge_case(self, <fixture_name>):
        from core.<module> import my_function
        with pytest.raises(ValueError):
            my_function(<bad_args>)
```

Run the test to confirm it FAILS:

```bash
cd usage-limits/app && uv run pytest tests/unit/test_<module>.py -v 2>&1 | head -30
```

**Expected output:** `FAILED` or `ERROR` (ImportError is acceptable at red phase).

**STOP if the test passes.** A passing test before implementation means the test is not testing anything meaningful. Rewrite it.

### Step 2: GREEN -- Minimal Implementation

Write the minimum code to make the test pass. No more, no less.

```bash
cd usage-limits/app && uv run pytest tests/unit/test_<module>.py -v
```

**Expected output:** All tests `PASSED`.

Rules for this phase:
- Write ONLY enough code to pass the tests
- Do not add features not covered by tests
- Do not optimize -- that comes in refactor
- If you need a new dependency, add it via `uv add <package>` (or `uv add --group dev <package>` for test deps)

### Step 3: REFACTOR -- Clean Up

With tests green, improve the code:
- Extract constants and configuration
- Improve naming
- Remove duplication
- Add type hints to public interfaces

Run tests after EVERY refactor change:

```bash
cd usage-limits/app && uv run pytest tests/unit/test_<module>.py -v
```

### Step 4: Expand Coverage

After the initial red-green-refactor cycle, add tests for:
- Edge cases (empty inputs, None values, boundary conditions)
- Error handling (exceptions, timeouts, connection failures)
- Integration points (if the module calls other modules)

Repeat the red-green-refactor cycle for each new test.

### Step 5: Run Full Backend Suite

```bash
cd usage-limits/app && uv run pytest tests/ -v --tb=short
```

All tests must pass. No exceptions.

## Frontend Workflow

### Step 0: Verify Test Infrastructure

Check that Vitest and React Testing Library are installed:

```bash
cd usage-limits/app/frontend && cat package.json | grep -E "vitest|testing-library"
```

If missing, install test dependencies:

```bash
cd usage-limits/app/frontend && npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom @vitejs/plugin-react
```

See [test-infrastructure.md](test-infrastructure.md) for the Vitest config and test setup file.

### Step 1: RED -- Write a Failing Test

For a **component**:

```tsx
// frontend/src/__tests__/overview.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock the API module
vi.mock("@/lib/api", () => ({
  getOverviewMetrics: vi.fn(),
  getTopUsers: vi.fn(),
}));

describe("OverviewPage", () => {
  it("renders metric cards", async () => {
    // Arrange: mock API responses
    // Act: render the component
    // Assert: verify expected content
  });
});
```

For an **API client function**:

```tsx
// frontend/src/__tests__/api.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import axios from "axios";

vi.mock("axios", () => ({
  default: { create: vi.fn(() => ({ get: vi.fn(), post: vi.fn(), delete: vi.fn() })) },
}));

describe("listBudgets", () => {
  it("calls GET /api/budgets/", async () => {
    // ...
  });
});
```

Run the test to confirm it FAILS:

```bash
cd usage-limits/app/frontend && npx vitest run src/__tests__/overview.test.tsx 2>&1 | head -30
```

**Expected output:** `FAIL` or compilation error.

### Step 2: GREEN -- Minimal Implementation

Write the minimum code to make the test pass:

```bash
cd usage-limits/app/frontend && npx vitest run src/__tests__/overview.test.tsx
```

Rules for this phase:
- Write ONLY enough code to pass the tests
- If you need a new dependency, add it via `npm install <package>` (or `npm install -D <package>` for test deps)

### Step 3: REFACTOR -- Clean Up

With tests green, improve the code. Run tests after every change:

```bash
cd usage-limits/app/frontend && npx vitest run src/__tests__/overview.test.tsx
```

### Step 4: Run Full Frontend Suite

```bash
cd usage-limits/app/frontend && npx vitest run
```

Also verify TypeScript compiles:

```bash
cd usage-limits/app/frontend && npx tsc --noEmit
```

## Test Organization

### Backend Directory Structure

```
app/tests/
  __init__.py
  conftest.py                   # Shared fixtures (mocks, sample data, env vars)
  unit/                         # Pure logic tests -- no external calls
    __init__.py
    test_config.py
    test_usage.py
    test_budget.py
    test_evaluator.py
    test_pricing.py
    test_discovery.py
    test_otel.py
    test_deps.py
    test_router_overview.py
    test_router_users.py
    test_router_budgets.py
    test_router_warnings.py
    test_router_audit.py
    test_router_otel.py
    test_router_discovery.py
    test_api.py
  integration/                  # Multi-module tests -- still mocked at boundaries
    __init__.py
    test_db.py
    test_validate_access.py
```

### Frontend Directory Structure

```
app/frontend/src/
  __tests__/
    setup.ts                    # Global test setup (jest-dom matchers, cleanup)
    helpers/
      render.tsx                # Custom render with providers (QueryClient, Router)
    routes/
      overview.test.tsx
      users.test.tsx
      budgets.test.tsx
      otel.test.tsx
    components/
      metric-card.test.tsx
    lib/
      api.test.ts
```

### Naming Conventions

**Backend:**

| Convention | Pattern | Example |
|-----------|---------|---------|
| Test file | `test_<source_module>.py` | `test_budget.py` |
| Test class | `TestClassName` grouped by function | `TestEvaluateBudget` |
| Test method | `test_<behavior>_<condition>` | `test_returns_zero_for_unknown_user` |
| Fixture | `mock_<dependency>` or descriptive noun | `mock_workspace_client` |
| Marker | `@pytest.mark.unit` or `@pytest.mark.integration` | -- |

**Frontend:**

| Convention | Pattern | Example |
|-----------|---------|---------|
| Test file | `<component>.test.tsx` or `<module>.test.ts` | `overview.test.tsx` |
| Describe block | Component or function name | `describe("OverviewPage", ...)` |
| Test name | `it("<does something>")` | `it("renders cost metric card")` |
| Mock | `vi.mock("@/lib/api", ...)` | -- |

### Backend Test-to-Source Mapping

Every source file MUST have a corresponding test file:

| Source | Test | Type |
|--------|------|------|
| `core/config.py` | `tests/unit/test_config.py` | unit |
| `core/db.py` | `tests/integration/test_db.py` | integration |
| `core/usage.py` | `tests/unit/test_usage.py` | unit |
| `core/budget.py` | `tests/unit/test_budget.py` | unit |
| `core/evaluator.py` | `tests/unit/test_evaluator.py` | unit |
| `core/pricing.py` | `tests/unit/test_pricing.py` | unit |
| `core/discovery.py` | `tests/unit/test_discovery.py` | unit |
| `core/otel.py` | `tests/unit/test_otel.py` | unit |
| `deps.py` | `tests/unit/test_deps.py` | unit |
| `api.py` | `tests/unit/test_api.py` | unit |
| `routers/overview.py` | `tests/unit/test_router_overview.py` | unit |
| `routers/users.py` | `tests/unit/test_router_users.py` | unit |
| `routers/budgets.py` | `tests/unit/test_router_budgets.py` | unit |
| `routers/warnings.py` | `tests/unit/test_router_warnings.py` | unit |
| `routers/audit.py` | `tests/unit/test_router_audit.py` | unit |
| `routers/otel.py` | `tests/unit/test_router_otel.py` | unit |
| `routers/discovery.py` | `tests/unit/test_router_discovery.py` | unit |
| `schemas/*.py` | *(tested implicitly via router tests)* | -- |
| `setup/init_schema.py` | `tests/integration/test_db.py` | integration |
| `setup/validate_access.py` | `tests/integration/test_validate_access.py` | integration |

### Frontend Test-to-Source Mapping

| Source | Test |
|--------|------|
| `routes/overview.tsx` | `__tests__/routes/overview.test.tsx` |
| `routes/users/index.tsx` | `__tests__/routes/users.test.tsx` |
| `routes/users/$userEmail.tsx` | `__tests__/routes/user-detail.test.tsx` |
| `routes/budgets/index.tsx` | `__tests__/routes/budgets.test.tsx` |
| `routes/otel.tsx` | `__tests__/routes/otel.test.tsx` |
| `lib/api.ts` | `__tests__/lib/api.test.ts` |
| Custom components | `__tests__/components/<name>.test.tsx` |

## Dependency Management

### Backend (uv)

```bash
# Add a runtime dependency
cd usage-limits/app && uv add <package>

# Add a dev/test dependency
cd usage-limits/app && uv add --group dev <package>

# Run tests through uv
cd usage-limits/app && uv run pytest tests/ -v

# Sync dependencies from lockfile
cd usage-limits/app && uv sync
```

### Frontend (npm)

```bash
# Add a runtime dependency
cd usage-limits/app/frontend && npm install <package>

# Add a dev dependency
cd usage-limits/app/frontend && npm install -D <package>

# Run tests
cd usage-limits/app/frontend && npx vitest run

# Run dev server
cd usage-limits/app/frontend && npm run dev

# Type-check
cd usage-limits/app/frontend && npx tsc --noEmit

# Build for production
cd usage-limits/app/frontend && npm run build
```

## Mocking Strategy

Mock at the boundary -- external dependencies only. Never mock internal modules.

**Backend boundaries to mock:**
- `databricks.sdk.WorkspaceClient` -- SDK calls (statement_execution, serving_endpoints)
- `sqlalchemy.orm.Session` -- Lakebase database operations
- `apscheduler.schedulers.background.BackgroundScheduler` -- timer
- Environment variables -- via `monkeypatch.setenv`

**Frontend boundaries to mock:**
- `@/lib/api` module -- all axios API calls
- `@tanstack/react-query` -- query state (or wrap with real QueryClientProvider)
- Browser APIs -- `window.location`, `localStorage`, etc.

See [mock-patterns.md](mock-patterns.md) for complete mocking templates for both backend and frontend.
(Keywords: mock, patch, MagicMock, vi.mock, WorkspaceClient, SQLAlchemy, Session, TestClient, render, screen)

## Fixture Patterns

See [test-infrastructure.md](test-infrastructure.md) for:
- Backend: complete `conftest.py` template, pytest configuration, `uv` dev dependencies
- Frontend: Vitest configuration, test setup file, custom render helper with providers
- `pyproject.toml` and `vite.config.ts` test configuration

(Keywords: conftest, fixture, vitest, setup, markers, providers, QueryClient)

## CI Integration

See [ci-patterns.md](ci-patterns.md) for:
- Makefile targets: `test-backend`, `test-frontend`, `test-all`, `type-check`
- Coverage reporting for both layers
- Build verification

(Keywords: CI, coverage, Makefile, vitest, pytest-cov, tsc)

## Common Issues

### Backend

| Issue | Solution |
|-------|----------|
| **ImportError in tests** | Ensure `pythonpath = ["."]` in pyproject.toml; imports use `from core.<module>` |
| **Mock not applied** | `@patch` target must match the import path in the SOURCE file, not the test file |
| **SQLAlchemy session mock leaking** | Use `mock_session` fixture per-test, not `autouse=True` |
| **Async test issues** | Databricks SDK is synchronous -- no async test infrastructure needed |
| **FastAPI TestClient setup** | Use `TestClient(app)` with `app.dependency_overrides[get_db] = lambda: mock_session` |
| **Test order dependency** | All tests must be independent; use `pytest-randomly` to detect coupling |
| **Slow tests** | Mark integration tests with `@pytest.mark.integration`; run `uv run pytest -m unit` for fast feedback |
| **uv dependency not found** | Run `uv sync` to install from lockfile, or `uv add --group dev <pkg>` for test deps |

### Frontend

| Issue | Solution |
|-------|----------|
| **Module not found in test** | Check `resolve.alias` in vitest config matches vite config (`@` -> `./src`) |
| **React context missing** | Use custom `renderWithProviders` that wraps with QueryClientProvider |
| **Async query not resolved** | Use `await screen.findByText(...)` or `waitFor(() => ...)` for async renders |
| **TanStack Router errors in test** | Mock `createFileRoute` or wrap component in a test router provider |
| **TypeScript errors in tests** | Add `@testing-library/jest-dom` types to tsconfig: `"types": ["vitest/globals", "@testing-library/jest-dom"]` |
| **Stale query cache between tests** | Create a fresh `QueryClient` per test in the render helper |

## Red Flags

**Never:**
- Write a source file without its test file existing first
- Leave a `# TODO: add tests` or `// TODO: add tests` comment -- add the test NOW
- Use `pytest.skip()` or `it.skip()` to defer broken tests
- Test implementation details (private methods, internal state)
- Share mutable state between test methods

**Always:**
- Run the failing test BEFORE writing implementation
- Mock at the boundary, not internal functions
- Use descriptive test names that explain the expected behavior
- Keep each test focused on one behavior
- Clean up test state in fixtures (backend) or beforeEach/afterEach (frontend)

## Related Skills

- **databricks-app-apx** -- APX framework patterns, FastAPI + React architecture
- **databricks-python-sdk** -- SDK API reference for writing accurate mocks
