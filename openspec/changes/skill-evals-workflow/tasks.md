## 1. Seed evals.json for all existing skills

- [ ] 1.1 Create `plugins/databricks-skills/skills/databricks-lineage/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [ ] 1.2 Create `plugins/databricks-skills/skills/databricks-workspace-files/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [ ] 1.3 Create `plugins/specialized-tools/skills/lucid-diagram/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [ ] 1.4 Create `plugins/databricks-mcp/skills/mcp-setup/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [ ] 1.5 Create `plugins/budget-checker/skills/budget-setup/evals/evals.json` — seed with 2 `should_trigger:true` entries from `skill-routing.yaml` + 1–2 `should_trigger:false` entries
- [ ] 1.6 Create `plugins/internal-skills/skills/incident-response/evals/evals.json` — 2+ `should_trigger:true` entries + 1–2 `should_trigger:false` entries (no existing routing entries; derive from SKILL.md)
- [ ] 1.7 Create `plugins/internal-skills/skills/onboarding/evals/evals.json` — 2+ `should_trigger:true` entries + 1–2 `should_trigger:false` entries (no existing routing entries; derive from SKILL.md)
- [ ] 1.8 Create `plugins/marketplace-management/skills/update-skills/evals/evals.json` — 2+ `should_trigger:true` entries + 1–2 `should_trigger:false` entries (no existing routing entries; derive from SKILL.md)

## 2. Write generate-routing-tests.py

- [ ] 2.1 Create `evals/scripts/generate-routing-tests.py` — CLI entry point; parse `--plugins-dir` (default `plugins/`) and `--out-dir` (default `evals/test-cases/`) args
- [ ] 2.2 Implement skill walker — glob `<plugins-dir>/*/skills/*/evals/evals.json`, extract plugin name and skill name from path
- [ ] 2.3 Implement test-case name derivation — `<skill-name>-<first-5-words-slug>`, strip non-alphanumeric, truncate to 80 chars, append `-2`/`-3` counter on collision
- [ ] 2.4 Implement per-plugin YAML writer — emit `evals/test-cases/<plugin-name>.yaml` with only that plugin's `should_trigger:true` entries
- [ ] 2.5 Implement all.yaml writer — stitch all per-plugin entries into `evals/test-cases/all.yaml`
- [ ] 2.6 Implement error handling — warn on missing `evals.json`, exit non-zero on malformed JSON or missing required fields
- [ ] 2.7 Verify generated YAML is parseable by `runner.py` — each entry has `name`, `prompt`, `expected_skill`

## 3. Update Makefile

- [ ] 3.1 Add `evals-generate` target — runs `generate-routing-tests.py`
- [ ] 3.2 Add `evals-check-generated` target — re-runs generator into a temp dir and diffs against committed YAMLs; exits non-zero on any diff
- [ ] 3.3 Update `evals` target — change YAML path from `skill-routing.yaml` to `all.yaml` by default
- [ ] 3.4 Add `PLUGIN` variable support to `evals` target — when set, use `evals/test-cases/$(PLUGIN).yaml`; print error and exit non-zero if file does not exist
- [ ] 3.5 Add `evals-generate` as a pre-requisite comment in the `evals` target (documentation only; do NOT make it auto-run to keep CI deterministic)

## 4. Update validate-skill.sh

- [ ] 4.1 Add check for `evals/evals.json` existence — emit `WARN: missing evals/evals.json in <skill-path>` if absent
- [ ] 4.2 Add check for at least one `should_trigger:true` entry — emit `WARN: no should_trigger:true entries in <skill-path>/evals/evals.json`
- [ ] 4.3 Add check for at least one `should_trigger:false` entry — emit `WARN: no should_trigger:false entries in <skill-path>/evals/evals.json`
- [ ] 4.4 Add JSON validity check for `evals.json` — emit error and exit non-zero on malformed JSON

## 5. Run generator and validate output

- [ ] 5.1 Run `make evals-generate` — verify per-plugin YAMLs are created for all plugins that have at least one skill with `evals.json`
- [ ] 5.2 Verify `evals/test-cases/all.yaml` contains at least all prompts that were in the old `skill-routing.yaml`
- [ ] 5.3 Run `make evals` against generated `all.yaml` — confirm all routing tests pass (equivalent coverage to old file)
- [ ] 5.4 Run `make evals-check-generated` — confirm it exits zero when YAMLs are current

## 6. Remove skill-routing.yaml and update docs

- [ ] 6.1 Delete `evals/test-cases/skill-routing.yaml`
- [ ] 6.2 Update `CLAUDE.md` — document that new skills must include `evals/evals.json` with at least one `should_trigger:true` and one `should_trigger:false` entry
- [ ] 6.3 Update `docs/SKILL-AUTHORING.md` — add section on evals format, how to run `make evals-generate`, and how skill-creator's output can be committed as-is
- [ ] 6.4 Run `validate-skill.sh --all` — confirm no missing-evals warnings for any skill in `plugins/`

## 7. Final verification

- [ ] 7.1 Run full test suite — confirm zero regressions
- [ ] 7.2 Confirm `evals/test-cases/skill-routing.yaml` no longer exists in the repository
- [ ] 7.3 Confirm `make evals PLUGIN=databricks-skills` runs only databricks-skills test cases
- [ ] 7.4 Commit all changes on `feat/skill-evals-workflow`
