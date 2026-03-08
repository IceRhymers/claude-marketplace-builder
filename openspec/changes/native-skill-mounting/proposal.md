## Why

The Claude Agent SDK provides native filesystem-based skill mounting: skills placed under `.claude/skills/<name>/SKILL.md` in an agent's working directory are discovered, routed, and invoked by the SDK automatically — exactly the same mechanism Claude Code uses. Scripts in `scripts/` run via the `Bash` tool using `$CLAUDE_SKILL_DIR` for absolute path resolution, and `references/` files are readable by the agent within its sandbox. There is no programmatic API for skill registration; the filesystem is the only supported mechanism.

The current implementation ignores this. It reads only `SKILL.md` content into `SkillsConfig.skill_contents: list[str]`, concatenates all skill content into a monolithic system prompt injection, and discards `scripts/` and `references/` entirely. This means multi-step skills with supporting scripts cannot work, the SDK's native skill routing is bypassed in favour of a fragile text concatenation, and there is no per-user control over which skills are active. The result is an application whose skill invocation model directly contradicts the SDK's design.

This change replaces the ad-hoc system-prompt-injection approach with the SDK's native mechanism: skills are copied as filesystem artifacts into each session's `.claude/skills/` directory at spawn time, enabling full script and reference support, SDK-native routing, and per-user opt-out of individual skills.

## What Changes

- `build-artifact.sh` preserves full skill directory trees (SKILL.md + scripts/ + references/) instead of flattening to SKILL.md only; `manifest.json` added to artifact root with `has_scripts`/`has_references` metadata per skill
- `SkillsConfig.skill_contents: list[str]` replaced by `SkillsConfig.skills: dict[str, SkillDefinition]`, where each `SkillDefinition` holds the path to the skill directory in the Volume artifact (no in-memory file content)
- New Lakebase table `user_skill_prefs` with `(user_id, skill_name, enabled)` and new API endpoints `GET /api/preferences/skills` and `PATCH /api/preferences/skills/{skill_name}`
- `AgentPool.get_or_create` copies only the user's enabled skill directories into `session_dir/.claude/skills/` before spawning the agent; `ClaudeAgentOptions` configured with `cwd=session_dir`, `setting_sources=["project"]`, `allowed_tools=["Skill","Bash","Read","Write"]`
- `build_agent` no longer accepts a `system_prompt` parameter and wraps `claude_agent_sdk.query()` instead of `anthropic.Anthropic().messages.stream()`

## Capabilities

### Modified Capabilities

- `artifact-pipeline`: update `build-artifact.sh` to preserve full skill directory trees and write `manifest.json`; amends the existing `artifact-pipeline` spec
- `mcp-config` (skills loading section only): replace `SkillsConfig.skill_contents` with path-based `SkillsConfig.skills` dict; the MCP loading, `substitute_token`, and `reload_if_changed` logic is unchanged

### New Capabilities

- `artifact-structure`: artifact layout and `manifest.json` schema for full skill tree preservation
- `skills-loader`: `SkillDefinition` dataclass and updated `SkillsConfig` shape with path-based skill references
- `user-skill-prefs`: per-user skill enable/disable via Lakebase and REST API
- `agent-sdk-integration`: native SDK skill mounting via `.claude/skills/` filesystem copy on agent spawn

## Impact

- `agent_pool.py`: `build_agent` signature changes (remove `system_prompt`, add `enabled_skill_names` + `skills_config`); `get_or_create` adds skill directory copy step before agent spawn; `SimpleAgent` wraps `claude_agent_sdk.query()` instead of raw Anthropic Messages API
- `skills.py`: `SkillsConfig` dataclass changes; `load_config_from_volume` reads `manifest.json` instead of globbing SKILL.md content; all callers of `skill_contents` must be updated
- `build-artifact.sh`: preserves `scripts/` and `references/` dirs; writes `manifest.json`; existing `SKILL.md`-only layout is superseded
- New migration: `user_skill_prefs` table added via Alembic
- New router: `routers/marketplace.py` (or `routers/preferences.py`) with preferences endpoints
- Existing tests using `mock_skills_config` fixture must be updated to use new `SkillsConfig` shape
- No React frontend changes required — skill preferences are exposed via REST and can be surfaced in settings UI in a future change
- New Python dependency: `claude-agent-sdk` (already declared as `anthropic[agent-sdk]`); no new packages required
