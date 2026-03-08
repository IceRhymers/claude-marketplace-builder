## ADDED Requirements

### Requirement: UserMcpPref model
The system SHALL persist per-user MCP server preferences in a `user_mcp_prefs` table with composite primary key `(user_id, mcp_name)`, an `enabled` boolean, and an `updated_at` timestamp.

#### Scenario: Model maps to correct table
- **WHEN** `UserMcpPref.__tablename__` is inspected
- **THEN** it equals `"user_mcp_prefs"`

#### Scenario: Composite PK on user_id and mcp_name
- **WHEN** a `UserMcpPref` row is inserted with a duplicate `(user_id, mcp_name)` pair
- **THEN** the database raises an integrity error

#### Scenario: Default enabled is True
- **WHEN** a `UserMcpPref` is created without specifying `enabled`
- **THEN** `enabled` is `True`

---

### Requirement: Alembic migration for user_mcp_prefs
The system SHALL include a migration file that creates the `user_mcp_prefs` table with columns `user_id VARCHAR(255)`, `mcp_name VARCHAR(255)`, `enabled BOOLEAN NOT NULL`, `updated_at DATETIME`.

#### Scenario: Migration creates table
- **WHEN** the migration is applied to a fresh database
- **THEN** `user_mcp_prefs` table exists with the correct schema

---

### Requirement: get_user_mcp_prefs dependency
The system SHALL expose a `get_user_mcp_prefs(user_id, db, mcp_config)` function in `deps.py` that returns the set of MCP server names enabled for the user.

#### Scenario: All enabled by default (no pref rows)
- **WHEN** `get_user_mcp_prefs` is called for a user with no rows in `user_mcp_prefs`
- **THEN** it returns all server names present in `mcp_config["mcpServers"]`

#### Scenario: Disabled server excluded
- **WHEN** a user has `enabled=False` for `"slack"` in `user_mcp_prefs`
- **THEN** `get_user_mcp_prefs` does not include `"slack"` in the returned set

#### Scenario: Stale pref rows ignored
- **WHEN** a user has a pref row for `"old-server"` that no longer exists in `mcp_config["mcpServers"]`
- **THEN** `get_user_mcp_prefs` does not include `"old-server"` in the returned set

#### Scenario: Empty mcp_config returns empty set
- **WHEN** `mcp_config` is `{"mcpServers": {}}` or `{}`
- **THEN** `get_user_mcp_prefs` returns an empty set

---

### Requirement: GET /api/preferences/mcp endpoint
The system SHALL expose `GET /api/preferences/mcp` returning a list of all available MCP servers with the authenticated user's `enabled` state. Servers without a pref row SHALL default to `enabled: true`.

#### Scenario: Returns all servers with enabled state
- **WHEN** `GET /api/preferences/mcp` is called by an authenticated user
- **THEN** the response is a JSON array of `{name, enabled}` objects, one per server in `mcp_config["mcpServers"]`

#### Scenario: No pref rows → all enabled
- **WHEN** the user has no rows in `user_mcp_prefs`
- **THEN** every object in the response has `"enabled": true`

#### Scenario: Disabled server reflected in response
- **WHEN** the user has `enabled=False` for `"slack"`
- **THEN** the response contains `{"name": "slack", "enabled": false}`

#### Scenario: Empty server list → empty array
- **WHEN** `mcp_config["mcpServers"]` is empty
- **THEN** the response is `[]`

---

### Requirement: PATCH /api/preferences/mcp/{mcp_name} endpoint
The system SHALL expose `PATCH /api/preferences/mcp/{mcp_name}` accepting `{"enabled": bool}` to upsert a per-user MCP preference. It SHALL return the updated `{name, enabled}` object. It SHALL return 404 if `mcp_name` is not in the current `mcp_config["mcpServers"]`.

#### Scenario: Disable a server (new row)
- **WHEN** `PATCH /api/preferences/mcp/slack` is called with `{"enabled": false}` and no existing row
- **THEN** a new `UserMcpPref` row is created and the response is `{"name": "slack", "enabled": false}`

#### Scenario: Re-enable a server (update existing row)
- **WHEN** `PATCH /api/preferences/mcp/slack` is called with `{"enabled": true}` and an existing `enabled=False` row
- **THEN** the row is updated and the response is `{"name": "slack", "enabled": true}`

#### Scenario: Unknown server returns 404
- **WHEN** `PATCH /api/preferences/mcp/unknown-server` is called
- **THEN** the response is HTTP 404
