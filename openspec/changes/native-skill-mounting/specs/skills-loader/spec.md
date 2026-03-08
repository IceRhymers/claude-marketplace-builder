## MODIFIED Requirements

### Capability: `mcp-config` — skills loading section replaced

This spec replaces the skills loading section of the `mcp-config` capability defined in `openspec/changes/claude-agent-sdk-databricks-app/specs/mcp-config/spec.md`. The requirement "Skills loaded as Claude Agent SDK system prompt fragments" and its associated scenarios are superseded in their entirety. All MCP config loading requirements (`latest.json`, `substitute_token`, `reload_if_changed`, hot-reload) remain unchanged.

#### Requirement: SkillsConfig uses path-based SkillDefinition, not in-memory content

`SkillsConfig` SHALL replace `skill_contents: list[str]` with `skills: dict[str, SkillDefinition]`, where each `SkillDefinition` holds the absolute path to the skill directory in the unpacked Volume artifact. No SKILL.md file content SHALL be read into memory by the loader.

New dataclass definitions:

```python
@dataclasses.dataclass
class SkillDefinition:
    name: str
    path: Path              # absolute path to skill dir in Volume artifact
    has_scripts: bool
    has_references: bool

@dataclasses.dataclass
class SkillsConfig:
    version: str
    skills: dict[str, SkillDefinition]   # name → SkillDefinition
    mcp_config: dict[str, Any]           # unchanged
```

##### Scenario: SkillsConfig.skills keyed by skill name
- **WHEN** `load_config_from_volume` loads an artifact containing skills `databricks-lineage` and `slack-summary`
- **THEN** `config.skills` is a dict with keys `"databricks-lineage"` and `"slack-summary"`
- **AND** each value is a `SkillDefinition` instance
- **AND** `config.skill_contents` does NOT exist (attribute removed)

##### Scenario: SkillDefinition.path points to correct artifact subdirectory
- **WHEN** the artifact is at `/dbfs/volumes/.../v1.2.0/`
- **AND** `manifest.json` lists skill `databricks-lineage`
- **THEN** `config.skills["databricks-lineage"].path == Path("/dbfs/volumes/.../v1.2.0/skills/databricks-lineage")`

##### Scenario: SkillDefinition.has_scripts reflects manifest metadata
- **WHEN** `manifest.json` contains `{"name": "databricks-lineage", "has_scripts": true, "has_references": false}`
- **THEN** `config.skills["databricks-lineage"].has_scripts is True`
- **AND** `config.skills["databricks-lineage"].has_references is False`

#### Requirement: load_config_from_volume reads manifest.json, not SKILL.md glob

`load_config_from_volume(volume_path: str) -> SkillsConfig` SHALL read `manifest.json` from the versioned artifact directory to enumerate skills. It SHALL NOT use `rglob("SKILL.md")` or read any file content from skill directories.

For each skill entry in `manifest.json["skills"]`:
- Construct `path = artifact_dir / "skills" / skill["name"]`
- Validate the path exists as a directory; if not, log a WARNING and skip this skill (do not raise)
- Create a `SkillDefinition` with `name`, `path`, `has_scripts`, `has_references` from the manifest entry

##### Scenario: Valid manifest with skill directories present
- **WHEN** `manifest.json` lists one skill and the corresponding `skills/<name>/` directory exists
- **THEN** `config.skills` contains one entry with a valid `SkillDefinition`
- **AND** no file content is read from the skill directory

##### Scenario: Skill directory listed in manifest but missing from artifact
- **WHEN** `manifest.json` lists skill `missing-skill` but `skills/missing-skill/` does not exist
- **THEN** `config.skills` does NOT contain an entry for `missing-skill`
- **AND** a WARNING is logged: `"Skill directory not found, skipping: <path>"`
- **AND** no exception is raised; other skills are loaded normally

##### Scenario: manifest.json missing from artifact directory
- **WHEN** the versioned artifact directory exists but contains no `manifest.json`
- **THEN** `load_config_from_volume` logs a WARNING and returns `SkillsConfig(version=version, skills={}, mcp_config={})`
- **AND** no exception is raised

##### Scenario: manifest.json contains invalid JSON
- **WHEN** `manifest.json` exists but contains malformed JSON
- **THEN** `load_config_from_volume` logs an ERROR and returns `SkillsConfig(version="", skills={}, mcp_config={})`
- **AND** no exception propagates to the caller

