## 0. Testing Infrastructure

- [ ] 0.1 Add `pytest`, `pytest-asyncio`, `httpx` to `[dependency-groups.dev]` in `claude-agent-app/app/pyproject.toml`; set `[tool.pytest.ini_options] asyncio_mode = "auto"` and `testpaths = ["tests"]`
- [ ] 0.2 Create `claude-agent-app/app/tests/__init__.py` and `claude-agent-app/app/tests/unit/__init__.py` and `claude-agent-app/app/tests/integration/__init__.py`
- [ ] 0.3 Create `claude-agent-app/app/tests/conftest.py` with fixtures: `env_vars`, `mock_workspace_client`, `mock_skills_config`, `mock_agent_pool`, `db_session`
- [ ] 0.4 Add `vitest`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `msw` to `devDependencies` in `claude-agent-app/app/frontend/package.json`; create `vitest.config.ts` with `environment: "jsdom"` and `setupFiles: ["./src/test/setup.ts"]`
- [ ] 0.5 Create `src/test/setup.ts` (imports jest-dom matchers, starts/resets/stops msw server), `src/test/server.ts` (msw `setupServer()` instance), and `src/test/handlers.ts` (default mock handlers for all API endpoints including SSE stream handler)
- [ ] 0.6 Verify testing infrastructure by running `pytest --collect-only` (zero tests, no errors) and `pnpm test --run` (zero tests, no errors)
- [ ] 0.7 Add `test` job to `.github/workflows/publish-artifact.yml` (or create `ci.yml`) running `pytest` with a PostgreSQL service container and `pnpm test --run`; add `needs: test` to the publish job

## 1. Project Scaffold

- [ ] 1.1 Create `claude-agent-app/` directory structure mirroring `usage-limits/`: `app/`, `app/core/`, `app/frontend/`, `resources/`, `scripts/`, `references/`
- [ ] 1.2 Create `claude-agent-app/app/pyproject.toml` with Python dependencies: `fastapi`, `uvicorn[standard]`, `sse-starlette`, `sqlalchemy[asyncio]`, `psycopg[binary]`, `alembic`, `apscheduler`, `anthropic[agent-sdk]`, `databricks-sdk`
- [ ] 1.3 Create `claude-agent-app/app/.python-version` pinned to match `usage-limits/`
- [ ] 1.4 Create `claude-agent-app/app/frontend/package.json` with same React 19 + Vite + TanStack + Radix + Tailwind stack as `usage-limits/`
- [ ] 1.5 Create `claude-agent-app/Makefile` with `dev`, `build`, `test`, `deploy` targets mirroring `usage-limits/Makefile`

## 2. User Identity Dependency

- [ ] 2.1 Write tests for `get_current_user` in `tests/unit/test_auth.py` (RED): valid token resolves user, missing token raises 401, invalid/expired token raises 401, dependency injection wires correctly, access_token forwarded to AgentPool
- [ ] 2.2 Create `claude-agent-app/app/core/auth.py` with `CurrentUser` dataclass (`user_id: str`, `access_token: str`) (GREEN)
- [ ] 2.3 Implement `get_current_user` FastAPI dependency in `core/auth.py` that reads `X-Forwarded-Access-Token`, calls `WorkspaceClient.current_user.me()`, and returns `CurrentUser`; raises `HTTPException(401)` on missing or invalid token (GREEN — run `pytest tests/unit/test_auth.py` to confirm all tests pass)

## 3. Database Layer

- [ ] 3.1 Write tests for database models and CRUD in `tests/unit/test_models.py` and `tests/integration/test_db.py` (RED): Alembic upgrade creates tables, upgrade is idempotent, conversation insert + user_id filter, messages cascade-delete, updated_at refresh, role constraint rejects invalid values, user isolation on list query, message lookup for non-owner returns empty
- [ ] 3.2 Create `claude-agent-app/app/core/db.py` with `create_engine_from_config` using the same Lakebase OAuth token injection pattern as `usage-limits/app/core/db.py` (GREEN)
- [ ] 3.3 Create `claude-agent-app/app/core/models.py` with `Conversation` SQLAlchemy model (`id` UUID PK, `user_id`, `title`, `created_at`, `updated_at`) and `Message` model (`id` UUID PK, `conversation_id` FK → conversations cascade delete, `user_id`, `role` constrained to `user`/`assistant`, `content`, `created_at`) (GREEN)
- [ ] 3.4 Initialize Alembic in `claude-agent-app/app/alembic/`: `alembic init`, configure `env.py` to use the app's SQLAlchemy engine and `Base.metadata` (GREEN)
- [ ] 3.5 Generate and review initial Alembic migration creating `conversations` and `messages` tables with all columns, constraints, and indexes on `(conversations.user_id)` and `(messages.conversation_id)` (GREEN — run `pytest tests/integration/test_db.py` to confirm)
- [ ] 3.6 Create `claude-agent-app/app/core/config.py` with `AppConfig` dataclass reading `PGHOST`, `PGDATABASE`, `LAKEBASE_INSTANCE`, `SKILLS_VOLUME_PATH`, `AGENT_TTL_MINUTES` (default 30), `SKILLS_RELOAD_INTERVAL_SECONDS` (default 60) from env
- [ ] 3.7 Create `claude-agent-app/app/deps.py` with `get_db` dependency yielding a SQLAlchemy `Session`

