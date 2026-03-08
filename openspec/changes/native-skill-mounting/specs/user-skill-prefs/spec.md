## ADDED Requirements

### Capability: `user-skill-prefs` — per-user skill enable/disable

#### Requirement: user_skill_prefs Lakebase table

The system SHALL maintain a `user_skill_prefs` table in the Lakebase Postgres instance that records each user's explicit enable/disable choices for individual skills.

```sql
CREATE TABLE user_skill_prefs (
    user_id     VARCHAR(255) NOT NULL,
    skill_name  VARCHAR(255) NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT true,
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, skill_name)
);
```

Skills with no row in this table default to `enabled=true` (see D3 in design.md).

##### Scenario: Table created by Alembic migration
- **WHEN** `alembic upgrade head` is run against a database that does not yet have `user_skill_prefs`
- **THEN** the `user_skill_prefs` table is created with the schema above
- **AND** the migration is idempotent (running again does not error)

##### Scenario: Primary key enforces one row per (user_id, skill_name)
- **WHEN** two rows with the same `(user_id, skill_name)` are inserted
- **THEN** the second insert raises a primary key violation
- **AND** an upsert (`INSERT ... ON CONFLICT DO UPDATE`) succeeds and updates the existing row

#### Requirement: GET /api/preferences/skills — list skills with user preference state

The system SHALL provide a `GET /api/preferences/skills` endpoint that returns every skill in the current `SkillsConfig.skills` merged with the authenticated user's preference rows. Skills absent from `user_skill_prefs` default to `enabled=true`.

##### Scenario: Response merges SkillsConfig with user preference rows
- **WHEN** `GET /api/preferences/skills` is called by `user_id=alice`
- **AND** `SkillsConfig.skills` contains `databricks-lineage` (has_scripts=true) and `slack-summary` (has_scripts=false)
- **AND** `user_skill_prefs` has a row `(alice, databricks-lineage, false)`
- **THEN** the response body is:
  ```json
  [
    {"name": "databricks-lineage", "enabled": false, "has_scripts": true, "has_references": false},
    {"name": "slack-summary",      "enabled": true,  "has_scripts": false, "has_references": false}
  ]
  ```
- **AND** the HTTP status is `200`

##### Scenario: No preference rows exist — all skills default to enabled=true
- **WHEN** `GET /api/preferences/skills` is called by a user with no rows in `user_skill_prefs`
- **THEN** every skill in `SkillsConfig.skills` is returned with `"enabled": true`

##### Scenario: Empty skills config returns empty list
- **WHEN** `SkillsConfig.skills` is empty
- **THEN** `GET /api/preferences/skills` returns `200` with body `[]`

##### Scenario: Endpoint requires authentication
- **WHEN** `GET /api/preferences/skills` is called without a valid `X-Forwarded-Access-Token`
- **THEN** the response is `401 Unauthorized`

#### Requirement: PATCH /api/preferences/skills/{skill_name} — update user preference

The system SHALL provide a `PATCH /api/preferences/skills/{skill_name}` endpoint that upserts a `user_skill_prefs` row for the authenticated user and named skill.

Request body:
```json
{"enabled": false}
```

Response (200):
```json
{"name": "databricks-lineage", "enabled": false, "has_scripts": true, "has_references": false}
```

##### Scenario: PATCH upserts new preference row
- **WHEN** `PATCH /api/preferences/skills/databricks-lineage` is called with `{"enabled": false}` by `user_id=alice`
- **AND** no row yet exists for `(alice, databricks-lineage)`
- **THEN** a new row is inserted with `enabled=false`
- **AND** the response is `200` with the updated preference object

##### Scenario: PATCH updates existing preference row
- **WHEN** `PATCH /api/preferences/skills/databricks-lineage` is called with `{"enabled": true}`
- **AND** a row already exists for `(alice, databricks-lineage)` with `enabled=false`
- **THEN** the row is updated to `enabled=true`
- **AND** `updated_at` is refreshed to the current timestamp

