## Why

The current eval system requires manually maintaining `evals/test-cases/skill-routing.yaml` — every time a skill is added or its trigger description changes, a developer must hand-write new YAML entries. This creates duplication with Anthropic's `skill-creator` tool, which already produces a per-skill `evals/evals.json` during skill authoring. And the current `/build-skill` skill is pure prose guidance — a contributor can bypass evals entirely, scaffold directly into a plugin directory, and accidentally ship a skill that never triggers or silently breaks other skills.

By treating `evals.json` as the source of truth, generating routing YAML automatically, and upgrading `/build-skill` into an enforced end-to-end pipeline, we eliminate manual steps, close the bypass gap, and give contributors a single command that carries them from idea to promoted skill with quality gates throughout.

## What Changes

- Add `evals/evals.json` to every existing skill under `plugins/` using the Anthropic skill-creator format: `[{query: str, should_trigger: bool}]`
- Add `evals/scripts/generate-routing-tests.py` — walks all `plugins/*/skills/*/evals/evals.json`, extracts `should_trigger: true` entries, and emits:
  - Per-plugin YAML: `evals/test-cases/<plugin-name>.yaml`
  - Stitched catalog YAML: `evals/test-cases/all.yaml` (default for CI)
- **BREAKING**: `evals/test-cases/skill-routing.yaml` is replaced by the generated `all.yaml`; the old file is deleted
- Update `Makefile` so `make evals` uses `all.yaml` and `make evals PLUGIN=<name>` uses the per-plugin YAML
- Upgrade `.claude/skills/build-skill/SKILL.md` into a gated pipeline: **Stage → Eval Loop → Promote**
  - Stage: scaffolds to `.claude/skills/staging/<skill-name>/` (gitignored, not distributed)
  - Eval loop: helps write `evals.json`, runs evals, iterates on description until routing passes
  - Promote: moves skill to target plugin, runs validate + evals-generate + version bump automatically
- Update `CLAUDE.md` to mandate `/build-skill` as the ONLY path for new skills; demote manual steps to "migration only"
- Update `scripts/validate-skill.sh` to warn (not error) when `evals/evals.json` is missing from a skill

## Capabilities

### New Capabilities
- `per-skill-evals`: Per-skill `evals/evals.json` format committed alongside `SKILL.md`; convention for what the file must contain and how skill-creator populates it
- `routing-test-generator`: `generate-routing-tests.py` script that derives per-plugin and all-catalog routing YAML from per-skill `evals.json` files
- `skill-development-pipeline`: Upgraded `/build-skill` skill that enforces Stage → Eval Loop → Promote with hard gates; staging area under `.claude/skills/staging/` (gitignored); evals must pass before promotion

### Modified Capabilities
- `catalog-routing-gate`: The existing CI routing gate now consumes generated YAMLs instead of a manually maintained file; adds per-plugin scoping via `PLUGIN=` Makefile variable

## Impact

- **`evals/test-cases/skill-routing.yaml`**: Deleted (replaced by generated `all.yaml`)
- **`evals/test-cases/`**: New per-plugin YAMLs + `all.yaml` (generated, committed)
- **`evals/scripts/generate-routing-tests.py`**: New script
- **`plugins/*/skills/*/evals/evals.json`**: New file in every skill (8 skills currently)
- **`.claude/skills/build-skill/SKILL.md`**: Rewritten as a pipeline orchestrator with stage/eval/promote phases
- **`.claude/skills/staging/`**: New gitignored staging area for in-progress skills
- **`Makefile`**: `evals` and `evals-*` targets updated
- **`scripts/validate-skill.sh`**: New warning for missing `evals/evals.json`
- **`CLAUDE.md`**: `/build-skill` mandatory; manual scaffold steps demoted to migration note
- **`docs/SKILL-AUTHORING.md`**: Updated to match new pipeline flow
- No changes to `evals/src/skill_evals/runner.py` — the runner is unchanged