## 4. MCP and Skills Config Loader

- [ ] 4.1 Write tests for `load_config_from_volume` and `substitute_token` in `tests/unit/test_skills.py` (RED): valid config loaded, missing latest.json returns empty config, malformed JSON returns empty config, token placeholder substituted in headers, token placeholder substituted in env, static entries unchanged, reload_if_changed detects new version, reload no-op on same version, reload failure retains previous config
- [ ] 4.2 Create `claude-agent-app/app/core/skills.py` with `SkillsConfig` dataclass holding loaded skill markdown strings and raw MCP server config dict (GREEN)
- [ ] 4.3 Implement `load_config_from_volume(volume_path: str) -> SkillsConfig` that reads `{volume_path}/latest.json`, resolves the versioned artifact path, reads all `**/SKILL.md` files, reads `.mcp.json`, and returns a `SkillsConfig` (GREEN)
- [ ] 4.4 Implement `substitute_token(mcp_config: dict, access_token: str) -> dict` that replaces `${ACCESS_TOKEN}` placeholders in MCP server `headers` and `env` values with the provided token (GREEN)
- [ ] 4.5 Implement hot-reload: expose a module-level `current_config: SkillsConfig` and a `reload_if_changed()` function that compares the `version` in `latest.json` to the loaded version and reloads only when changed (GREEN — run `pytest tests/unit/test_skills.py` to confirm all tests pass)

## 5. AgentPool

- [ ] 5.1 Write tests for `AgentPool` in `tests/unit/test_agent_pool.py` (RED): first message spawns agent, second call reuses same agent, TTL eviction removes stale entries, active agent not evicted within TTL, cross-user isolation, shutdown drains pool, MCP spawn failure does not persist broken agent
- [ ] 5.2 Create `claude-agent-app/app/core/agent_pool.py` with `AgentEntry` dataclass (`agent`, `last_accessed: datetime`, `user_id: str`) (GREEN)
- [ ] 5.3 Implement `AgentPool` class with `_pool: dict[str, AgentEntry]`, `_lock: asyncio.Lock`, `get_or_create(conversation_id, user_id, access_token) -> ClaudeAgent` method, and `evict(conversation_id)` method (GREEN)
- [ ] 5.4 In `get_or_create`: if entry exists, update `last_accessed` and return agent; if not, build MCP config by calling `substitute_token(current_config.mcp, access_token)`, spawn a `ClaudeAgent` with the current skills system prompt and MCP connections, store in pool (GREEN)
- [ ] 5.5 Implement `evict_stale(ttl_minutes: int)` method that iterates pool entries, closes MCP connections, and removes entries older than TTL (GREEN)
- [ ] 5.6 Implement `shutdown()` method that calls `close()` on all agents and clears the pool (GREEN — run `pytest tests/unit/test_agent_pool.py` to confirm all tests pass)

## 6. FastAPI Backend

