## MODIFIED Requirements

### Capability: `artifact-pipeline` — full skill directory preservation

This spec amends the `artifact-pipeline` capability defined in `openspec/changes/claude-agent-sdk-databricks-app/specs/artifact-pipeline/spec.md`. All existing requirements remain in force except where explicitly superseded below.

#### Requirement: build-artifact.sh preserves full skill directory trees

The `build-artifact.sh` script SHALL copy the entire skill directory subtree — including `scripts/` and `references/` subdirectories — for each skill found under `SKILLS_DIR`, not only `SKILL.md`. The resulting artifact unpacked layout SHALL match `.claude/skills/<name>/` structure expected by the Claude Agent SDK.

##### Scenario: Skill with scripts/ and references/ — full tree preserved
- **WHEN** a skill directory contains `SKILL.md`, `scripts/run_lineage.py`, and `references/lineage_concepts.md`
- **AND** `build-artifact.sh v1.2.0` is invoked
- **THEN** the tarball extracts to:
  ```
  v1.2.0/
  └── skills/
      └── databricks-lineage/
          ├── SKILL.md
          ├── scripts/
          │   └── run_lineage.py
          └── references/
              └── lineage_concepts.md
  ```
- **AND** no files from the skill directory are omitted

##### Scenario: Skill with SKILL.md only — single file preserved (no empty dirs)
- **WHEN** a skill directory contains only `SKILL.md` and no `scripts/` or `references/` subdirectory
- **AND** `build-artifact.sh v1.2.0` is invoked
- **THEN** the tarball extracts to `v1.2.0/skills/<name>/SKILL.md` with no empty `scripts/` or `references/` directories

##### Scenario: Multiple skills — each tree independently preserved
- **WHEN** `SKILLS_DIR` contains two skill subdirectories, one with `scripts/` and one without
- **THEN** the tarball preserves the full tree of the first skill and the SKILL.md-only tree of the second skill; no cross-contamination between skill directories

#### Requirement: manifest.json written at artifact root

`build-artifact.sh` SHALL write a `manifest.json` file at `<version>/manifest.json` inside the tarball (alongside the `skills/` directory). The manifest SHALL enumerate every skill included in the artifact with per-skill metadata.

##### Scenario: manifest.json schema
- **WHEN** `build-artifact.sh v1.2.0` completes successfully
- **THEN** `v1.2.0/manifest.json` contains valid JSON matching:
  ```json
  {
    "version": "v1.2.0",
    "skills": [
      {
        "name": "databricks-lineage",
        "plugin": "databricks-skills",
        "has_scripts": true,
        "has_references": false
      }
    ],
    "mcp_servers": ["databricks", "slack"]
  }
  ```
- **AND** `has_scripts` is `true` if and only if a non-empty `scripts/` directory exists for that skill
- **AND** `has_references` is `true` if and only if a non-empty `references/` directory exists for that skill
- **AND** `mcp_servers` lists the top-level keys from `mcpServers` in `.mcp.json` (empty array if no `.mcp.json`)

##### Scenario: manifest.json with no skills
- **WHEN** `SKILLS_DIR` contains no skill directories
- **THEN** `manifest.json` contains `{"version": "<version>", "skills": [], "mcp_servers": [...]}`
- **AND** the script exits `0` with a warning on stderr (existing behaviour unchanged)

##### Scenario: manifest.json plugin field derived from directory name
- **WHEN** `SKILLS_DIR` is set to a plugin's skills directory (e.g., `plugins/databricks-skills/skills`)
- **THEN** the `plugin` field in each skill entry in `manifest.json` is the basename of the parent plugin directory (e.g., `"databricks-skills"`)
- **AND** if the plugin name cannot be determined (e.g., `SKILLS_DIR` does not follow plugin convention), `plugin` is set to `""` (empty string)

#### Requirement: Artifact layout is compatible with .claude/skills/ SDK structure

The `skills/<name>/` layout inside the unpacked tarball SHALL exactly match the `.claude/skills/<name>/` structure expected by the Claude Agent SDK, so that the application can copy the unpacked directory tree directly into a session sandbox without path transformation.

##### Scenario: Direct copy into session sandbox is valid
- **WHEN** the tarball for version `v1.2.0` is extracted
- **AND** `v1.2.0/skills/` is copied to `session_dir/.claude/skills/`
- **THEN** the resulting `session_dir/.claude/skills/<name>/SKILL.md` is readable
- **AND** `session_dir/.claude/skills/<name>/scripts/` exists if the skill has scripts
- **AND** the Claude Agent SDK can discover and mount the skill from `ClaudeAgentOptions(cwd=str(session_dir))`

#### Requirement: MCP config remains in .mcp.json at artifact root (unchanged)

The MCP configuration file `.mcp.json` SHALL remain at `<version>/.mcp.json` in the artifact layout. The `manifest.json` `mcp_servers` field summarises its top-level server keys for metadata purposes but does not replace it. This requirement is unchanged from the existing `artifact-pipeline` spec.

## Test Requirements

Shell script tests MUST be written in `claude-agent-app/scripts/test-build-artifact.sh` BEFORE the updated `build-artifact.sh` is implemented (RED phase). All new test scenarios MUST be added to the existing test harness file.

Required test scenarios (in addition to existing artifact-pipeline tests):

- `build-artifact.sh v1.2.0` with `skills/databricks-lineage/SKILL.md` and `skills/databricks-lineage/scripts/run_lineage.py` present → tarball extracts with `v1.2.0/skills/databricks-lineage/scripts/run_lineage.py` preserved
- `build-artifact.sh v1.2.0` with `skills/databricks-lineage/references/concepts.md` present → tarball extracts with `references/concepts.md` preserved
- `build-artifact.sh v1.2.0` with SKILL.md-only skill → no empty `scripts/` or `references/` dirs in tarball
- `build-artifact.sh v1.2.0` with scripts present → `manifest.json` contains `"has_scripts": true` for that skill
- `build-artifact.sh v1.2.0` with no scripts → `manifest.json` contains `"has_scripts": false`
- `build-artifact.sh v1.2.0` with `.mcp.json` containing `{"mcpServers": {"databricks": {}, "slack": {}}}` → `manifest.json` `mcp_servers` equals `["databricks", "slack"]`
- `build-artifact.sh v1.2.0` with no `.mcp.json` → `manifest.json` `mcp_servers` equals `[]`
- Extracted `v1.2.0/skills/<name>/` directory tree can be `cp -r`'d into a `.claude/skills/` directory and SKILL.md is readable at the expected path
