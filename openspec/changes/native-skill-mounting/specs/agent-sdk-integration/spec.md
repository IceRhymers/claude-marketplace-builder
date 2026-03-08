## MODIFIED Requirements

### Capability: `agent-pool` — native SDK skill mounting replaces system prompt injection

This spec replaces the `build_agent` and agent spawn sections of the `agent-pool` capability defined in `openspec/changes/claude-agent-sdk-databricks-app/specs/agent-pool/spec.md`. All eviction, TTL, shutdown, and MCP connection requirements remain unchanged. The file sync (`file-sync-on-eviction`) and file restore (`file-restore-on-resume`) behaviours from `openspec/changes/session-persistence/` remain unchanged and occur at the same points in the spawn sequence.

#### Requirement: Enabled skill directories are copied into session sandbox at spawn

On every cache miss in `AgentPool.get_or_create`, the system SHALL copy each enabled skill directory from the Volume artifact into `session_dir/.claude/skills/` BEFORE initialising the Claude Agent SDK.

Steps on cache miss (full ordered sequence):
1. File restore from Volume (existing — unchanged)
2. Create `session_dir/.claude/skills/` directory
3. For each `skill_name` in `enabled_skills`:
   - Resolve `skill_def = skills_config.skills[skill_name]`
   - Call `shutil.copytree(skill_def.path, session_dir / ".claude" / "skills" / skill_name)`
4. Hydrate history from DB (existing — unchanged)
5. Initialise Agent SDK (new — see below)

##### Scenario: Only enabled skills are copied into .claude/skills/
- **WHEN** `SkillsConfig.skills` contains `skill-a`, `skill-b`, `skill-c`
- **AND** `enabled_skills = {"skill-a", "skill-c"}` (skill-b disabled by user)
- **THEN** `session_dir/.claude/skills/skill-a/` exists
- **AND** `session_dir/.claude/skills/skill-c/` exists
- **AND** `session_dir/.claude/skills/skill-b/` does NOT exist

##### Scenario: Skill with scripts/ is fully preserved after copy
- **WHEN** `skill_def.path` contains `SKILL.md` and `scripts/run_lineage.py`
- **THEN** `session_dir/.claude/skills/<name>/SKILL.md` exists
- **AND** `session_dir/.claude/skills/<name>/scripts/run_lineage.py` exists

##### Scenario: No enabled skills — .claude/skills/ directory is empty
- **WHEN** `enabled_skills` is an empty set
- **THEN** `session_dir/.claude/skills/` exists but contains no subdirectories
- **AND** agent is still spawned normally (SDK starts with no skills)

##### Scenario: Skill copy failure raises RuntimeError (surfaces as 503)
- **WHEN** `shutil.copytree` raises an `OSError` for one of the enabled skills
- **THEN** the exception is caught, wrapped as `RuntimeError("Agent initialization failed: <reason>")`, and propagated to the streaming endpoint
- **AND** the pool does NOT store the failed agent entry
- **AND** the streaming endpoint returns `503 Service Unavailable`

#### Requirement: ClaudeAgentOptions configured with session cwd and project settings

The Claude Agent SDK SHALL be initialised with `ClaudeAgentOptions` pointing to the session sandbox as its working directory, using project-level settings only.

```python
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    cwd=str(session_dir),
    setting_sources=["project"],
    allowed_tools=["Skill", "Bash", "Read", "Write"],
)
```

##### Scenario: ClaudeAgentOptions receives correct cwd
- **WHEN** `build_agent` is called with `session_dir = Path("/tmp/claude-agent-sessions/conv-123")`
- **THEN** `ClaudeAgentOptions.cwd == "/tmp/claude-agent-sessions/conv-123"`

##### Scenario: setting_sources is ["project"] only
- **WHEN** `ClaudeAgentOptions` is constructed
- **THEN** `setting_sources == ["project"]`
- **AND** user-level settings (`~/.claude/`) are NOT included

##### Scenario: allowed_tools includes Skill, Bash, Read, Write
- **WHEN** `ClaudeAgentOptions` is constructed
- **THEN** `"Skill"` is in `allowed_tools`
- **AND** `"Bash"` is in `allowed_tools`

#### Requirement: build_agent signature removes system_prompt and substitute_token call

`build_agent` SHALL no longer accept a `system_prompt` parameter and SHALL NOT call `substitute_token` on the MCP config. Skills provide their own prompts natively via SKILL.md; the MCP config is passed through unchanged from `SkillsConfig.mcp_config` (token substitution, if still needed, is handled by the caller before passing to `build_agent`).

