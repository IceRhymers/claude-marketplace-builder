## ADDED Requirements

### Requirement: Backend testing stack installed
The system SHALL include `pytest`, `pytest-asyncio`, and `httpx` as dev dependencies in `claude-agent-app/app/pyproject.toml` under `[project.optional-dependencies]` or `[dependency-groups]`, and `asyncio_mode = "auto"` SHALL be set in the `[tool.pytest.ini_options]` section so all async test functions run without per-function decorators.

#### Scenario: pytest discovers and runs all backend tests
- **WHEN** `pytest` is run from `claude-agent-app/app/`
- **THEN** all files matching `tests/**/test_*.py` are collected, async test functions execute without `@pytest.mark.asyncio`, and the exit code is `0` when all tests pass

#### Scenario: httpx AsyncClient used for FastAPI integration tests
- **WHEN** an integration test imports `httpx.AsyncClient` with `transport=ASGITransport(app=app)`
- **THEN** the full FastAPI ASGI stack (middleware, dependencies, exception handlers) is exercised without binding a TCP port

### Requirement: Backend test directory structure mirrors usage-limits
The system SHALL organize backend tests under `claude-agent-app/app/tests/` with the layout:
```
tests/
  __init__.py
  conftest.py
  unit/
    __init__.py
    test_auth.py
    test_agent_pool.py
    test_skills.py
    test_config.py
    test_deps.py
  integration/
    __init__.py
    test_db.py
    test_stream.py
    test_conversations.py
```

#### Scenario: Unit tests run without external connections
- **WHEN** `pytest tests/unit/` is run with no Databricks credentials or live database
- **THEN** all unit tests pass using only in-process mocks

#### Scenario: Integration tests isolated from production data
- **WHEN** `pytest tests/integration/` is run with a test PostgreSQL connection string
- **THEN** integration tests create their own tables, insert test data, and clean up after each test without touching production state

### Requirement: conftest.py provides shared fixtures
The `claude-agent-app/app/tests/conftest.py` SHALL define the following fixtures available to all test files:

- `env_vars(monkeypatch)`: Sets `PGHOST`, `PGDATABASE`, `LAKEBASE_INSTANCE`, `SKILLS_VOLUME_PATH`, `AGENT_TTL_MINUTES`, `SKILLS_RELOAD_INTERVAL_SECONDS` env vars for the duration of a test
- `mock_workspace_client()`: Returns a `MagicMock` with `current_user.me()` pre-configured to return a mock user object with `user_name = "test@example.com"` and `database.generate_database_credential()` returning a mock credential with `token = "mock-oauth-token"`
- `mock_skills_config()`: Returns a `SkillsConfig` instance with one sample SKILL.md string (`"# Getting Started\nThis is a test skill."`) and a minimal `mcp_config` dict (`{"mcpServers": {}}`)
- `mock_agent_pool()`: Returns a `MagicMock` for `AgentPool` where `get_or_create` is an async function returning a mock `ClaudeAgent` that yields a pre-scripted list of SSE event dicts: `[{"type": "text_delta", "text": "Hello"}, {"type": "done"}]`
- `db_session(env_vars)`: Yields a SQLAlchemy `Session` connected to a test in-memory or test PostgreSQL database with all tables created via `Base.metadata.create_all`

#### Scenario: env_vars fixture restores environment after test
- **WHEN** a test uses the `env_vars` fixture and then completes
- **THEN** all environment variables set by the fixture are restored to their pre-test values (via `monkeypatch` teardown)

#### Scenario: mock_workspace_client configures all required sub-services
- **WHEN** a test uses the `mock_workspace_client` fixture
- **THEN** accessing `client.current_user.me()` returns a mock with `user_name = "test@example.com"` and `client.database.generate_database_credential()` returns a mock with `token = "mock-oauth-token"`

