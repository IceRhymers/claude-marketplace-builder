---
name: tdd-uc-mcp-proxy
description: >
  Enforces test-driven development workflow when building or modifying the
  uc-mcp-proxy package. Auto-triggers when creating or editing Python files
  under the uc-mcp-proxy/ directory. Requires writing failing tests before
  implementation. Provides mocking patterns for MCP SDK transports, Databricks
  SDK OAuth, httpx Auth, and anyio stream bridging. Use when writing proxy code,
  adding new modules, or implementing features in the uc-mcp-proxy package.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# TDD for uc-mcp-proxy

Enforce test-driven development when building the MCP stdio-to-Streamable-HTTP proxy.

**Announce at start:** "Using tdd-uc-mcp-proxy skill — enforcing test-first development."

## Project Context

The `uc-mcp-proxy` is a lightweight Python package (~80 lines) that:
- Bridges MCP protocol from stdio (Claude Code) to Streamable HTTP (Databricks App)
- Injects fresh Databricks OAuth tokens per-request via `httpx.Auth` subclass
- Uses `WorkspaceClient(profile=...)` for SDK-managed token refresh
- Ships as a PEX executable via GitHub Releases

```
uc-mcp-proxy/
├── pyproject.toml
├── build/
│   └── build.sh                  # PEX builder
├── src/uc_mcp_proxy/
│   ├── __init__.py
│   └── __main__.py               # CLI entry point + proxy logic
└── tests/
    ├── __init__.py
    ├── conftest.py               # Shared fixtures
    ├── unit/
    │   ├── __init__.py
    │   ├── test_auth.py          # DatabricksAuth httpx.Auth subclass
    │   ├── test_bridge.py        # Stream copy / bidirectional bridging
    │   └── test_cli.py           # Argument parsing, client construction
    └── integration/
        ├── __init__.py
        └── test_proxy.py         # End-to-end with mocked transports
```

## Critical Rules (always follow)

1. **NEVER write implementation code before its test exists and fails** — the test file must be created and run (showing FAIL or ImportError) before the source file
2. **NEVER skip the red-green-refactor cycle** — every function goes through: write test -> see it fail -> implement -> see it pass -> refactor
3. **NEVER mock what you own** — mock external boundaries (MCP SDK transports, Databricks SDK, httpx), not internal functions
4. **NEVER commit code with failing tests** — all tests must pass before any commit
5. **ALWAYS create `conftest.py` before any test files** in a new test directory
6. **ALWAYS use fixtures for shared test state** — no global variables in test files
7. **ALWAYS separate unit tests from integration tests** using pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`)
8. **ALWAYS use `@pytest.mark.anyio`** for async test functions — the proxy is fully async

## Required Steps

Copy this checklist when starting work on any module:

```
- [ ] Test file created at tests/{unit|integration}/test_<module>.py
- [ ] conftest.py exists with required fixtures
- [ ] Test runs and FAILS (red phase confirmed)
- [ ] Source file created/modified at src/uc_mcp_proxy/<module>.py
- [ ] Minimal implementation makes test PASS (green phase confirmed)
- [ ] Code refactored with tests still passing (refactor phase)
- [ ] Coverage check: all public functions have at least one test
- [ ] pytest markers applied (@pytest.mark.unit or @pytest.mark.integration)
```

## Workflow

### Step 0: Verify Test Infrastructure

Before writing any tests, ensure the project has pytest configured:

```bash
ls uc-mcp-proxy/tests/conftest.py uc-mcp-proxy/tests/__init__.py uc-mcp-proxy/pyproject.toml 2>/dev/null
```

If missing, create the test infrastructure first. See [test-infrastructure.md](test-infrastructure.md) for the complete conftest.py template and pytest configuration.

### Step 1: RED — Write a Failing Test

For the function you are about to implement, write the test FIRST:

```python
# tests/unit/test_auth.py
import pytest
import httpx
from unittest.mock import MagicMock

@pytest.mark.unit
class TestDatabricksAuth:
    """Tests for DatabricksAuth httpx.Auth subclass."""

    def test_injects_bearer_token(self, mock_workspace_client):
        from uc_mcp_proxy import DatabricksAuth
        auth = DatabricksAuth(mock_workspace_client)

        request = httpx.Request("POST", "https://example.com/mcp")
        flow = auth.sync_auth_flow(request)
        authed = next(flow)

        assert authed.headers["Authorization"] == "Bearer test-oauth-token"
