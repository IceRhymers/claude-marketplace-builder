## ADDED Requirements

### Requirement: Test coverage for skills and MCP config loader
The system SHALL have `tests/unit/test_skills.py` covering all `SkillsConfig` and `load_config_from_volume` scenarios before `core/skills.py` is implemented.

## Test Requirements

The following test scenarios MUST be implemented in `tests/unit/test_skills.py` before `core/skills.py` is written. All tests mock filesystem/Volume reads using `unittest.mock.patch` or `tmp_path` fixtures.

#### Scenario: load_config_from_volume reads latest.json and resolves artifact path
- **WHEN** `load_config_from_volume("/vol/skills")` is called and a mock filesystem contains `latest.json = {"version": "v1.0.0", "path": "artifacts/v1.0.0"}` plus one `SKILL.md` file and a `.mcp.json`
- **THEN** the returned `SkillsConfig` has `version = "v1.0.0"`, `skill_contents` containing the SKILL.md text, and `mcp_config` matching the parsed `.mcp.json` dict

#### Scenario: Missing latest.json returns empty SkillsConfig without raising
- **WHEN** `load_config_from_volume("/vol/skills")` is called and `latest.json` does not exist
- **THEN** no exception is raised and the returned `SkillsConfig` has `skill_contents = []` and `mcp_config = {}`

#### Scenario: Malformed latest.json returns empty SkillsConfig without raising
- **WHEN** `load_config_from_volume` is called and `latest.json` contains `"not valid json"`
- **THEN** no exception is raised, an error is logged, and an empty `SkillsConfig` is returned

#### Scenario: substitute_token replaces ACCESS_TOKEN placeholder in headers
- **WHEN** `substitute_token({"mcpServers": {"slack": {"headers": {"Authorization": "Bearer ${ACCESS_TOKEN}"}}}}, "my-token")` is called
- **THEN** the returned dict contains `"Authorization": "Bearer my-token"` in the Slack server headers

#### Scenario: substitute_token replaces ACCESS_TOKEN placeholder in env values
- **WHEN** the MCP config contains `"env": {"TOKEN": "${ACCESS_TOKEN}"}` and `substitute_token` is called with `access_token="abc123"`
- **THEN** the returned dict contains `"TOKEN": "abc123"` in the server env

#### Scenario: substitute_token leaves static entries unchanged
- **WHEN** the MCP config contains no `${ACCESS_TOKEN}` placeholders
- **THEN** the returned dict is equal to the input dict (no modifications)

#### Scenario: reload_if_changed detects new version and reloads
- **WHEN** the current loaded version is `"v1.0.0"` and `latest.json` now points to `"v1.1.0"`
- **THEN** `reload_if_changed()` loads the new artifact and updates the module-level `current_config` to the `v1.1.0` configuration

#### Scenario: reload_if_changed is a no-op when version unchanged
- **WHEN** the current loaded version matches `latest.json`
- **THEN** `reload_if_changed()` does not read the artifact directory (verified by asserting filesystem mock was not called for artifact files)

#### Scenario: Reload failure retains previous config without raising
- **WHEN** `reload_if_changed()` is called and reading the new artifact raises an `IOError`
- **THEN** no exception propagates and `current_config` still holds the previously loaded configuration
