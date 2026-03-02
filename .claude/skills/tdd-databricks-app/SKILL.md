---
name: tdd-databricks-app
description: >
  Enforces test-driven development workflow when building or modifying Databricks
  app code in this marketplace repo. Auto-triggers when creating Python modules
  under any plugins/*/skills/*/app/ directory. Requires writing failing tests
  before implementation. Provides mocking patterns for Databricks SDK, Lakebase,
  and SQL warehouse dependencies. Use when writing Python app code, adding new
  modules, or implementing features in a Databricks app within this repo.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# TDD for Databricks Apps

Enforce test-driven development when building Databricks application modules in this marketplace.

**Announce at start:** "Using tdd-databricks-app skill — enforcing test-first development."

## Critical Rules (always follow)

1. **NEVER write implementation code before its test exists and fails** — the test file must be created and run (showing FAIL or ImportError) before the source file
2. **NEVER skip the red-green-refactor cycle** — every module goes through: write test → see it fail → implement → see it pass → refactor
3. **NEVER mock what you own** — mock external boundaries (Databricks SDK, Lakebase pool, SQL warehouse), not internal modules
4. **NEVER commit code with failing tests** — all tests must pass before any commit
5. **ALWAYS create `conftest.py` before any test files** in a new test directory
6. **ALWAYS use fixtures for shared test state** — no global variables in test files
7. **ALWAYS separate unit tests from integration tests** using pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`)

## Required Steps

Copy this checklist when starting work on any module:

```
- [ ] Test file created at app/tests/{unit|integration}/test_<module>.py
- [ ] conftest.py exists with required fixtures
- [ ] Test runs and FAILS (red phase confirmed)
- [ ] Source file created at app/core/<module>.py
- [ ] Minimal implementation makes test PASS (green phase confirmed)
- [ ] Code refactored with tests still passing (refactor phase)
- [ ] Coverage check: all public functions have at least one test
- [ ] pytest markers applied (@pytest.mark.unit or @pytest.mark.integration)
```

## Workflow

### Step 0: Verify Test Infrastructure

Before writing any tests, ensure the app has pytest configured:

```bash
ls app/tests/conftest.py app/tests/__init__.py app/pyproject.toml 2>/dev/null
```

If missing, create the test infrastructure first. See [test-infrastructure.md](test-infrastructure.md) for the complete conftest.py template and pytest configuration.

### Step 1: RED — Write a Failing Test

For the module you are about to implement, write the test FIRST:

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
cd plugins/databricks-skills/skills/<app-name>/app && python -m pytest tests/unit/test_<module>.py -v 2>&1 | head -30
```

**Expected output:** `FAILED` or `ERROR` (ImportError is acceptable at red phase).

**STOP if the test passes.** A passing test before implementation means the test is not testing anything meaningful. Rewrite it.

### Step 2: GREEN — Minimal Implementation

Write the minimum code to make the test pass. No more, no less.

```bash
cd plugins/databricks-skills/skills/<app-name>/app && python -m pytest tests/unit/test_<module>.py -v
```

**Expected output:** All tests `PASSED`.

Rules for this phase:
- Write ONLY enough code to pass the tests
- Do not add features not covered by tests
- Do not optimize — that comes in refactor
- If you need a new dependency, add it to both `requirements.txt` AND `test-requirements.txt`

### Step 3: REFACTOR — Clean Up

With tests green, improve the code:
- Extract constants and configuration
- Improve naming
- Remove duplication
- Add type hints to public interfaces

Run tests after EVERY refactor change:

```bash
cd plugins/databricks-skills/skills/<app-name>/app && python -m pytest tests/unit/test_<module>.py -v
```

### Step 4: Expand Coverage

After the initial red-green-refactor cycle, add tests for:
- Edge cases (empty inputs, None values, boundary conditions)
- Error handling (exceptions, timeouts, connection failures)
- Integration points (if the module calls other modules)

Repeat the red-green-refactor cycle for each new test.

### Step 5: Run Full Suite

Before considering the module complete:

```bash
cd plugins/databricks-skills/skills/<app-name>/app && python -m pytest tests/ -v --tb=short
```

All tests must pass. No exceptions.

## Test Organization

### Directory Structure

```
app/tests/
├── __init__.py
├── conftest.py                   # Shared fixtures (mocks, sample data, env vars)
├── unit/                         # Pure logic tests — no external calls
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_usage.py
│   ├── test_budget.py
│   ├── test_enforcer.py
│   └── test_otel.py
└── integration/                  # Multi-module tests — still mocked at boundaries
    ├── __init__.py
    ├── test_db.py
    ├── test_enforcement_flow.py
    └── test_validate_access.py
```

