## Context

The Claude Agent SDK discovers skills purely through the filesystem: it reads `.claude/skills/<name>/SKILL.md` relative to the `cwd` passed in `ClaudeAgentOptions`. Skills with supporting scripts place them under `scripts/` inside the skill directory; the SDK sets `$CLAUDE_SKILL_DIR` so scripts can resolve their own absolute paths. There is no `register_skill()` API — the filesystem is the only integration point.

The existing `claude-agent-app/` follows the Volume-backed artifact pattern established in `claude-agent-sdk-databricks-app`: a `latest.json` pointer file identifies the current versioned artifact directory, an APScheduler job hot-reloads when the pointer changes, and the Databricks WorkspaceClient is used for Volume I/O. Session sandbox persistence (sync on eviction, restore on resume) was added in `session-persistence`. This change builds on both: it extends the artifact layout, replaces the in-memory skill representation, adds per-user preference storage, and wires the SDK's native mounting mechanism into the agent spawn path.

## Goals / Non-Goals

**Goals:**
- Skills work as first-class SDK artifacts: SKILL.md, scripts/, and references/ all copied into the session sandbox
- Per-user opt-out of individual skills without affecting other users
- Full skill directory preserved in the Volume artifact — no content read into memory
- `build_agent` wraps `claude_agent_sdk.query()` so SDK-native tool routing works
- All changes are test-driven: failing tests before every implementation task

**Non-Goals:**
- Per-user MCP server enable/disable (MCP auth management is a separate concern)
- Skill discovery from sources other than the Volume artifact (e.g., Git or local disk at runtime)
- UI for skill preferences (REST API only in this change; frontend settings page is a follow-up)
- Skill version pinning per user (all users see the same artifact version)
- Concurrent write safety for `user_skill_prefs` beyond what Postgres upsert provides

## Decisions

### D1: Filesystem over in-memory — SDK has no programmatic skill API

**Decision:** Skills are represented in `SkillsConfig` as `SkillDefinition` objects holding a `Path` to the skill directory in the unpacked Volume artifact. `load_config_from_volume` records paths and validates their existence; it never reads file content into memory.

**Rationale:** The Claude Agent SDK has no `register_skill()` or equivalent API. Skills must be present as files under `.claude/skills/` in the agent's `cwd`. Holding file content in memory and injecting it into a system prompt (the old approach) bypasses the SDK entirely — scripts, references, and SDK-native routing all fail silently. Path-based representation is the minimum necessary to support the copy-on-spawn pattern in D2.

**Alternative considered:** Keep `skill_contents: list[str]` and also copy files. Rejected — dual representation creates a sync hazard and keeps the wrong mental model alive in the codebase.

### D2: Copy on spawn, not symlink

**Decision:** At agent spawn time, `shutil.copytree` copies each enabled skill directory from the Volume artifact path into `session_dir/.claude/skills/<name>/`. Symlinks are not used.

**Rationale:** The Volume artifact is mounted at a fixed path shared across all sessions; symlinks into a shared directory would mean one session's script execution could observe another session's file mutations. Full copy provides session isolation at the cost of disk space (skills are typically small — SKILL.md + a few scripts). Symlinks across Volume mount points are also unreliable on some Databricks runtime configurations.

**Alternative considered:** Symlink from `session_dir/.claude/skills/<name>` to the artifact path. Rejected — not isolating, unreliable across mount points.

### D3: Default-enabled — skills are on unless the user explicitly disables

**Decision:** If no row exists in `user_skill_prefs` for a given `(user_id, skill_name)` pair, the skill is treated as enabled. `get_user_skill_prefs` returns the full set of skill names from `SkillsConfig.skills` minus those with an explicit `enabled=false` row.

**Rationale:** New skills added to the artifact become immediately available to all users without requiring each user to opt in. This matches the expected rollout behaviour: ops team publishes a new skill, all users get it on next session spawn. Users who want to opt out can PATCH to disable. Defaulting to disabled would require every user to explicitly enable every skill, adding friction with no corresponding safety benefit since skills are org-controlled artifacts.

**Alternative considered:** Default-disabled; users must opt in to each skill. Rejected — too much friction; contradicts marketplace model where skills are curated org-wide.

### D4: No MCP prefs in this change

**Decision:** `user_skill_prefs` covers skills only. There is no `user_mcp_prefs` table or MCP enable/disable endpoint in this change.

**Rationale:** MCP enable/disable is entangled with credential management: an MCP server may require per-user OAuth setup before it can be used. Disabling an MCP server without revoking its credentials is a half-measure; enabling one requires confirming the user has completed auth. This complexity is out of scope here. The `user_skill_prefs` pattern is straightforward by comparison — skills have no credential state.

### D5: `setting_sources=["project"]` not `["user", "project"]`

**Decision:** `ClaudeAgentOptions(setting_sources=["project"])` is used when initialising the agent. User-level settings (`~/.claude/`) are excluded.

**Rationale:** Skills in this app are org-controlled marketplace artifacts, not personal user customisations. Including user-level settings (`~/.claude/`) would allow individual users to inject arbitrary skills or tool permissions that bypass the marketplace approval process, and would make session behaviour non-deterministic across Databricks App instances (different underlying VMs may have different `~/.claude/` states). Project-level settings are authoritative and reproducible.

**Alternative considered:** `setting_sources=["user","project"]`. Rejected — security and reproducibility concerns outweigh any convenience gain.

### D6: Remove `system_prompt` from `build_agent`