- [ ] 6.1 Write tests for all routers in `tests/unit/test_router_conversations.py` and `tests/integration/test_stream.py` (RED): POST /api/conversations returns 201, POST without token returns 401, GET /api/conversations lists only caller's, GET messages returns 404 for non-owner, DELETE returns 204 and evicts agent, DELETE non-owned returns 404, stream emits text_delta and done events, stream returns 404 for non-owned conversation, tool call events in stream, stream persists messages on completion, partial stream cancellation persists nothing
- [ ] 6.2 Create `claude-agent-app/app/main.py` with FastAPI lifespan that: (startup) creates engine, runs `alembic upgrade head`, loads initial `SkillsConfig` from Volume, starts APScheduler jobs for agent eviction and config hot-reload, mounts `SPAStaticFiles`; (shutdown) calls `AgentPool.shutdown()` and stops scheduler (GREEN)
- [ ] 6.3 Create `claude-agent-app/app/routers/conversations.py` with `POST /api/conversations` endpoint: resolves user via `get_current_user`, inserts conversation row, returns `201` with `conversation_id` and `created_at` (GREEN)
- [ ] 6.4 Implement `GET /api/conversations` in `routers/conversations.py`: returns paginated list of caller's conversations ordered by `updated_at` desc (GREEN)
- [ ] 6.5 Implement `GET /api/conversations/{conversation_id}/messages` in `routers/conversations.py`: returns ordered message history, enforces `user_id` ownership, returns `404` for non-owned conversations (GREEN)
- [ ] 6.6 Implement `DELETE /api/conversations/{conversation_id}` in `routers/conversations.py`: enforces ownership, deletes conversation + messages (cascade), evicts agent from pool, returns `204` (GREEN)
- [ ] 6.7 Create `claude-agent-app/app/routers/stream.py` with `GET /api/conversations/{conversation_id}/stream` SSE endpoint: validates ownership, calls `AgentPool.get_or_create`, streams agent response as SSE events (`text_delta`, `tool_use`, `tool_result`, `done`), persists both messages atomically on completion, handles client disconnect cancellation (GREEN)
- [ ] 6.8 Create `claude-agent-app/app/routers/me.py` with `GET /api/me` endpoint returning `{"user_id": ..., "display_name": ...}` using `get_current_user` dependency (mirrors `usage-limits/` me endpoint) (GREEN — run `pytest tests/` to confirm all backend tests pass)

## 7. Deployment Config

- [ ] 7.1 Create `claude-agent-app/app/app.yml` following `usage-limits/app/app.yml` pattern with command `uvicorn main:app`, env vars for `PGHOST`, `PGDATABASE`, `LAKEBASE_INSTANCE`, `SKILLS_VOLUME_PATH`, `AGENT_TTL_MINUTES`, `SKILLS_RELOAD_INTERVAL_SECONDS`
- [ ] 7.2 Create `claude-agent-app/resources/app.yml` Databricks asset bundle app resource: app name `claude-agent-app`, Lakebase database resource (`claude-agent-app-db`), permissions `CAN_USE` for `users` group
- [ ] 7.3 Create `claude-agent-app/resources/lakebase.yml` defining the `claude-agent-app` Lakebase instance resource
- [ ] 7.4 Create `claude-agent-app/databricks.yml` bundle config: name `claude-agent-app`, `include: [resources/*.yml]`, `variables` for `admin_user`, `targets` for `dev` (default) and `prod`

## 8. Artifact Pipeline

