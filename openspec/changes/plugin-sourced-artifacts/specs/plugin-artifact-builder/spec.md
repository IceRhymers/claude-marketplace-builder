## ADDED Requirements

### Requirement: Build artifact from marketplace plugins
The build script SHALL read skill definitions from `plugins/*/` by parsing each plugin's `.claude-plugin/plugin.json` and copying skill directories from the plugin's `skills/` path into the artifact.

#### Scenario: Standard build from plugin tree
- **WHEN** `build-artifact.sh <version>` is executed with no overrides
- **THEN** the script discovers all plugins under `plugins/`, reads each `plugin.json`, copies every skill directory into `<version>/skills/<skill-name>/`, and produces a valid tarball

#### Scenario: Plugin with no skills directory
- **WHEN** a plugin exists in `plugins/` but has no `skills/` subdirectory
- **THEN** the script skips that plugin with a warning and continues

### Requirement: Generate manifest from plugin metadata
The build script SHALL generate `manifest.json` with skill entries derived from the plugin tree, including `name`, `has_scripts`, and `has_references` fields per skill.

#### Scenario: Manifest includes all discovered skills
- **WHEN** the artifact is built from plugins containing skills `databricks-lineage`, `databricks-workspace-files`, `onboarding`, `incident-response`, `lucid-diagram`, `update-skills`, `mcp-setup`, and `budget-setup`
- **THEN** `manifest.json` contains entries for all 8 skills with correct `has_scripts` and `has_references` flags

### Requirement: Merge MCP configs from plugin .mcp.json files
The build script SHALL find all `.mcp.json` files at plugin roots, merge their `mcpServers` entries into a single `.mcp.json` in the artifact.

#### Scenario: Single plugin with MCP config
- **WHEN** only `plugins/databricks-mcp/.mcp.json` exists with `slack-mcp` and `genie-mcp` servers
- **THEN** the artifact `.mcp.json` contains both `slack-mcp` and `genie-mcp` under `mcpServers`

#### Scenario: Duplicate MCP server names across plugins
- **WHEN** two plugins define an MCP server with the same name
- **THEN** the build script emits a warning to stderr indicating the duplicate, and the last-processed plugin's definition wins

### Requirement: Remove cowork/skills directory
The `cowork/skills/` directory SHALL be deleted. The `getting-started` skill SHALL be moved to `plugins/internal-skills/skills/getting-started/`.

#### Scenario: getting-started skill relocated
- **WHEN** the change is applied
- **THEN** `cowork/skills/` no longer exists and `plugins/internal-skills/skills/getting-started/SKILL.md` contains the skill content

### Requirement: Configurable plugin source path
The build script SHALL accept a `PLUGINS_DIR` environment variable override (defaulting to `../plugins` relative to the script). This allows CI or alternative layouts.

#### Scenario: Custom plugins directory
- **WHEN** `PLUGINS_DIR=/custom/path build-artifact.sh v1.0.0` is executed
- **THEN** the script reads plugins from `/custom/path/*/` instead of the default location