New signature:

```python
def build_agent(
    session_dir: Path,
    mcp_config: dict,
    enabled_skill_names: set[str],
    skills_config: SkillsConfig,
) -> Any:
```

##### Scenario: build_agent does not accept system_prompt
- **WHEN** `build_agent` is called with a `system_prompt` keyword argument
- **THEN** a `TypeError` is raised (parameter does not exist)

##### Scenario: build_agent copies skills and returns agent wrapping SDK query
- **WHEN** `build_agent(session_dir=..., mcp_config={}, enabled_skill_names={"skill-a"}, skills_config=config)` is called
- **THEN** `session_dir/.claude/skills/skill-a/SKILL.md` exists
- **AND** the returned agent wraps `claude_agent_sdk.query()`

#### Requirement: SimpleAgent wraps claude_agent_sdk.query(), not anthropic.messages.stream()

The `SimpleAgent` class SHALL wrap `claude_agent_sdk.query()` for streaming responses. It SHALL NOT use `anthropic.Anthropic().messages.stream()`.

##### Scenario: SimpleAgent.stream() uses claude_agent_sdk.query()
- **WHEN** `agent.stream("hello")` is called
- **THEN** `claude_agent_sdk.query` is called (not `anthropic.Anthropic.messages.stream`)
- **AND** the agent yields `{"type": "text_delta", "text": "..."}` events from the SDK output
- **AND** the agent yields `{"type": "done"}` as the final event

##### Scenario: SimpleAgent propagates SDK tool-use events
- **WHEN** the SDK emits a tool-use event during query execution
- **THEN** `SimpleAgent.stream()` yields `{"type": "tool_use", ...}` to the SSE streaming endpoint

#### Requirement: get_or_create passes enabled_skill_names to build_agent

`AgentPool.get_or_create` SHALL resolve the set of enabled skills for the user via `get_user_skill_prefs` and pass it to `build_agent`. The `system_prompt` parameter is removed from all internal calls.

##### Scenario: get_or_create calls build_agent with enabled_skill_names
- **WHEN** `get_or_create` is called for a new conversation for `user_id=alice`
- **AND** `get_user_skill_prefs("alice", db, skills_config)` returns `{"skill-a", "skill-b"}`
- **THEN** `build_agent` is called with `enabled_skill_names={"skill-a", "skill-b"}`
- **AND** `session_dir/.claude/skills/skill-a/` and `session_dir/.claude/skills/skill-b/` exist

##### Scenario: Cache hit does not re-copy skills
- **WHEN** `get_or_create` is called for an existing pool entry
- **THEN** no `shutil.copytree` calls are made (skills already in place)
- **AND** `build_agent` is NOT called

## Test Requirements

Tests MUST be written in `tests/unit/test_agent_pool.py` BEFORE implementation (RED phase). All tests mock `build_agent` and `shutil.copytree` using `unittest.mock.patch`.

Required test scenarios (new or updated):

- `build_agent` copies only enabled skills into `.claude/skills/` — disabled skill directory NOT present
- `build_agent` preserves `scripts/` subdir if present in skill source
- `ClaudeAgentOptions` receives correct `cwd`, `setting_sources=["project"]`, `allowed_tools` includes `"Skill"`
- `session_dir/.claude/skills/<name>/SKILL.md` exists after `build_agent` returns
- `SimpleAgent.stream()` calls `claude_agent_sdk.query` (not `anthropic.Anthropic.messages.stream`)
- `build_agent` with `system_prompt` kwarg → `TypeError`
- `shutil.copytree` raises `OSError` → `RuntimeError` propagated; pool stays empty; 503 returned
- Cache miss with 2 enabled skills → `shutil.copytree` called twice with correct source/dest paths
- Cache hit → `shutil.copytree` NOT called; `build_agent` NOT called
- `get_or_create` with empty `enabled_skills` → `session_dir/.claude/skills/` created but empty; agent spawned

Fixture additions required in `tests/conftest.py`:
- `session_dir_with_skill_structure`: a `tmp_path`-based fixture that creates:
  ```
  <tmp>/
  └── .claude/
      └── skills/
          └── test-skill/
              ├── SKILL.md
              └── scripts/
                  └── run_test.py
  ```
  Used to verify that `build_agent` correctly populates the session sandbox.
- Update `mock_skills_config` to use new `SkillsConfig` shape (see `skills-loader` spec)
- `mock_user_skill_prefs`: fixture yielding `{"test-skill"}` as the default enabled set (see `user-skill-prefs` spec)