#### Scenario: mock_agent_pool streams scripted SSE events
- **WHEN** a test calls `await mock_agent_pool.get_or_create(conversation_id, user_id, access_token)` and iterates the returned agent
- **THEN** it yields `{"type": "text_delta", "text": "Hello"}` followed by `{"type": "done"}` without any real Claude API calls

### Requirement: Frontend testing stack installed
The system SHALL include `vitest`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, and `msw` as dev dependencies in `claude-agent-app/app/frontend/package.json`, with a `vitest.config.ts` that sets `environment: "jsdom"` and `setupFiles: ["./src/test/setup.ts"]`.

#### Scenario: vitest discovers and runs all frontend tests
- **WHEN** `pnpm test` is run from `claude-agent-app/app/frontend/`
- **THEN** all files matching `src/**/*.test.{ts,tsx}` are collected and executed, with `@testing-library/jest-dom` matchers available globally

#### Scenario: msw intercepts fetch in Node environment
- **WHEN** a test file imports `server` from `src/test/server.ts` and calls `server.use(handler)` to override an endpoint
- **THEN** subsequent `fetch` calls in the component under test are intercepted by msw without any real HTTP requests leaving the process

### Requirement: Frontend test setup file and msw server
The system SHALL provide:

- `src/test/setup.ts`: imports `@testing-library/jest-dom/vitest` to extend `expect`, and starts/resets/stops the msw `server` via `beforeAll`/`afterEach`/`afterAll` hooks
- `src/test/server.ts`: creates and exports an msw `setupServer()` instance with default handlers for all API endpoints (`GET /api/me`, `GET /api/conversations`, `POST /api/conversations`, `GET /api/conversations/:id/messages`, `DELETE /api/conversations/:id`, `GET /api/conversations/:id/stream`)
- `src/test/handlers.ts`: exports the default handler array used by `server.ts`, with realistic mock responses matching the API contract

#### Scenario: Default handlers return consistent mock data
- **WHEN** a component test renders without overriding any msw handlers
- **THEN** `GET /api/me` returns `{"user_id": "test@example.com", "display_name": "Test User"}`, `GET /api/conversations` returns an array with one conversation, and `GET /api/conversations/:id/stream` returns a minimal SSE stream with one `text_delta` event and a `done` event

#### Scenario: Per-test handler override replaces default
- **WHEN** a test calls `server.use(http.get('/api/conversations', () => HttpResponse.json([])))` before rendering
- **THEN** `GET /api/conversations` returns an empty array for that test only, and the default handler is restored after the test

### Requirement: SSE streaming mock pattern for React tests
The system SHALL provide a documented pattern in `src/test/handlers.ts` for mocking the SSE streaming endpoint using a `ReadableStream` that emits pre-scripted SSE chunks, so `ChatInput` and conversation route tests can verify streaming token rendering.

#### Scenario: Streamed text delta renders in component
- **WHEN** a test triggers `streamMessage` via user interaction and the msw handler returns a `ReadableStream` emitting `data: {"type":"text_delta","text":"Hello"}\n\ndata: {"type":"done"}\n\n`
- **THEN** the `MessageBubble` component renders "Hello" without making any real HTTP requests

### Requirement: CI test step in GitHub Actions
The system SHALL add a `test` job to `.github/workflows/publish-artifact.yml` (or a separate `ci.yml` workflow) that:
- Runs `pytest` for the backend (with test PostgreSQL via GitHub Actions `services`)
- Runs `pnpm test --run` for the frontend
- Gates the artifact publish job (`needs: test`)

#### Scenario: Test job runs before publish
- **WHEN** a commit is pushed to `main`
- **THEN** the `test` job runs both backend and frontend test suites before the `publish` job starts, and the publish job is skipped if the test job fails

#### Scenario: Backend CI uses PostgreSQL service container
- **WHEN** the `test` job runs in GitHub Actions
- **THEN** a PostgreSQL service container is started, `PGHOST` / `PGDATABASE` env vars point to it, and `pytest tests/integration/` connects successfully for migration and CRUD tests