##### Scenario: PATCH returns 404 for unknown skill name
- **WHEN** `PATCH /api/preferences/skills/nonexistent-skill` is called
- **AND** `nonexistent-skill` is NOT in `SkillsConfig.skills`
- **THEN** the response is `404 Not Found` with `{"detail": "Skill not found: nonexistent-skill"}`
- **AND** no row is inserted or updated in `user_skill_prefs`

##### Scenario: Two users have independent preferences
- **WHEN** `alice` disables `databricks-lineage` via PATCH
- **AND** `bob` has no preference row for `databricks-lineage`
- **THEN** `GET /api/preferences/skills` for `alice` returns `databricks-lineage` with `enabled=false`
- **AND** `GET /api/preferences/skills` for `bob` returns `databricks-lineage` with `enabled=true`

##### Scenario: PATCH requires authentication
- **WHEN** `PATCH /api/preferences/skills/databricks-lineage` is called without a valid token
- **THEN** the response is `401 Unauthorized`

#### Requirement: get_user_skill_prefs dependency returns the set of enabled skill names

A new FastAPI dependency `get_user_skill_prefs(user_id: str, db: Session, skills_config: SkillsConfig) -> set[str]` SHALL return the set of skill names that are enabled for the given user. This dependency is consumed by `AgentPool.get_or_create` (via the streaming endpoint) to determine which skills to copy into the session sandbox.

Implementation:
- Query `user_skill_prefs` for all rows where `user_id = user_id`
- Build a dict `{skill_name: enabled}` from the rows
- For each skill name in `skills_config.skills`: include it in the result set if `prefs.get(skill_name, True)` is `True`
- Return `set[str]` of enabled skill names

##### Scenario: Mix of explicit prefs and defaults
- **WHEN** `skills_config.skills` contains `skill-a`, `skill-b`, `skill-c`
- **AND** `user_skill_prefs` has rows: `(alice, skill-a, false)`, `(alice, skill-c, true)`
- **THEN** `get_user_skill_prefs("alice", db, skills_config)` returns `{"skill-b", "skill-c"}`
  (skill-a disabled explicitly, skill-b default-enabled, skill-c explicitly enabled)

##### Scenario: No preference rows — all skills enabled
- **WHEN** `user_skill_prefs` has no rows for a user
- **THEN** `get_user_skill_prefs` returns the full set of skill names from `skills_config.skills`

##### Scenario: Skill removed from config but preference row remains
- **WHEN** `user_skill_prefs` has a row for `old-skill` that no longer exists in `skills_config.skills`
- **THEN** `old-skill` is NOT included in the returned set
- **AND** no error is raised

## Test Requirements

Tests MUST be written BEFORE implementation (RED phase):
- Unit tests for the dependency in `tests/unit/test_prefs.py`
- Integration tests for the endpoints in `tests/integration/test_prefs.py`

Required test scenarios:

- `GET /api/preferences/skills` returns all skills with `enabled=true` when no pref rows exist
- `GET /api/preferences/skills` returns `enabled=false` for a skill with explicit `false` row
- `GET /api/preferences/skills` with empty `SkillsConfig.skills` → `200 []`
- `GET /api/preferences/skills` without token → `401`
- `PATCH /api/preferences/skills/databricks-lineage` with `{"enabled": false}` → `200`, row inserted, response body includes `has_scripts`/`has_references` from `SkillsConfig`
- `PATCH /api/preferences/skills/databricks-lineage` called twice → row updated (not duplicated), `updated_at` refreshed
- `PATCH /api/preferences/skills/nonexistent` → `404` with detail message; no DB write
- `PATCH /api/preferences/skills/databricks-lineage` without token → `401`
- Two users (`alice`, `bob`): alice disables skill, bob's preferences unaffected
- `get_user_skill_prefs` with mix of explicit prefs and defaults → correct set returned
- `get_user_skill_prefs` with no pref rows → full skill name set returned
- `get_user_skill_prefs` with orphaned pref row for removed skill → removed skill not in result set

Fixture additions required in `tests/conftest.py`:
- `mock_user_skill_prefs`: returns a mock `set[str]` of enabled skill names (e.g., `{"skill-a", "skill-b"}`) for use in `agent_pool` and stream endpoint tests that need `get_user_skill_prefs`
