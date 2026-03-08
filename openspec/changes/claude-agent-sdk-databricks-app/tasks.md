## 1. Project Scaffold

- [ ] 1.1 Create `claude-agent-app/` directory structure mirroring `usage-limits/`: `app/`, `app/core/`, `app/frontend/`, `resources/`, `scripts/`, `references/`
- [ ] 1.2 Create `claude-agent-app/app/pyproject.toml` with Python dependencies: `fastapi`, `uvicorn[standard]`, `sse-starlette`, `sqlalchemy[asyncio]`, `psycopg[binary]`, `alembic`, `apscheduler`, `anthropic[agent-sdk]`, `databricks-sdk`
- [ ] 1.3 Create `claude-agent-app/app/.python-version` pinned to match `usage-limits/`
- [ ] 1.4 Create `claude-agent-app/app/frontend/package.json` with same React 19 + Vite + TanStack + Radix + Tailwind stack as `usage-limits/`
- [ ] 1.5 Create `claude-agent-app/Makefile` with `dev`, `build`, `test`, `deploy` targets mirroring `usage-limits/Makefile`

## 2. User Identity Dependency

- [ ] 2.1 Create `claude-agent-app/app/core/auth.py` with `CurrentUser` dataclass (`user_id: str`, `access_token: str`)
- [ ] 2.2 Implement `get_current_user` FastAPI dependency in `core/auth.py` that reads `X-Forwarded-Access-Token`, calls `WorkspaceClient.current_user.me()`, and returns `CurrentUser`; raises `HTTPException(401)` on missing or invalid token
- [ ] 2.3 Write unit tests for `get_current_user` covering valid token, missing token, and invalid token cases

## 3. Database Layer

- [ ] 3.1 Create `claude-agent-app/app/core/db.py` with `create_engine_from_config` using the same Lakebase OAuth token injection pattern as `usage-limits/app/core/db.py`
- [ ] 3.2 Create `claude-agent-app/app/core/models.py` with `Conversation` SQLAlchemy model (`id` UUID PK, `user_id`, `title`, `created_at`, `updated_at`) and `Message` model (`id` UUID PK, `conversation_id` FK → conversations cascade delete, `user_id`, `role` constrained to `user`/`assistant`, `content`, `created_at`)
- [ ] 3.3 Initialize Alembic in `claude-agent-app/app/alembic/`: `alembic init`, configure `env.py` to use the app's SQLAlchemy engine and `Base.metadata`
- [ ] 3.4 Generate and review initial Alembic migration creating `conversations` and `messages` tables with all columns, constraints, and an index on `(conversations.user_id)` and `(messages.conversation_id)`
- [ ] 3.5 Create `claude-agent-app/app/core/config.py` with `AppConfig` dataclass reading `PGHOST`, `PGDATABASE`, `LAKEBASE_INSTANCE`, `SKILLS_VOLUME_PATH`, `AGENT_TTL_MINUTES` (default 30), `SKILLS_RELOAD_INTERVAL_SECONDS` (default 60) from env
- [ ] 3.6 Create `claude-agent-app/app/deps.py` with `get_db` dependency yielding a SQLAlchemy `Session`

## 4. MCP and Skills Config Loader

- [ ] 4.1 Create `claude-agent-app/app/core/skills.py` with `SkillsConfig` dataclass holding loaded skill markdown strings and raw MCP server config dict
- [ ] 4.2 Implement `load_config_from_volume(volume_path: str) -> SkillsConfig` that reads `{volume_path}/latest.json`, resolves the versioned artifact path, reads all `**/SKILL.md` files, reads `.mcp.json`, and returns a `SkillsConfig`
- [ ] 4.3 Implement `substitute_token(mcp_config: dict, access_token: str) -> dict` that replaces `${ACCESS_TOKEN}` placeholders in MCP server `headers` and `env` values with the provided token
- [ ] 4.4 Implement hot-reload: expose a module-level `current_config: SkillsConfig` and a `reload_if_changed()` function that compares the `version` in `latest.json` to the loaded version and reloads only when changed
- [ ] 4.5 Write unit tests for `load_config_from_volume` covering valid config, missing `latest.json`, and malformed JSON

## 5. AgentPool

