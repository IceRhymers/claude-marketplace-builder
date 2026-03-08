## Why

Users currently have no control over which pre-installed MCP servers are active in their agent sessions — all servers from the marketplace artifact are always enabled. This mirrors the same gap that `user_skill_prefs` solved for skills: different users want different integrations (e.g., one user wants Slack but not GitHub; another wants neither).

## What Changes

- Add `UserMcpPref` database model with composite PK `(user_id, mcp_name)` and an `enabled` flag
- Add Alembic migration for the new table
- Add `get_user_mcp_prefs()` dependency that resolves which MCP servers are enabled for the requesting user (defaulting to all enabled when no explicit preference exists)
- Add `GET /api/preferences/mcp` endpoint listing all available MCP servers with their enabled state per user
- Add `PATCH /api/preferences/mcp/{mcp_name}` endpoint to toggle a single server on or off
- Filter `build_agent` to pass only the user's enabled MCP servers into `ClaudeAgentOptions` (instead of the full `mcp_config`)

## Capabilities

### New Capabilities
- `user-mcp-prefs`: Per-user enable/disable of pre-installed MCP servers; persistence in Lakebase; REST API for reading and mutating preferences; agent build integration to filter active MCP connections

### Modified Capabilities
- `agent-sdk-integration`: `build_agent` now receives the filtered MCP config (enabled servers only) rather than the full `mcp_config` blob from `SkillsConfig`

## Impact

- **New table**: `user_mcp_prefs (user_id, mcp_name, enabled, updated_at)`
- **New router**: `routers/preferences_mcp.py` (or extend existing `routers/preferences.py`)
- **Modified**: `core/agent_pool.py` — `get_or_create` resolves MCP prefs before calling `build_agent`
- **Modified**: `deps.py` — adds `get_user_mcp_prefs()`
- **Modified**: `core/models.py` — adds `UserMcpPref` model
- **New migration**: `alembic/versions/002_add_user_mcp_prefs.py`
- **No frontend changes required** — preference endpoints consumed by same settings UI pattern used for skill prefs
