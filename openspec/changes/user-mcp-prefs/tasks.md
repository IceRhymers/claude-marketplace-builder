## 0. Test Infrastructure

- [x] 0.1 (RED) Add `mock_mcp_config` fixture to `tests/conftest.py` — dict with 2 servers (`slack`, `github`) matching `{"mcpServers": {"slack": {...}, "github": {...}}}`
- [x] 0.2 (RED) Add `mock_user_mcp_prefs` fixture to `tests/conftest.py` — returns `{"slack", "github"}` by default
- [x] 0.3 (RED) Verify fixtures fail to import (since `UserMcpPref` doesn't exist yet)

## 1. Model & Migration

- [x] 1.1 (RED) Write `tests/unit/test_models.py::test_user_mcp_pref_*` — table name, composite PK, default enabled
- [x] 1.2 (GREEN) Add `UserMcpPref` to `core/models.py` — `user_id VARCHAR(255) PK`, `mcp_name VARCHAR(255) PK`, `enabled BOOLEAN NOT NULL DEFAULT TRUE`, `updated_at DATETIME`
- [x] 1.3 (RED) Write `tests/unit/test_migration_mcp.py` — assert migration SQL creates `user_mcp_prefs` table
- [x] 1.4 (GREEN) Create `alembic/versions/002_add_user_mcp_prefs.py` migration

## 2. get_user_mcp_prefs Dependency

- [x] 2.1 (RED) Write `tests/unit/test_deps.py::test_get_user_mcp_prefs_*` covering all 4 scenarios: all-enabled default, disabled excluded, stale rows ignored, empty mcp_config
- [x] 2.2 (GREEN) Add `get_user_mcp_prefs(user_id, db, mcp_config) -> set[str]` to `deps.py`

## 3. Preferences API

- [x] 3.1 (RED) Write `tests/unit/test_preferences_mcp.py::test_get_mcp_prefs_*` — all servers listed, all enabled by default, disabled reflected, empty list
- [x] 3.2 (RED) Write `tests/unit/test_preferences_mcp.py::test_patch_mcp_pref_*` — disable new row, re-enable existing row, 404 for unknown server
- [x] 3.3 (GREEN) Add `GET /api/preferences/mcp` endpoint to `routers/preferences.py`
- [x] 3.4 (GREEN) Add `PATCH /api/preferences/mcp/{mcp_name}` endpoint to `routers/preferences.py`
- [x] 3.5 (GREEN) Register new routes in `main.py` (include prefix, verify no conflicts)

## 4. AgentPool MCP Filtering

- [x] 4.1 (RED) Write `tests/unit/test_agent_pool.py::test_get_or_create_mcp_filtering_*` — enabled servers only in build_agent call, all servers when no prefs, all servers when db=None, RuntimeError on prefs failure
- [x] 4.2 (GREEN) Update `AgentPool.get_or_create` in `core/agent_pool.py` to call `get_user_mcp_prefs` and build `filtered_mcp_config` before calling `build_agent`

## 5. Full Suite Green Gate

- [x] 5.1 Run `pytest claude-agent-app/app/tests/ -x` — all tests pass, zero regressions
- [x] 5.2 Confirm zero references to unfiltered `mcp_config` reaching `build_agent` when user has disabled servers
- [x] 5.3 Update `openspec/changes/user-mcp-prefs/tasks.md` to mark all tasks complete
- [x] 5.4 Commit and push to `feat/claude-agent-app-wt`