```

Run the test to confirm it FAILS:

```bash
cd uc-mcp-proxy && python -m pytest tests/unit/test_auth.py -v 2>&1 | head -30
```

**Expected output:** `FAILED` or `ERROR` (ImportError is acceptable at red phase).

**STOP if the test passes.** A passing test before implementation means the test is not testing anything meaningful. Rewrite it.

### Step 2: GREEN — Minimal Implementation

Write the minimum code to make the test pass. No more, no less.

```bash
cd uc-mcp-proxy && python -m pytest tests/unit/test_auth.py -v
```

**Expected output:** All tests `PASSED`.

Rules for this phase:
- Write ONLY enough code to pass the tests
- Do not add features not covered by tests
- Do not optimize — that comes in refactor
- If you need a new dependency, add it to `pyproject.toml` under `[project.dependencies]`

### Step 3: REFACTOR — Clean Up

With tests green, improve the code:
- Extract constants
- Improve naming
- Remove duplication
- Add type hints to public interfaces

Run tests after EVERY refactor change:

```bash
cd uc-mcp-proxy && python -m pytest tests/unit/test_auth.py -v
```

### Step 4: Expand Coverage

After the initial red-green-refactor cycle, add tests for:
- Edge cases (missing profile, invalid URL, connection refused)
- Error handling (expired refresh tokens, closed streams)
- Stream lifecycle (graceful shutdown, one-side close)

Repeat the red-green-refactor cycle for each new test.

### Step 5: Run Full Suite

Before considering the module complete:

```bash
cd uc-mcp-proxy && python -m pytest tests/ -v --tb=short
```

All tests must pass. No exceptions.

## Test Organization

### Naming Conventions

| Convention | Pattern | Example |
|-----------|---------|---------|
| Test file | `test_<module>.py` | `test_auth.py` |
| Test class | `TestClassName` grouped by function | `TestDatabricksAuth` |
| Test method | `test_<behavior>_<condition>` | `test_injects_fresh_token_per_request` |
| Fixture | `mock_<dependency>` or descriptive noun | `mock_workspace_client` |
| Marker | `@pytest.mark.unit` or `@pytest.mark.integration` | — |
| Async marker | `@pytest.mark.anyio` | Required for all async tests |

### Test-to-Source Mapping

| Source | Test | Type |
|--------|------|------|
| `__main__.py` (DatabricksAuth) | `tests/unit/test_auth.py` | unit |
| `__main__.py` (copy_stream, bridge) | `tests/unit/test_bridge.py` | unit |
| `__main__.py` (main, arg parsing) | `tests/unit/test_cli.py` | unit |
| `__main__.py` (full proxy flow) | `tests/integration/test_proxy.py` | integration |

## Mocking Strategy

Mock at the boundary — external dependencies only. Never mock internal functions.

**Boundaries to mock:**
- `mcp.server.stdio.stdio_server` — local stdio transport
- `mcp.client.streamable_http.streamablehttp_client` — remote HTTP transport
- `databricks.sdk.WorkspaceClient` — OAuth token management
- `httpx.AsyncClient` — HTTP client (only if testing auth injection directly)

**Do NOT mock:**
- `copy_stream()` — it's internal logic, test it with real anyio memory streams
- `bridge()` — test with real streams, mock only the transport context managers

See [mock-patterns.md](mock-patterns.md) for complete mocking templates.
(Keywords: mock, patch, MagicMock, WorkspaceClient, stdio_server, streamablehttp_client, httpx, Auth, anyio, streams)

## Fixture Patterns

See [test-infrastructure.md](test-infrastructure.md) for:
- Complete `conftest.py` template with all shared fixtures
- pytest configuration (markers, paths, options)
- `pyproject.toml` `[tool.pytest.ini_options]` configuration

(Keywords: conftest, fixture, pytest.ini, markers, anyio, memory_object_stream)

## CI Integration

See [ci-patterns.md](ci-patterns.md) for:
- Makefile targets: `test-proxy`, `test-proxy-coverage`, `build-proxy`
- PEX build configuration
- GitHub Actions release workflow

(Keywords: CI, coverage, Makefile, PEX, GitHub Releases, build.sh)

## Common Issues

| Issue | Solution |
|-------|----------|
| **ImportError in tests** | Ensure `pythonpath = ["src"]` in pyproject.toml |
| **Mock not applied** | `@patch` target must match the import path in the SOURCE file, not the test file |
| **Async test not running** | Add `@pytest.mark.anyio` to async test functions |
| **Stream deadlock in tests** | Use buffered memory streams: `anyio.create_memory_object_stream(16)` |
| **Auth flow generator issues** | Step with `next(flow)` for sync, `await flow.__anext__()` for async |
| **PEX build fails** | Check `uv pip compile` succeeds first; verify entry point matches `[project.scripts]` |

## Red Flags

**Never:**
- Write a source file without its test file existing first
- Leave a `# TODO: add tests` comment — add the test NOW
- Use `pytest.skip()` to defer broken tests
- Test implementation details (private methods, internal state)
- Share mutable state between test methods
- Use `time.sleep()` in async tests — use `anyio` primitives

**Always:**
- Run the failing test BEFORE writing implementation
- Mock at the boundary, not internal functions
- Use descriptive test names that explain the expected behavior
- Keep each test focused on one behavior
- Clean up test state in fixtures, not in test methods
- Use real anyio memory streams for bridge/copy tests (no mocking needed)

## Related Skills

- **[tdd-databricks-app](../tdd-databricks-app/SKILL.md)** — TDD patterns for Databricks apps (similar structure, different dependencies)