- [ ] 5.1 Create `claude-agent-app/app/core/agent_pool.py` with `AgentEntry` dataclass (`agent`, `last_accessed: datetime`, `user_id: str`)
- [ ] 5.2 Implement `AgentPool` class with `_pool: dict[str, AgentEntry]`, `_lock: asyncio.Lock`, `get_or_create(conversation_id, user_id, access_token) -> ClaudeAgent` method, and `evict(conversation_id)` method
- [ ] 5.3 In `get_or_create`: if entry exists, update `last_accessed` and return agent; if not, build MCP config by calling `substitute_token(current_config.mcp, access_token)`, spawn a `ClaudeAgent` with the current skills system prompt and MCP connections, store in pool
- [ ] 5.4 Implement `evict_stale(ttl_minutes: int)` method that iterates pool entries, closes MCP connections, and removes entries older than TTL
- [ ] 5.5 Implement `shutdown()` method that calls `close()` on all agents and clears the pool
- [ ] 5.6 Write unit tests for AgentPool covering: first-message spawn, subsequent-message reuse, TTL eviction, cross-user isolation, shutdown drain

## 6. FastAPI Backend

- [ ] 6.1 Create `claude-agent-app/app/main.py` with FastAPI lifespan that: (startup) creates engine, runs `alembic upgrade head`, loads initial `SkillsConfig` from Volume, starts APScheduler jobs for agent eviction and config hot-reload, mounts `SPAStaticFiles`; (shutdown) calls `AgentPool.shutdown()` and stops scheduler
- [ ] 6.2 Create `claude-agent-app/app/routers/conversations.py` with `POST /api/conversations` endpoint: resolves user via `get_current_user`, inserts conversation row, returns `201` with `conversation_id` and `created_at`
- [ ] 6.3 Implement `GET /api/conversations` in `routers/conversations.py`: returns paginated list of caller's conversations ordered by `updated_at` desc
- [ ] 6.4 Implement `GET /api/conversations/{conversation_id}/messages` in `routers/conversations.py`: returns ordered message history, enforces `user_id` ownership, returns `404` for non-owned conversations
- [ ] 6.5 Implement `DELETE /api/conversations/{conversation_id}` in `routers/conversations.py`: enforces ownership, deletes conversation + messages (cascade), evicts agent from pool, returns `204`
- [ ] 6.6 Create `claude-agent-app/app/routers/stream.py` with `GET /api/conversations/{conversation_id}/stream` SSE endpoint: validates ownership, calls `AgentPool.get_or_create`, streams agent response as SSE events (`text_delta`, `tool_use`, `tool_result`, `done`), persists both messages atomically on completion, handles client disconnect cancellation
- [ ] 6.7 Create `claude-agent-app/app/routers/me.py` with `GET /api/me` endpoint returning `{"user_id": ..., "display_name": ...}` using `get_current_user` dependency (mirrors `usage-limits/` me endpoint)
- [ ] 6.8 Write unit tests for all routers covering happy paths, auth failures, ownership enforcement, and SSE event format

## 7. Deployment Config

- [ ] 7.1 Create `claude-agent-app/app/app.yml` following `usage-limits/app/app.yml` pattern with command `uvicorn main:app`, env vars for `PGHOST`, `PGDATABASE`, `LAKEBASE_INSTANCE`, `SKILLS_VOLUME_PATH`, `AGENT_TTL_MINUTES`, `SKILLS_RELOAD_INTERVAL_SECONDS`
- [ ] 7.2 Create `claude-agent-app/resources/app.yml` Databricks asset bundle app resource: app name `claude-agent-app`, Lakebase database resource (`claude-agent-app-db`), permissions `CAN_USE` for `users` group
- [ ] 7.3 Create `claude-agent-app/resources/lakebase.yml` defining the `claude-agent-app` Lakebase instance resource
- [ ] 7.4 Create `claude-agent-app/databricks.yml` bundle config: name `claude-agent-app`, `include: [resources/*.yml]`, `variables` for `admin_user`, `targets` for `dev` (default) and `prod`

## 8. Artifact Pipeline