- [ ] 8.1 Write shell script tests for `build-artifact.sh` using a `tmp` directory (RED): script creates versioned tarball with correct layout, exits non-zero without version argument, warns but succeeds with no SKILL.md files, writes latest.json with correct schema — document these as bash assertions in a `scripts/test-build-artifact.sh` test harness
- [ ] 8.2 Create `claude-agent-app/skills/` directory with a sample `getting-started/SKILL.md` demonstrating the expected frontmatter and content format (GREEN)
- [ ] 8.3 Create `claude-agent-app/.mcp.json` template with a `uc-mcp-proxy` Slack entry using `${ACCESS_TOKEN}` placeholder in `Authorization` header (GREEN)
- [ ] 8.4 Create `claude-agent-app/scripts/build-artifact.sh`: collects `skills/**/SKILL.md` and `.mcp.json`, bundles into `dist/<version>.tar.gz` with directory layout `<version>/skills/*/SKILL.md` + `<version>/.mcp.json`, writes `dist/latest.json` (GREEN)
- [ ] 8.5 Add upload logic to `build-artifact.sh` (or `scripts/publish-artifact.sh`): uses `databricks fs cp` to upload tarball to `{VOLUME_PATH}/artifacts/<version>/`, then overwrites `{VOLUME_PATH}/latest.json` with `{"version": ..., "path": ..., "published_at": ...}` (GREEN — run `scripts/test-build-artifact.sh` to confirm all shell tests pass)
- [ ] 8.6 Create `.github/workflows/publish-artifact.yml`: triggers on push to `main` and `workflow_dispatch` with `version` input; runs `build-artifact.sh`; uploads via publish script using `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `VOLUME_PATH` secrets; requires `test` job from CI workflow to pass

## 9. React Frontend

- [ ] 9.1 Write tests for `src/lib/api.ts` in `src/lib/api.test.ts` using msw (RED): GET /api/me returns user, GET /api/conversations returns list, POST /api/conversations returns new conversation_id, DELETE returns 204
- [ ] 9.2 Initialize Vite + React 19 + TypeScript frontend in `claude-agent-app/app/frontend/` using `pnpm create vite` or matching `usage-limits/` structure; configure TanStack Router file-based routing, TanStack Query, Tailwind CSS v4, Radix UI (GREEN)
- [ ] 9.3 Copy/adapt `auth.tsx`, `theme-provider.tsx`, `mode-toggle.tsx`, and shared Radix UI components (`button.tsx`, `card.tsx`, `input.tsx`, `separator.tsx`, `skeleton.tsx`) from `usage-limits/app/frontend/src/` (GREEN)
- [ ] 9.4 Create `src/lib/api.ts` with typed fetch wrappers for `GET /api/me`, `GET /api/conversations`, `POST /api/conversations`, `GET /api/conversations/{id}/messages`, `DELETE /api/conversations/{id}` (GREEN — run `pnpm test --run src/lib/api.test.ts` to confirm)
- [ ] 9.5 Write tests for `src/lib/stream.ts` in `src/lib/stream.test.ts` using the msw SSE ReadableStream mock pattern (RED): streamMessage calls onEvent with text_delta, streamMessage calls onEvent with done, streamMessage handles tool_use and tool_result events, streamMessage handles error event
- [ ] 9.6 Implement `src/lib/stream.ts` with `streamMessage(conversationId, message, onEvent)` that opens an `EventSource` to `GET /api/conversations/{id}/stream?message=...`, parses SSE events (`text_delta`, `tool_use`, `tool_result`, `done`, error), and calls `onEvent` callbacks (GREEN — run `pnpm test --run src/lib/stream.test.ts` to confirm)
- [ ] 9.7 Write tests for `ConversationList` component in `src/components/sidebar/ConversationList.test.tsx` (RED): renders conversation titles from mock API, highlights active conversation, clicking "New Chat" calls POST /api/conversations and navigates
- [ ] 9.8 Create `src/routes/__root.tsx` with `AuthProvider`, `ThemeProvider`, sidebar layout (conversation list on left, chat area on right), and top nav with user display name and theme toggle (GREEN)
- [ ] 9.9 Create `src/routes/index.tsx` (redirect to first conversation or empty state prompt to start a new chat) (GREEN)
- [ ] 9.10 Create `src/components/sidebar/ConversationList.tsx`: lists conversations from `GET /api/conversations`, highlights active, includes "New Chat" button that calls `POST /api/conversations` and navigates to the new conversation route (GREEN — run `pnpm test --run src/components/sidebar/ConversationList.test.tsx` to confirm)
- [ ] 9.11 Write tests for `ChatInput` component in `src/components/chat/ChatInput.test.tsx` (RED): renders textarea and send button, send button disabled during active stream, textarea clears on send, onSend callback called with message text
- [ ] 9.12 Write tests for `MessageBubble` component in `src/components/chat/MessageBubble.test.tsx` (RED): renders user message with correct styling, renders assistant message with Markdown, renders ToolCallBadge for tool_use events
- [ ] 9.13 Create `src/components/chat/MessageBubble.tsx`: renders user/assistant messages with Markdown support for assistant responses, and inline `ToolCallBadge` display for tool use events (GREEN)
- [ ] 9.14 Create `src/components/chat/ChatInput.tsx`: textarea with send button, disabled during active stream, clears on send (GREEN — run `pnpm test --run src/components/chat/` to confirm)
- [ ] 9.15 Write tests for the conversation route in `src/routes/conversations/$conversationId.test.tsx` (RED): renders message history from mock API, renders ChatInput, streaming tokens append to UI as text_delta events arrive, done event stops the stream
- [ ] 9.16 Create `src/routes/conversations/$conversationId.tsx`: fetches message history via TanStack Query, renders message list with role-based styling, includes `ChatInput` component that calls `streamMessage` and appends streaming tokens to the UI in real time (GREEN — run `pnpm test --run src/routes/conversations/` to confirm)
- [ ] 9.17 Run `vite build` and verify compiled output lands in `app/frontend/dist/` (served by `SPAStaticFiles` in `main.py`)

## 10. Integration and Documentation

- [ ] 10.1 Write integration test for Alembic schema: verify `alembic upgrade head` creates correct tables on a test PostgreSQL instance (if not already covered by task 3.1 — verify and extend as needed)
- [ ] 10.2 Write integration test for the full SSE stream: mock Claude Agent SDK, verify SSE events are emitted in the correct order and user + assistant messages are persisted to the database after stream completes
- [ ] 10.3 Run the full test suite: `pytest tests/` and `pnpm test --run` — all tests must be green before marking this group done
- [ ] 10.4 Add `claude-agent-app/references/` docs: `agent-sdk-setup.md` (Agent SDK install and config), `mcp-proxy-setup.md` (uc-mcp-proxy endpoint and auth), `volume-setup.md` (Unity Catalog Volume path convention)
- [ ] 10.5 Update repo root `README.md` to list `claude-agent-app/` alongside `usage-limits/` with a brief description and link to its references