### Naming Conventions

| Convention | Pattern | Example |
|-----------|---------|---------|
| Test file | `test_<source_module>.py` | `test_budget.py` |
| Test class | `TestClassName` grouped by function | `TestEvaluateBudget` |
| Test method | `test_<behavior>_<condition>` | `test_returns_zero_for_unknown_user` |
| Fixture | `mock_<dependency>` or descriptive noun | `mock_workspace_client` |
| Marker | `@pytest.mark.unit` or `@pytest.mark.integration` | — |

### Test-to-Source Mapping

Every source file MUST have a corresponding test file:

| Source | Test | Type |
|--------|------|------|
| `core/config.py` | `tests/unit/test_config.py` | unit |
| `core/db.py` | `tests/integration/test_db.py` | integration |
| `core/usage.py` | `tests/unit/test_usage.py` | unit |
| `core/budget.py` | `tests/unit/test_budget.py` | unit |
| `core/enforcer.py` | `tests/unit/test_enforcer.py` | unit |
| `core/otel.py` | `tests/unit/test_otel.py` | unit |
| `setup/init_schema.py` | `tests/integration/test_db.py` | integration |
| `setup/validate_access.py` | `tests/integration/test_validate_access.py` | integration |
| `pages/*.py` | *(no dedicated tests — test the data functions they call)* | — |

## Mocking Strategy

Mock at the boundary — external dependencies only. Never mock internal modules.

**Boundaries to mock:**
- `databricks.sdk.WorkspaceClient` — SDK calls (statement_execution, serving_endpoints)
- `psycopg_pool.ConnectionPool` — Lakebase database connections
- `psycopg.Connection` / `psycopg.Cursor` — SQL execution
- `apscheduler.schedulers.background.BackgroundScheduler` — timer
- Environment variables — via `monkeypatch.setenv`

See [mock-patterns.md](mock-patterns.md) for complete mocking templates.
(Keywords: mock, patch, MagicMock, WorkspaceClient, psycopg, ConnectionPool, statement_execution, serving_endpoints, permissions)

## Fixture Patterns

See [test-infrastructure.md](test-infrastructure.md) for:
- Complete `conftest.py` template with all shared fixtures
- pytest configuration (markers, paths, options)
- `test-requirements.txt` dependencies
- `pyproject.toml` `[tool.pytest.ini_options]` configuration

(Keywords: conftest, fixture, pytest.ini, markers, test-requirements, setup)

## CI Integration

See [ci-patterns.md](ci-patterns.md) for:
- Makefile targets: `test-app`, `test-app-coverage`
- Coverage reporting configuration
- Pre-commit hook for test execution

(Keywords: CI, coverage, Makefile, pre-commit, pytest-cov)

## Common Issues

| Issue | Solution |
|-------|----------|
| **ImportError in tests** | Ensure `pythonpath = ["."]` in pyproject.toml; imports use `from core.<module>` |
| **Mock not applied** | `@patch` target must match the import path in the SOURCE file, not the test file |
| **Lakebase pool mock leaking** | Use `mock_db_pool` fixture per-test, not `autouse=True` |
| **Async test issues** | Databricks SDK is synchronous — no async test infrastructure needed |
| **Streamlit import errors** | Never import `streamlit` in unit tests; pages are tested via their data functions |
| **Test order dependency** | All tests must be independent; use `pytest-randomly` to detect coupling |
| **Slow tests** | Mark integration tests with `@pytest.mark.integration`; run `pytest -m unit` for fast feedback |

## Red Flags

**Never:**
- Write a source file without its test file existing first
- Leave a `# TODO: add tests` comment — add the test NOW
- Use `pytest.skip()` to defer broken tests
- Test implementation details (private methods, internal state)
- Share mutable state between test methods

**Always:**
- Run the failing test BEFORE writing implementation
- Mock at the boundary, not internal functions
- Use descriptive test names that explain the expected behavior
- Keep each test focused on one behavior
- Clean up test state in fixtures, not in test methods

## Related Skills

- **[databricks-app-python](../databricks-app-python/SKILL.md)** — Streamlit app patterns, Lakebase connectivity
- **[databricks-python-sdk](../databricks-python-sdk/SKILL.md)** — SDK API reference for writing accurate mocks
