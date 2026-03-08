## 0. Test Infrastructure

- [ ] 0.1 Update `mock_skills_config` fixture in `tests/conftest.py`: replace `skill_contents=["..."]` with `skills={"test-skill": SkillDefinition(name="test-skill", path=Path("/tmp/fake/skills/test-skill"), has_scripts=False, has_references=False)}` and `version="v1.0.0"`, `mcp_config={}`; import `SkillDefinition` and `SkillsConfig` from `core.skills`
- [ ] 0.2 Add `mock_user_skill_prefs` fixture to `tests/conftest.py` that returns `{"test-skill"}` as the default enabled skill name set; wire as a FastAPI dependency override in the test client fixture
- [ ] 0.3 Add `session_dir_with_skill_structure` fixture to `tests/conftest.py` using `tmp_path`: creates `<tmp>/.claude/skills/test-skill/SKILL.md` and `<tmp>/.claude/skills/test-skill/scripts/run_test.py` for post-spawn sandbox verification
- [ ] 0.4 Verify test infrastructure compiles: `pytest --collect-only` exits 0 with no import errors after fixture updates

## 1. artifact-structure (amends artifact-pipeline)

- [ ] 1.1 Write new shell test cases in `claude-agent-app/scripts/test-build-artifact.sh` (RED): skill with `scripts/` → tarball preserves `scripts/` subdir; skill with `references/` → tarball preserves `references/` subdir; SKILL.md-only skill → no empty dirs; `manifest.json` exists at `<version>/manifest.json`; `manifest.json` `has_scripts` correct; `manifest.json` `has_references` correct; `manifest.json` `mcp_servers` lists keys from `.mcp.json`; direct copy to `.claude/skills/` yields readable SKILL.md
- [ ] 1.2 Update `claude-agent-app/scripts/build-artifact.sh`: replace SKILL.md-only collection loop with `cp -r <skill_dir> <staging>/<version>/skills/<name>` for each skill directory, preserving `scripts/` and `references/` subdirs (GREEN)
- [ ] 1.3 Add `manifest.json` generation to `build-artifact.sh`: after collecting skills, enumerate each skill dir to detect `scripts/` and `references/`, derive `plugin` from `SKILLS_DIR` basename, write `<version>/manifest.json` with `version`, `skills[]`, `mcp_servers[]` (GREEN)
- [ ] 1.4 Run `claude-agent-app/scripts/test-build-artifact.sh` — all tests green

## 2. skills-loader (replaces mcp-config skills section)

- [ ] 2.1 Write failing tests in `tests/unit/test_skills.py` (RED): `SkillsConfig` has no `skill_contents` attribute; `SkillsConfig.skills` is a dict; `load_config_from_volume` reads `manifest.json` (not rglob); `SkillDefinition.path` correct; `SkillDefinition.has_scripts` correct; missing skill dir → skipped + WARNING; missing `manifest.json` → empty skills, no exception; malformed `manifest.json` → empty config, ERROR logged; `reload_if_changed` logs `skills=<count>` (not `skill_contents`); `list_skills` endpoint returns `[{name, has_scripts, has_references}]`
- [ ] 2.2 Remove `skill_contents: list[str]` field from `SkillsConfig` dataclass in `core/skills.py`; add `skills: dict[str, SkillDefinition]` field; add `SkillDefinition` dataclass with `name`, `path`, `has_scripts`, `has_references` (GREEN — compile check)
- [ ] 2.3 Rewrite `load_config_from_volume` in `core/skills.py`: read `manifest.json` instead of `rglob("SKILL.md")`; for each skill entry construct `SkillDefinition`; validate path exists; skip missing dirs with WARNING; return `SkillsConfig(version=..., skills={...}, mcp_config=...)` (GREEN)
- [ ] 2.4 Update `reload_if_changed` log line to use `len(new_config.skills)` instead of `len(new_config.skill_contents)` (GREEN)
- [ ] 2.5 Update `routers/marketplace.py` (or equivalent) `list_skills` endpoint to return `[{name, has_scripts, has_references}]` from `skills_config.skills.values()` (GREEN)
- [ ] 2.6 Run `pytest tests/unit/test_skills.py` — all tests green

## 3. user-skill-prefs (new capability)