#### Requirement: get_current_config and reload_if_changed remain thread-safe and interface-compatible

`get_current_config() -> SkillsConfig` SHALL remain unchanged: it returns the current `SkillsConfig` under `_config_lock`. `reload_if_changed(volume_path: str) -> None` SHALL remain unchanged: it reads `latest.json`, compares versions, and calls `load_config_from_volume` only when the version has changed. Both functions are unaffected by the `skill_contents` → `skills` rename except that the logged count now uses `len(new_config.skills)`.

##### Scenario: reload_if_changed logs skill count from new dict
- **WHEN** `reload_if_changed` loads a new version with 3 skills
- **THEN** the log line reads: `"reloaded config version=v1.2.0 skills=3"` (or equivalent)

#### Requirement: list_skills endpoint returns name and metadata, not SKILL.md content

The `GET /api/marketplace/skills` (or `GET /api/skills`) endpoint SHALL return a list of `{name, has_scripts, has_references}` objects derived from `SkillsConfig.skills.values()`. It SHALL NOT return raw SKILL.md content.

##### Scenario: list_skills response shape
- **WHEN** `GET /api/marketplace/skills` is called
- **THEN** the response is `200` with body:
  ```json
  [
    {"name": "databricks-lineage", "has_scripts": true, "has_references": false},
    {"name": "slack-summary", "has_scripts": false, "has_references": false}
  ]
  ```
- **AND** no SKILL.md file content appears in the response

##### Scenario: list_skills with empty skills config
- **WHEN** `SkillsConfig.skills` is empty (e.g., no artifact loaded)
- **THEN** the response is `200` with body `[]`

#### Requirement: All existing call sites of skill_contents are updated

Every reference to `SkillsConfig.skill_contents` or `config.skill_contents` in the codebase SHALL be removed or replaced with `SkillsConfig.skills` access patterns. This includes:
- `agent_pool.py`: system prompt concatenation removed (replaced by SDK skill mounting in `agent-sdk-integration` spec)
- `routers/marketplace.py` or equivalent: `list_skills` endpoint updated (see above)
- `tests/conftest.py`: `mock_skills_config` fixture updated to use new `SkillsConfig` shape
- Any other file that references `skill_contents`

## Test Requirements

Tests MUST be written in `tests/unit/test_skills.py` BEFORE `core/skills.py` is updated (RED phase). Existing tests that used `skill_contents` MUST be rewritten to use the new API.

Required test scenarios (new or updated):

- `load_config_from_volume` with valid `manifest.json` + skill directories → `SkillsConfig.skills` dict with correct `SkillDefinition` entries; no `skill_contents` attribute
- `SkillDefinition.path` equals `artifact_dir / "skills" / skill_name`
- `SkillDefinition.has_scripts` is `True` when manifest says `has_scripts: true`
- `SkillDefinition.has_references` is `False` when manifest says `has_references: false`
- Skill directory listed in manifest but missing from filesystem → skill skipped, WARNING logged, no exception
- `manifest.json` missing from artifact → empty `skills` dict, no exception
- `manifest.json` malformed JSON → empty `SkillsConfig`, ERROR logged, no exception
- `latest.json` missing → no exception, empty `SkillsConfig` returned (existing test updated to use new shape)
- `substitute_token` tests → unchanged (these tests remain valid)
- `reload_if_changed` detects new version → `current_config.skills` dict updated (not `skill_contents`)
- `reload_if_changed` version unchanged → skill directories NOT re-read (existing test updated)
- `reload_if_changed` artifact read raises `IOError` → no exception, `current_config` retains previous value (existing test updated)
- `GET /api/marketplace/skills` (or equivalent) → returns `[{name, has_scripts, has_references}]` from `skills.values()`
- `GET /api/marketplace/skills` with empty config → returns `[]`

Fixture changes required in `tests/conftest.py`:
- `mock_skills_config`: replace `skill_contents=["..."]` with `skills={"skill-name": SkillDefinition(name="skill-name", path=Path("/tmp/fake/skills/skill-name"), has_scripts=False, has_references=False)}` and `version="v1.0.0"`, `mcp_config={}`
