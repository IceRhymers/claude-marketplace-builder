## ADDED Requirements

### Requirement: Load skill and MCP config from Databricks Volume
The system SHALL read skill definitions (SKILL.md files) and MCP server configuration (`.mcp.json`) from a Databricks Volume path specified by the `SKILLS_VOLUME_PATH` environment variable, enabling configuration updates without redeploying the application.

#### Scenario: Config loaded at startup
- **WHEN** the FastAPI app starts
- **THEN** the system reads `{SKILLS_VOLUME_PATH}/latest.json` to obtain the current artifact version path, then loads skill Markdown files and `.mcp.json` from that versioned directory

#### Scenario: Missing volume path env var
- **WHEN** `SKILLS_VOLUME_PATH` is not set
- **THEN** the app logs a warning and starts with an empty skill set and no MCP connections (graceful degradation)

### Requirement: Latest pointer via latest.json
The system SHALL determine the active artifact version by reading a `latest.json` file at `{SKILLS_VOLUME_PATH}/latest.json` with the schema `{"version": "<semver>", "path": "<relative-path>"}`, where `path` points to the versioned artifact directory relative to `SKILLS_VOLUME_PATH`.

#### Scenario: latest.json read successfully
- **WHEN** `latest.json` exists and is valid JSON
- **THEN** the system resolves the full artifact path as `{SKILLS_VOLUME_PATH}/{latest.path}` and loads skills and MCP config from there

#### Scenario: latest.json missing or malformed
- **WHEN** `latest.json` does not exist or contains invalid JSON
- **THEN** the system logs an error and starts with an empty configuration (does not crash)

### Requirement: Hot-reload on artifact publish
The system SHALL support reloading the skill and MCP configuration without restarting the application when a new artifact is published and `latest.json` is updated. Reloading SHALL be triggered by an APScheduler job on a configurable interval (default: every 60 seconds).

#### Scenario: New artifact detected and loaded
- **WHEN** `latest.json` is updated to point to a new version path and the reload job fires
- **THEN** the system loads the new skills and MCP config, updates the in-memory configuration, and logs the version change

#### Scenario: Reload interval configurable
- **WHEN** `SKILLS_RELOAD_INTERVAL_SECONDS` env var is set
- **THEN** the APScheduler reload job fires at that interval instead of the default 60 seconds

#### Scenario: Reload failure is non-fatal
- **WHEN** the reload job encounters an error reading from the Volume (e.g., network hiccup)
- **THEN** the system retains the previously loaded configuration and logs the error; it does not crash or clear existing config

### Requirement: MCP server config schema
The system SHALL parse `.mcp.json` using the schema `{"mcpServers": {"<name>": {"command": ..., "args": [...], "env": {...}, "headers": {...}}}}`, consistent with the Claude Code MCP config format, substituting the user's `X-Forwarded-Access-Token` for `${ACCESS_TOKEN}` placeholders in `headers` and `env` values at agent spawn time.

#### Scenario: Token placeholder substituted at spawn
- **WHEN** a `.mcp.json` entry contains `"Authorization": "Bearer ${ACCESS_TOKEN}"` in its `headers`
- **THEN** the AgentPool substitutes the spawning user's access token before establishing the MCP connection

#### Scenario: Static MCP entries passed through unchanged
- **WHEN** a `.mcp.json` entry contains no `${ACCESS_TOKEN}` placeholder
- **THEN** its configuration is passed to the MCP transport unchanged

### Requirement: Skills loaded as Claude Agent SDK system prompt fragments
The system SHALL load each SKILL.md file from the artifact directory and concatenate their contents into the agent's system prompt (or provide them as tool descriptions), preserving the frontmatter metadata for logging and version tracking.

#### Scenario: Skills injected into agent system prompt
- **WHEN** an agent is spawned
- **THEN** the agent's system prompt includes the concatenated content of all SKILL.md files from the current artifact version

#### Scenario: No skills file loaded gracefully
- **WHEN** the artifact directory contains no SKILL.md files
- **THEN** the agent is spawned with a minimal default system prompt and no skill-specific instructions

## Test Requirements

Tests MUST be written in `tests/unit/test_skills.py` BEFORE `core/skills.py` is implemented (RED phase). Filesystem reads are mocked using `unittest.mock.patch` on `open` / `os.path.exists`, or a `tmp_path` fixture with real files.

Required test scenarios:
- `load_config_from_volume` with valid `latest.json` + SKILL.md + `.mcp.json` → `SkillsConfig` with correct version, skill_contents, mcp_config
- `latest.json` missing → no exception, empty `SkillsConfig` returned
- `latest.json` contains invalid JSON → no exception, error logged, empty `SkillsConfig` returned
- `substitute_token` with `${ACCESS_TOKEN}` in headers → correct token substituted
- `substitute_token` with `${ACCESS_TOKEN}` in env values → correct token substituted
- `substitute_token` with no placeholders → dict returned unchanged
- `reload_if_changed` detects new version in `latest.json` → `current_config` updated to new version
- `reload_if_changed` version unchanged → artifact directory NOT re-read
- `reload_if_changed` artifact read raises `IOError` → no exception, `current_config` retains previous value