- [ ] 3.1 Write failing unit tests in `tests/unit/test_prefs.py` (RED): `get_user_skill_prefs` with mix of prefs and defaults → correct set; no pref rows → full skill set; orphaned pref for removed skill → not in result; two users → independent sets
- [ ] 3.2 Write failing integration tests in `tests/integration/test_prefs.py` (RED): `GET /api/preferences/skills` all-default → all enabled; `GET` with disabled row → enabled=false for that skill; `GET` empty config → `[]`; `GET` without token → `401`; `PATCH` new pref → `200` + row inserted; `PATCH` update existing → `200` + `updated_at` refreshed; `PATCH` unknown skill → `404` + no DB write; `PATCH` without token → `401`; two-user isolation
- [ ] 3.3 Generate and review Alembic migration for `user_skill_prefs` table in `claude-agent-app/app/alembic/versions/`: `user_id VARCHAR(255) NOT NULL`, `skill_name VARCHAR(255) NOT NULL`, `enabled BOOLEAN NOT NULL DEFAULT true`, `updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()`, `PRIMARY KEY (user_id, skill_name)` (GREEN)
- [ ] 3.4 Add `UserSkillPref` SQLAlchemy model to `core/models.py` with columns matching the migration (GREEN)
- [ ] 3.5 Implement `get_user_skill_prefs(user_id: str, db: Session, skills_config: SkillsConfig) -> set[str]` in `app/deps.py`: query all pref rows for user, default missing skills to enabled, intersect with current `skills_config.skills` keys (GREEN)
- [ ] 3.6 Create `claude-agent-app/app/routers/preferences.py` with `GET /api/preferences/skills` and `PATCH /api/preferences/skills/{skill_name}` endpoints; mount in `main.py` under `/api/preferences` (GREEN)
- [ ] 3.7 Run `pytest tests/unit/test_prefs.py tests/integration/test_prefs.py` — all tests green

## 4. agent-sdk-integration (replaces agent-pool build_agent section)

- [ ] 4.1 Write failing tests in `tests/unit/test_agent_pool.py` (RED): `build_agent` with `system_prompt` kwarg → `TypeError`; enabled skills copied to `.claude/skills/`; disabled skill NOT present in sandbox; `scripts/` preserved; `ClaudeAgentOptions` receives correct `cwd`, `setting_sources`, `allowed_tools`; `SimpleAgent.stream()` calls `claude_agent_sdk.query` not `anthropic.messages.stream`; `shutil.copytree` raises `OSError` → `RuntimeError` + pool empty + 503; cache hit → no `copytree` call
- [ ] 4.2 Remove `system_prompt` parameter from `build_agent` in `core/agent_pool.py`; add `enabled_skill_names: set[str]` and `skills_config: SkillsConfig` parameters (GREEN — compile check; tests still red until logic implemented)
- [ ] 4.3 Implement skill directory copy in `build_agent`: create `session_dir / ".claude" / "skills"` dir; for each `name` in `enabled_skill_names` call `shutil.copytree(skills_config.skills[name].path, session_dir / ".claude" / "skills" / name)` (GREEN)
- [ ] 4.4 Update `SimpleAgent` to wrap `claude_agent_sdk.query()`: construct `ClaudeAgentOptions(cwd=str(session_dir), setting_sources=["project"], allowed_tools=["Skill","Bash","Read","Write"])`; in `stream()` call `claude_agent_sdk.query(prompt=message, options=options)` and yield normalised event dicts (GREEN)
- [ ] 4.5 Update `AgentPool.get_or_create` to: (a) resolve `enabled_skills = get_user_skill_prefs(user_id, db, skills_config)` before calling `build_agent`; (b) remove `system_prompt` from `build_agent` call; (c) pass `enabled_skill_names` and `skills_config` to `build_agent`; (d) remove `substitute_token` call from spawn path (token substitution stays in MCP transport layer if needed) (GREEN)
- [ ] 4.6 Run `pytest tests/unit/test_agent_pool.py` — all tests green

## 5. Migration — update all existing tests broken by SkillsConfig changes

- [ ] 5.1 Identify all test files that reference `skill_contents` via: `grep -r "skill_contents" tests/` — list each file
- [ ] 5.2 Update each failing test to use new `SkillsConfig.skills` dict shape (using `mock_skills_config` fixture updated in task 0.1); remove any assertions about `skill_contents`
- [ ] 5.3 Update any test that asserts the agent's `_system_prompt` contains concatenated SKILL.md content — replace with assertions about `.claude/skills/` directory existence in session sandbox
- [ ] 5.4 Update `tests/unit/test_agent_pool.py` spawn test to assert `shutil.copytree` was called (not system prompt injection) and remove `substitute_token` assertion from spawn path

## 6. Documentation

- [ ] 6.1 Add `$CLAUDE_SKILL_DIR` section to `docs/SKILL-AUTHORING.md`: explain that scripts must use `$CLAUDE_SKILL_DIR` for absolute path resolution because the SDK's Bash tool working directory is the session sandbox root, not the skill directory; include example correct and incorrect script patterns

## 7. Full Suite Green Gate

- [ ] 7.1 Run `pytest tests/` — all tests pass with no failures or warnings about deprecated APIs
- [ ] 7.2 Run `claude-agent-app/scripts/test-build-artifact.sh` — all shell tests pass
- [ ] 7.3 Confirm no remaining references to `skill_contents` in `app/` or `tests/` (use `grep -r "skill_contents" claude-agent-app/app/ claude-agent-app/tests/` — expect zero results)
