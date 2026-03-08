## Context

The `claude-agent-sdk-databricks-app` change was authored with testing deferred to the final group (group 10). This violates test-driven development: tests should define the expected behavior before any implementation begins. Tanner requires the TDD amendment to restructure the work so that a failing test is the first artifact produced for every component, and implementation is the act of making those tests pass.

The `usage-limits/app/tests/` directory establishes the canonical test layout for Databricks Apps in this repo: a top-level `conftest.py` with shared fixtures (env vars, mock `WorkspaceClient`, DB session), `unit/` for fast isolated tests, and `integration/` for tests that exercise real DB or HTTP surfaces. The `claude-agent-app/` backend must mirror this layout exactly.

## Goals / Non-Goals

**Goals:**
- Define a concrete testing framework spec (`specs/testing/spec.md`) that implementers follow without ambiguity
- Restructure `tasks.md` so every implementation task is immediately preceded by a test-writing task
- Add D8 to `design.md` in the parent change codifying TDD as an architectural constraint, not a preference
- Provide fixture patterns for every external dependency the app has: `WorkspaceClient`, Lakebase/SQLAlchemy session, `MarketplaceLoader`/`SkillsConfig`, and the Claude Agent SDK `ClaudeAgent`
- Cover the React frontend with vitest + `@testing-library/react` + msw so component and API-layer behavior is tested before implementation
- Ensure CI runs tests on every PR via a GitHub Actions test step

