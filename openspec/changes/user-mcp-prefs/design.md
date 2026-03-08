## Context

The app already has a `user_skill_prefs` pattern: a `UserSkillPref` DB table + `get_user_skill_prefs()` dep + REST endpoints + `build_agent` integration. MCP server preferences follow exactly the same pattern with one structural difference: MCP config is a nested dict (`{"mcpServers": {"server-name": {...}}}`) rather than a flat list.

`SkillsConfig.mcp_config` holds the full MCP configuration blob from the manifest. `build_agent` currently receives `mcp_config` (already token-substituted) and passes it through to `ClaudeAgentOptions` wholesale. We need to filter that blob to only include servers the user has enabled before handing it to `build_agent`.

## Goals / Non-Goals

**Goals:**
- Per-user MCP server enable/disable, defaulting to all enabled
- Persistence in Lakebase via `user_mcp_prefs` table
- `GET /api/preferences/mcp` — list all available servers with enabled state
- `PATCH /api/preferences/mcp/{mcp_name}` — toggle a single server
- `build_agent` receives only the filtered `mcp_config` (no wholesale changes to its signature)
- TDD throughout: RED test before each GREEN implementation

**Non-Goals:**
- Adding new MCP servers (catalog is fixed by the marketplace artifact)
- Custom MCP server configuration (URLs, credentials) — enable/disable only
- Frontend UI (endpoints are consumed by the same settings UI pattern as skill prefs)
- Cross-user visibility of preferences

## Decisions

### D1: Extend `preferences.py` rather than a new file
The existing `routers/preferences.py` already handles `/api/preferences/skills`. Adding `/api/preferences/mcp` routes to the same file keeps the router cohesive and avoids an extra registration in `main.py`. If the file grows unwieldy this can be split later.

**Alternatives considered**: New `routers/preferences_mcp.py` — rejected because it adds router registration complexity for only 2 new endpoints.

### D2: Filter in `get_or_create`, not inside `build_agent`
`build_agent` already accepts `mcp_config: dict`. Filtering in `get_or_create` (same place skill prefs are resolved) keeps `build_agent` a pure "construct from given config" function. No signature changes needed.

**Alternatives considered**: Pass `enabled_mcp_names` into `build_agent` and filter there — rejected because `build_agent` would then need to know the structure of the mcp dict, coupling it to config format.

### D3: Default to all enabled (opt-out model)
New users and users with no pref rows see all MCP servers. Only explicit `enabled=False` rows are respected. Mirrors the skill prefs model exactly.

### D4: MCP server names keyed by `mcpServers` dict keys
The `mcp_config` dict is `{"mcpServers": {"slack": {...}, "github": {...}}}`. The keys are the canonical server names used as `mcp_name` in the DB and URLs. No additional name mapping needed.

## Risks / Trade-offs

- [Risk: MCP server removed from manifest but pref row still exists] → Non-issue: `get_user_mcp_prefs` ignores pref rows for names not in `mcp_config["mcpServers"]`, same as skill prefs ignores rows for removed skills.
- [Risk: `mcp_config` is None or missing `mcpServers` key] → `get_user_mcp_prefs` treats this as an empty server list; `build_agent` receives empty `{"mcpServers": {}}` — no crash.
- [Risk: Session in pool before user changes a pref] → Same as skills: pref changes only take effect on next `get_or_create` (eviction or new session). Acceptable for MVP.

## Migration Plan

1. Add `UserMcpPref` to `models.py`
2. Create Alembic migration `002_add_user_mcp_prefs.py`
3. Add `get_user_mcp_prefs()` to `deps.py`
4. Extend `routers/preferences.py` with 2 new endpoints
5. Update `get_or_create` in `agent_pool.py` to resolve and pass filtered MCP config
6. All steps are additive — zero breaking changes; rollback is dropping the table and reverting `get_or_create`