- [ ] 8.1 Create `claude-agent-app/skills/` directory with a sample `getting-started/SKILL.md` demonstrating the expected frontmatter and content format
- [ ] 8.2 Create `claude-agent-app/.mcp.json` template with a `uc-mcp-proxy` Slack entry using `${ACCESS_TOKEN}` placeholder in `Authorization` header
- [ ] 8.3 Create `claude-agent-app/scripts/build-artifact.sh`: collects `skills/**/SKILL.md` and `.mcp.json`, bundles into `dist/<version>.tar.gz` with directory layout `<version>/skills/*/SKILL.md` + `<version>/.mcp.json`, writes `dist/latest.json`
- [ ] 8.4 Add upload logic to `build-artifact.sh` (or `scripts/publish-artifact.sh`): uses `databricks fs cp` to upload tarball to `{VOLUME_PATH}/artifacts/<version>/`, then overwrites `{VOLUME_PATH}/latest.json` with `{"version": ..., "path": ..., "published_at": ...}`
- [ ] 8.5 Create `.github/workflows/publish-artifact.yml`: triggers on push to `main` and `workflow_dispatch` with `version` input; runs `build-artifact.sh`; uploads via publish script using `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `VOLUME_PATH` secrets

## 9. React Frontend

- [ ] 9.1 Initialize Vite + React 19 + TypeScript frontend in `claude-agent-app/app/frontend/` using `pnpm create vite` or matching `usage-limits/` structure; configure TanStack Router file-based routing, TanStack Query, Tailwind CSS v4, Radix UI
- [ ] 9.2 Copy/adapt `auth.tsx`, `theme-provider.tsx`, `mode-toggle.tsx`, and shared Radix UI components (`button.tsx`, `card.tsx`, `input.tsx`, `separator.tsx`, `skeleton.tsx`) from `usage-limits/app/frontend/src/`
- [ ] 9.3 Create `src/lib/api.ts` with typed fetch wrappers for `GET /api/me`, `GET /api/conversations`, `POST /api/conversations`, `GET /api/conversations/{id}/messages`, `DELETE /api/conversations/{id}`
- [ ] 9.4 Implement `src/lib/stream.ts` with `streamMessage(conversationId, message, onEvent)` that opens an `EventSource` to `GET /api/conversations/{id}/stream?message=...`, parses SSE events (`text_delta`, `tool_use`, `tool_result`, `done`, error), and calls `onEvent` callbacks
- [ ] 9.5 Create `src/routes/__root.tsx` with `AuthProvider`, `ThemeProvider`, sidebar layout (conversation list on left, chat area on right), and top nav with user display name and theme toggle
- [ ] 9.6 Create `src/routes/index.tsx` (redirect to first conversation or empty state prompt to start a new chat)
- [ ] 9.7 Create `src/routes/conversations/$conversationId.tsx`: fetches message history via TanStack Query, renders message list with role-based styling, includes `ChatInput` component that calls `streamMessage` and appends streaming tokens to the UI in real time
- [ ] 9.8 Create `src/components/chat/MessageBubble.tsx`: renders user/assistant messages with Markdown support for assistant responses, and inline `ToolCallBadge` display for tool use events
- [ ] 9.9 Create `src/components/chat/ChatInput.tsx`: textarea with send button, disabled during active stream, clears on send
- [ ] 9.10 Create `src/components/sidebar/ConversationList.tsx`: lists conversations from `GET /api/conversations`, highlights active, includes "New Chat" button that calls `POST /api/conversations` and navigates to the new conversation route
- [ ] 9.11 Run `vite build` and verify compiled output lands in `app/frontend/dist/` (served by `SPAStaticFiles` in `main.py`)

## 10. Testing and Documentation

- [ ] 10.1 Write integration tests for Lakebase schema: verify `alembic upgrade head` creates correct tables on a test PostgreSQL instance
- [ ] 10.2 Write integration test for the full SSE stream: mock Claude Agent SDK, verify SSE events are emitted and messages are persisted
- [ ] 10.3 Add `claude-agent-app/references/` docs: `agent-sdk-setup.md` (Agent SDK install and config), `mcp-proxy-setup.md` (uc-mcp-proxy endpoint and auth), `volume-setup.md` (Unity Catalog Volume path convention)
- [ ] 10.4 Update repo root `README.md` to list `claude-agent-app/` alongside `usage-limits/` with a brief description and link to its references