**Non-Goals:**
- Achieving 100% branch coverage (quality over quantity; each spec's `Test Requirements` section defines the required scenarios, not a coverage target)
- End-to-end browser automation (Playwright, Cypress) — the msw layer is sufficient for frontend contract testing
- Evaluating agent response quality (that belongs in the `evals/` package, not pytest)
- Retrofitting tests onto `usage-limits/` (out of scope for this amendment)

## Decisions

### D1: Mirror usage-limits/app/tests/ directory layout

**Decision:** `claude-agent-app/app/tests/` mirrors `usage-limits/app/tests/` exactly: `__init__.py`, `conftest.py` at the top, then `unit/` and `integration/` subdirectories. Unit tests use `unittest.mock` and run without any external connections. Integration tests may use a test PostgreSQL instance or the FastAPI `TestClient`.

**Rationale:** Consistency with the canonical pattern reduces cognitive overhead. Developers who know how `usage-limits/` tests work immediately know how `claude-agent-app/` tests work.

**Alternative considered:** A flat test directory with no `unit/`/`integration/` split. Rejected — the split allows CI to run fast unit tests on every commit and reserve integration tests for pre-merge or nightly runs.

### D2: httpx AsyncClient as the primary HTTP test client

**Decision:** FastAPI integration tests use `httpx.AsyncClient` with `transport=ASGITransport(app=app)`, matching the `usage-limits/` pattern. `pytest-asyncio` is configured with `asyncio_mode = "auto"` in `pyproject.toml`.

**Rationale:** `httpx.AsyncClient` with ASGI transport is the recommended pattern for async FastAPI apps. It allows testing the full ASGI stack (middleware, dependency injection, exception handlers) without binding a TCP port. The `ASGITransport` makes SSE endpoint testing straightforward — responses can be iterated as async generators.

**Alternative considered:** FastAPI's built-in `TestClient` (synchronous, wraps Starlette). Rejected — the streaming SSE endpoint requires an async client; synchronous `TestClient` cannot iterate async generators cleanly.

### D3: Mock WorkspaceClient, not a live Databricks connection

**Decision:** The `conftest.py` provides a `mock_workspace_client` fixture using `unittest.mock.MagicMock` pre-configured with `current_user.me()` returning a mock user. Tests patch `core.auth.WorkspaceClient` at the module import level using `unittest.mock.patch`.

**Rationale:** Live Databricks connections require secrets, are slow, and make tests environment-dependent. The mock patterns from `usage-limits/conftest.py` are proven and sufficient. The real SDK integration is validated by deployment smoke tests, not unit tests.

**Alternative considered:** A Databricks SDK `mock_server` fixture or HTTP replay. Rejected — unnecessarily complex for the scope of unit testing authentication logic.

### D4: msw (Mock Service Worker) for React API mocking

**Decision:** Frontend tests use `msw` in a Node.js (non-browser) environment via `msw/node`. Each test file sets up handlers for the specific API endpoints it exercises. The SSE streaming endpoint is mocked by returning a `ReadableStream` with pre-scripted chunks.

**Rationale:** msw intercepts `fetch` at the network layer, allowing component tests to exercise actual `api.ts` and `stream.ts` call paths without importing FastAPI. This tests the real request/response contract, not just mocked module exports.

**Alternative considered:** Mocking `src/lib/api.ts` directly with `vi.mock`. Rejected — this divorces component tests from the actual API contract; msw keeps tests honest about what the API returns.

### D5: Test tasks interleaved immediately before implementation tasks

**Decision:** For every implementation task `X.Y`, a test task `X.Y-0.5` (shown as a new sub-item preceding it) is added: "Write tests for [component] (RED)". The implementation task is relabeled "Implement [component] to pass tests (GREEN)". No implementation task may be marked done unless its corresponding test task is also done.

**Rationale:** Interleaving rather than grouping enforces the TDD discipline at the task level. Developers cannot skip ahead to implementation without explicitly passing a test checkpoint. Group-10-style "write all tests last" patterns are eliminated structurally.

**Alternative considered:** A separate test group appended before each implementation group (e.g., group 1.5 before group 2). Rejected — cross-group reordering is confusing; immediate adjacency within the same group is clearer.

### D6: Testing infrastructure as Group 0 (runs before all implementation)

**Decision:** A new Group 0 "Testing Infrastructure" is prepended to `tasks.md`. It covers: pytest + pytest-asyncio + httpx added to `pyproject.toml`, `conftest.py` with all shared fixtures, vitest + @testing-library/react + msw added to `package.json`, and a CI test step in GitHub Actions.

**Rationale:** The test infrastructure must exist before any red-green cycle can begin. Placing it in Group 0 ensures it is the first thing implemented and is never blocked by other groups.

### D7: Fixture contract for mock MarketplaceLoader / SkillsConfig

**Decision:** `conftest.py` provides a `mock_skills_config` fixture returning a `SkillsConfig` with one sample SKILL.md string and a minimal `.mcp.json` dict. A `mock_agent_pool` fixture provides a pre-configured `MagicMock` for `AgentPool` with `get_or_create` returning a mock `ClaudeAgent` that yields a scripted async generator of SSE events.

**Rationale:** These two fixtures are needed by nearly every test touching the streaming endpoint. Centralizing them in `conftest.py` prevents duplication and ensures consistent mock contracts across test files.

## Risks / Trade-offs

**[Risk] Interleaved task numbering is harder to read if tasks are added mid-group**
→ Mitigation: Task numbers are labels, not enforced identifiers. Renumber within a group when tasks are added; OpenSpec tasks.md is a living document.

**[Risk] msw SSE mocking is non-trivial (ReadableStream in a Node environment)**
→ Mitigation: The testing spec provides explicit code snippets for the SSE mock pattern so implementers are not left to figure it out from scratch.

**[Risk] pytest-asyncio `asyncio_mode = "auto"` may conflict with synchronous fixtures**
→ Mitigation: Synchronous fixtures (env vars, mock objects) work correctly in auto mode. Only fixtures that `await` something need to be declared `async`. This is well-tested behavior in `usage-limits/`.

**[Risk] TDD discipline erodes during implementation if not enforced in code review**
→ Mitigation: The D8 decision in the parent change's `design.md` and the task structure make intent explicit. Code reviewers should reject PRs where tests are committed after implementation (check git log order).

## Migration Plan

1. Apply this TDD amendment's artifacts to the `claude-agent-sdk-databricks-app` change directory (update `design.md` with D8, add `## Test Requirements` to all 6 spec files)
2. Replace `tasks.md` in `claude-agent-sdk-databricks-app` with the TDD-restructured version (Group 0 first, all implementation tasks preceded by test tasks)
3. Create `specs/testing/spec.md` in `claude-agent-sdk-databricks-app` as a new capability spec
4. During implementation via `/opsx:apply`, Group 0 (testing infrastructure) must be completed before any other group is started

**Rollback:** The original `tasks.md` is preserved in git history. Reverting to pre-TDD task ordering requires only a `git revert` of the tasks.md commit in `claude-agent-sdk-databricks-app`.

## Open Questions

- Should `asyncio_mode = "auto"` be set globally in `pyproject.toml` (affects all tests) or only per-file with `@pytest.mark.asyncio`? Global is simpler; per-file is more explicit. (Recommendation: global, matching `usage-limits/` if it uses `asyncio_mode = "auto"`.)
- Should the integration test step in GitHub Actions gate the artifact publish step, or run in parallel? (Recommendation: gate — a failed test should block publish.)
