## 1. Seed evals.json for all existing skills

- [x] 1.1 Create `plugins/databricks-skills/skills/databricks-lineage/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [x] 1.2 Create `plugins/databricks-skills/skills/databricks-workspace-files/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [x] 1.3 Create `plugins/specialized-tools/skills/lucid-diagram/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [x] 1.4 Create `plugins/databricks-mcp/skills/mcp-setup/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [x] 1.5 Create `plugins/budget-checker/skills/budget-setup/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [x] 1.6 Create `plugins/internal-skills/skills/incident-response/evals/evals.json` — 2+ `should_trigger:true` entries + 1–2 `should_trigger:false` entries (no existing routing entries; derive from SKILL.md)
- [x] 1.7 Create `plugins/internal-skills/skills/onboarding/evals/evals.json` — 2+ `should_trigger:true` entries + 1–2 `should_trigger:false` entries (no existing routing entries; derive from SKILL.md)
- [x] 1.8 Create `plugins/marketplace-management/skills/update-skills/evals/evals.json` — 2+ `should_trigger:true` entries + 1–2 `should_trigger:false` entries (no existing routing entries; derive from SKILL.md)

## 2. Write generate-routing-tests.py

- [x] 2.1 Create `evals/scripts/generate-routing-tests.py` — CLI entry point; parse `--plugins-dir` (default `plugins/`) and `--out-dir` (default `evals/test-cases/`) args
- [x] 2.2 Implement skill walker — glob `<plugins-dir>/*/skills/*/evals/evals.json`, extract plugin name and skill name from path
- [x] 2.3 Implement test-case name derivation — `<skill-name>-<first-5-words-slug>`, strip non-alphanumeric, truncate to 80 chars, append `-2`/`-3` counter on collision
- [x] 2.4 Implement per-plugin YAML writer — emit `evals/test-cases/<plugin-name>.yaml` with only that plugin's `should_trigger:true` entries
- [x] 2.5 Implement all.yaml writer — stitch all per-plugin entries into `evals/test-cases/all.yaml`
- [x] 2.6 Implement error handling — warn on missing `evals.json`, exit non-zero on malformed JSON or missing required fields
- [x] 2.7 Verify generated YAML is parseable by `runner.py` — each entry has `name`, `prompt`, `expected_skill`

## 3. Update Makefile

- [x] 3.1 Add `evals-generate` target — runs `generate-routing-tests.py`
- [x] 3.2 Add `evals-check-generated` target — re-runs generator into a temp dir and diffs against committed YAMLs; exits non-zero on any diff
- [x] 3.3 Update `evals` target — change YAML path from `skill-routing.yaml` to `all.yaml` by default
- [x] 3.4 Add `PLUGIN` variable support to `evals` target — when set, use `evals/test-cases/$(PLUGIN).yaml`; print error and exit non-zero if file does not exist
- [x] 3.5 Add `evals-generate` as a pre-requisite comment in the `evals` target (documentation only; do NOT make it auto-run to keep CI deterministic)

## 4. Update validate-skill.sh

- [x] 4.1 Add check for `evals/evals.json` existence — emit `WARN: missing evals/evals.json in <skill-path>` if absent
- [x] 4.2 Add check for at least one `should_trigger:true` entry — emit `WARN: no should_trigger:true entries in <skill-path>/evals/evals.json`
- [x] 4.3 Add check for at least one `should_trigger:false` entry — emit `WARN: no should_trigger:false entries in <skill-path>/evals/evals.json`
- [x] 4.4 Add JSON validity check for `evals.json` — emit error and exit non-zero on malformed JSON

## 5. Run generator and validate output

- [x] 5.1 Run `make evals-generate` — verify per-plugin YAMLs are created for all plugins that have at least one skill with `evals.json`
- [x] 5.2 Verify `evals/test-cases/all.yaml` contains at least all prompts that were in the old `skill-routing.yaml`
- [x] 5.3 Run `make evals` against generated `all.yaml` — confirm all routing tests pass (equivalent coverage to old file)
- [x] 5.4 Run `make evals-check-generated` — confirm it exits zero when YAMLs are current

## 6. Remove skill-routing.yaml and update docs

- [x] 6.1 Delete `evals/test-cases/skill-routing.yaml`
- [x] 6.2 Update `docs/SKILL-AUTHORING.md` — add section on evals format, how to run `make evals-generate`, and how skill-creator's output can be committed as-is
- [x] 6.3 Run `validate-skill.sh --all` — confirm no missing-evals warnings for any skill in `plugins/`

## 7. Rewrite .claude/skills/build-skill/SKILL.md as a pipeline orchestrator

- [x] 7.1 Add staging area to `.gitignore` — add `.claude/skills/staging/` entry
- [x] 7.2 Rewrite Phase 1 (Requirements) — keep intake questions but add "target plugin will be selected at promotion time, not now"
- [x] 7.3 Rewrite Phase 2 (Stage) — scaffold to `.claude/skills/staging/<skill-name>/` instead of directly to plugin; copy from template into staging
- [x] 7.4 Rewrite Phase 3 (Eval Loop) — replace old "add to skill-routing.yaml" step with: create `evals/evals.json`, run `make evals-filter SKILL=<name>` (or equivalent), iterate on description until all entries pass; minimum 2 `true` + 2 `false` entries required to advance
- [x] 7.5 Rewrite Phase 4 (Promote) — move staging dir to selected plugin path, run `validate-skill.sh`, run `make evals-generate`, run `make evals PLUGIN=<plugin>`, bump version in plugin.json + marketplace.json
- [x] 7.6 Update Checklist at bottom of SKILL.md — replace old eval step with evals.json and pipeline gate steps
- [x] 7.7 Add override escape hatch — document "promote anyway" override with warning comment written to SKILL.md frontmatter

## 8. Update CLAUDE.md to enforce pipeline workflow

- [x] 8.1 Replace "Adding a Skill" section step 1 — change from "Use `/build-skill` to create a new skill interactively, or:" to "**All new skills MUST be created via `/build-skill`** — it runs the full Stage → Eval Loop → Promote pipeline"
- [x] 8.2 Demote manual scaffold steps to a collapsed "Advanced / migration only" note — not a first-class option
- [x] 8.3 Replace "Eval Requirements" section — remove reference to `skill-routing.yaml`, document `evals/evals.json` format, minimum entry counts, and `make evals-generate`
- [x] 8.4 Update project structure diagram — add `.claude/skills/staging/` entry with "(gitignored, in-progress skills)" annotation
- [x] 8.5 Update `evals/test-cases/` entry in structure diagram — replace `skill-routing.yaml` with `all.yaml` and `<plugin-name>.yaml` entries

## 9. Final verification

- [x] 9.1 Run full test suite — confirm zero regressions
- [x] 9.2 Confirm `evals/test-cases/skill-routing.yaml` no longer exists in the repository
- [x] 9.3 Confirm `make evals PLUGIN=databricks-skills` runs only databricks-skills test cases
- [x] 9.4 Run `validate-skill.sh --all` — confirm warnings only for skills without `evals/evals.json`
- [x] 9.5 Verify staging area is gitignored — create a test file in `.claude/skills/staging/` and confirm `git status` does not show it
- [x] 9.6 Read through updated `build-skill` SKILL.md end-to-end and confirm all three phases (Stage / Eval Loop / Promote) are clearly described with hard gates between them
- [x] 9.7 Commit all changes on `feat/skill-evals-workflow`
