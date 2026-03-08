## Why

The `claude-agent-sdk-databricks-app` change places all testing in group 10 (last), causing implementation to proceed without tests — violating test-driven development principles. Tanner requires TDD enforcement: tests must be written before every component is implemented, in a red-green-refactor cycle, so regressions are caught at the authoring stage rather than after the fact.

## What Changes

- New `specs/testing/spec.md` defining the full testing framework for both the FastAPI backend and the React frontend
- All 6 existing spec files updated with a `## Test Requirements` section defining what must be tested per capability
- `design.md` updated with architecture decision D8 mandating TDD (tests before implementation, red-green-refactor cycle enforced)
- `tasks.md` fully restructured so that for every implementation task a corresponding test task appears immediately before it, following the pattern:
  ```
  - [ ] X.Y  Write tests for [component] (RED)
  - [ ] X.Y+1 Implement [component] to pass tests (GREEN)
  ```
- A new Group 0 "Testing Infrastructure" prepended to `tasks.md` covering pytest + pytest-asyncio + httpx setup, `conftest.py`, shared fixtures, vitest + testing-library + msw setup for React, and a CI test step in GitHub Actions

## Capabilities

### New Capabilities

- `testing`: Testing framework specification — backend pytest/pytest-asyncio/httpx stack, frontend vitest/@testing-library/react/msw stack, directory structure, conftest.py and fixture patterns, CI integration

### Modified Capabilities

- `agent-chat`: Add `## Test Requirements` section defining SSE streaming tests, auth tests, ownership tests, and message persistence tests
- `agent-pool`: Add `## Test Requirements` section defining pool spawn, reuse, TTL eviction, cross-user isolation, and shutdown drain tests
- `conversation-state`: Add `## Test Requirements` section defining Alembic migration tests, CRUD tests, and user isolation tests
- `user-identity`: Add `## Test Requirements` section defining dependency injection tests and token resolution tests
- `mcp-config`: Add `## Test Requirements` section defining volume load tests, hot-reload tests, and token substitution tests
- `artifact-pipeline`: Add `## Test Requirements` section defining shell script and GitHub Actions validation tests

## Impact

- No new runtime dependencies — test packages (`pytest`, `pytest-asyncio`, `httpx`, `vitest`, `@testing-library/react`, `msw`) are dev-only
- All existing 40 tasks from `claude-agent-sdk-databricks-app` are preserved and reordered; no tasks are removed
- Adds approximately 40 new test-writing tasks (one per implementation task) plus a new Group 0 with ~7 infrastructure tasks
- GitHub Actions workflow gains a test step before the artifact publish step
- `claude-agent-app/app/tests/` directory structure mirrors `usage-limits/app/tests/` with `unit/`, `integration/`, and `conftest.py`
