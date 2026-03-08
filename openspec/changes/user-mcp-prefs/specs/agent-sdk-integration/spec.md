## MODIFIED Requirements

### Requirement: AgentPool.get_or_create resolves MCP preferences before building agent
`get_or_create` SHALL resolve the user's enabled MCP server names from `user_mcp_prefs` (via `get_user_mcp_prefs`) and filter `mcp_config` to only include enabled servers before passing it to `build_agent`. The ordering in `get_or_create` SHALL be:
1. Volume file restore
2. Skill prefs lookup
3. **MCP prefs lookup** ← new step
4. History hydration
5. `build_agent(session_dir, filtered_mcp_config, enabled_skills, skills_config)`

When `db` is `None`, all MCP servers SHALL be treated as enabled (no filtering).

#### Scenario: Enabled servers only reach build_agent
- **WHEN** `get_or_create` is called for a user with `"slack"` disabled in `user_mcp_prefs`
- **THEN** `build_agent` is called with an `mcp_config` that does NOT contain a `"slack"` key under `mcpServers`

#### Scenario: All servers when no pref rows
- **WHEN** `get_or_create` is called for a user with no `user_mcp_prefs` rows
- **THEN** `build_agent` is called with the full (token-substituted) `mcp_config`

#### Scenario: All servers when db is None
- **WHEN** `get_or_create` is called with `db=None`
- **THEN** `build_agent` is called with the full (token-substituted) `mcp_config`

#### Scenario: MCP prefs lookup failure raises RuntimeError
- **WHEN** `get_user_mcp_prefs` raises an exception inside `get_or_create`
- **THEN** `get_or_create` raises `RuntimeError` with a descriptive message
