## Why

The current eval system requires manually maintaining `evals/test-cases/skill-routing.yaml` — every time a skill is added or its trigger description changes, a developer must hand-write new YAML entries. This creates duplication with Anthropic's `skill-creator` tool, which already produces a per-skill `evals/evals.json` during skill authoring. By treating `evals.json` as the source of truth and generating routing YAML automatically, we eliminate the manual step, enable the skill-creator optimization loop to run locally against committed eval data, and give the catalog-level CI gate a composable per-plugin structure as the marketplace grows.

## What Changes

- Add `evals/evals.json` to every existing skill under `plugins/` using the Anthropic skill-creator format: `[{query: str, should_trigger: bool}]`
- Add `evals/scripts/generate-routing-tests.py` — walks all `plugins/*/skills/*/evals/evals.json`, extracts `should_trigger: true` entries, and emits:
  - Per-plugin YAML: `evals/test-cases/<plugin-name>.yaml`
  - Stitched catalog YAML: `evals/test-cases/all.yaml` (default for CI)
- **BREAKING**: `evals/test-cases/skill-routing.yaml` is replaced by the generated `all.yaml`; the old file is deleted
- Update `Makefile` so `make evals` uses `all.yaml` and `make evals PLUGIN=<name>` uses the per-plugin YAML
- Update `CLAUDE.md` and `docs/SKILL-AUTHORING.md` to document that new skills must include `evals/evals.json`
- Update `scripts/validate-skill.sh` to warn (not error) when `evals/evals.json` is missing from a skill

## Capabilities

### New Capabilities
- `per-skill-evals`: Per-skill `evals/evals.json` format committed alongside `SKILL.md`; convention for what the file must contain and how skill-creator populates it
- `routing-test-generator`: `generate-routing-tests.py` script that derives per-plugin and all-catalog routing YAML from per-skill `evals.json` files

### Modified Capabilities
- `catalog-routing-gate`: The existing CI routing gate now consumes generated YAMLs instead of a manually maintained file; adds per-plugin scoping via `PLUGIN=` Makefile variable

## Impact

- **`evals/test-cases/skill-routing.yaml`**: Deleted (replaced by generated `all.yaml`)
- **`evals/test-cases/`**: New per-plugin YAMLs + `all.yaml` (generated, committed or gitignored — TBD in design)
- **`evals/scripts/generate-routing-tests.py`**: New script
- **`plugins/*/skills/*/evals/evals.json`**: New file in every skill (10 skills currently)
- **`Makefile`**: `evals` and `evals-*` targets updated
- **`scripts/validate-skill.sh`**: New warning for missing `evals/evals.json`
- **`CLAUDE.md`**, **`docs/SKILL-AUTHORING.md`**: Updated authoring guidance
- No changes to `evals/src/skill_evals/runner.py` — the runner is unchanged