**Decision:** `build_agent` no longer accepts a `system_prompt` parameter. The SDK reads skill prompts from SKILL.md files in the session sandbox; there is no separate system prompt.

**Rationale:** A hand-crafted system prompt and native SKILL.md prompts would both be injected into the same context window, potentially conflicting or duplicating instructions. Removing the system prompt parameter eliminates this ambiguity and makes the call site unambiguous: the agent's instructions come exclusively from the skills the user has enabled.

**Alternative considered:** Keep `system_prompt` as an optional override for a brief preamble. Rejected — the right place for a global preamble is a dedicated skill (e.g., `system-context`) that can be updated through the normal artifact pipeline.

### D7: `$CLAUDE_SKILL_DIR` in scripts — document as authoring requirement

**Decision:** Skills with `scripts/` MUST use `$CLAUDE_SKILL_DIR` for absolute path references within their scripts. This requirement is documented in `docs/SKILL-AUTHORING.md` as part of this change.

**Rationale:** When the SDK invokes a script via the `Bash` tool, the working directory is the session sandbox root (`session_dir`), not the skill directory. A script that uses a relative path like `./helpers.py` will fail. `$CLAUDE_SKILL_DIR` is set by the SDK to the absolute path of the skill directory in the session sandbox, providing the only reliable path anchor. Documenting this prevents a class of silent bugs in skill authoring.

### D8: `manifest.json` replaces glob-based skill discovery in the app

**Decision:** `load_config_from_volume` reads `manifest.json` (written by `build-artifact.sh`) to enumerate skills and their metadata. It no longer uses `artifact_dir.rglob("SKILL.md")` to discover skills.

**Rationale:** Glob discovery is order-dependent, cannot carry metadata (`has_scripts`, `has_references`, `plugin`), and would silently include partial or malformed skill directories. A manifest written at build time is authoritative: if a skill directory exists in the artifact but is not in the manifest, it is ignored. This makes the loader's behaviour predictable and testable without filesystem mocking.

**Alternative considered:** Keep glob discovery and infer `has_scripts`/`has_references` by checking subdirectory existence at load time. Rejected — adds filesystem I/O on every hot-reload check and makes the loader responsible for skill validity decisions that belong at build time.

## Risks / Trade-offs

**[Risk] Skill copy on every cache miss adds latency to agent spawn**
→ Mitigation: Skills are small (SKILL.md + a few scripts/references); `shutil.copytree` for 5-10 skills is sub-100ms. File restore from Volume (existing) dominates spawn latency. Skill copy is bounded by skill count, which is controlled by the artifact pipeline.

**[Risk] Stale skill content in session sandbox after hot-reload**
→ Mitigation: Skills are copied at spawn time from the current `SkillsConfig.skills[name].path`. Existing in-pool agents retain their spawned skill set for their TTL lifetime (max 30 minutes). This is acceptable — agents have a short TTL and users can manually evict by deleting the conversation. A future change could force-evict all pool entries on config reload.

**[Risk] `user_skill_prefs` rows become orphaned when skills are removed from the artifact**
→ Mitigation: `PATCH /api/preferences/skills/{skill_name}` validates against current `SkillsConfig.skills` and returns 404 for unknown names. Orphaned rows for removed skills are harmless — `get_user_skill_prefs` intersects the prefs set with the current skill set, so removed skills are never copied. A periodic cleanup job is a future concern.

**[Risk] `shutil.copytree` fails if the artifact directory is removed mid-copy (Volume remount)**
→ Mitigation: The copy is wrapped in a try/except in `get_or_create`; failure raises `RuntimeError` and surfaces as a 503, same as any other agent spawn failure. The artifact directory is only replaced atomically via `latest.json` pointer update — the old directory remains accessible until the next hot-reload.

## Migration Plan

1. Update `build-artifact.sh` to preserve full skill trees and write `manifest.json` (no app code changes yet)
2. Re-publish the artifact to the Volume so `manifest.json` is present (pre-condition for app code changes)
3. Refactor `skills.py` (`SkillsConfig`, `load_config_from_volume`) — all call sites updated in same PR
4. Add Alembic migration for `user_skill_prefs` table
5. Add preferences router and `get_user_skill_prefs` dependency
6. Refactor `build_agent` and `AgentPool.get_or_create` — update `SimpleAgent` to wrap SDK query
7. Update `docs/SKILL-AUTHORING.md` with `$CLAUDE_SKILL_DIR` requirement
8. Run full test suite green gate before merge

**Rollback:** Revert to previous artifact (update `latest.json` to previous version path); revert `skills.py` and `agent_pool.py` to `skill_contents`-based approach. The Alembic migration for `user_skill_prefs` can remain (harmless empty table).

## Open Questions

- **`claude_agent_sdk.query()` streaming interface:** Does `query()` return an async generator of event dicts compatible with the existing SSE event format (`text_delta`, `tool_use`, `tool_result`, `done`)? The `SimpleAgent.stream()` method must be verified against the actual SDK interface before implementation; a thin adapter layer may be needed.
- **`ClaudeAgentOptions.allowed_tools` exhaustiveness:** Is `["Skill", "Bash", "Read", "Write"]` the complete set needed, or should `Edit` and `Glob` also be included? To be confirmed against SDK documentation during implementation.
- **Volume artifact path on Databricks:** Is the Volume artifact unpacked to a local filesystem path accessible to the app process, or does it require streaming reads via `WorkspaceClient.files`? If the latter, the `SkillDefinition.path` approach must be replaced with a download-to-tmp step in `load_config_from_volume`.
