## Context

The repo currently has two separate eval concerns that are manually kept in sync:
1. **Authoring evals** — not present; skill-creator produces `evals/evals.json` per-skill but those files are never committed to the repo
2. **Routing gate** — `evals/test-cases/skill-routing.yaml` with hand-written entries, run via `make evals`

The runner (`skill_evals/runner.py`) is correct and unchanged. The problem is purely in the data pipeline: how test cases get into the YAML the runner consumes.

There are 10 skills across 7 plugins. None currently have committed `evals/evals.json` files.

## Goals / Non-Goals

**Goals:**
- Single source of truth: per-skill `evals/evals.json` is the only place routing test prompts are authored
- `generate-routing-tests.py` derives all runner-compatible YAMLs automatically
- `make evals` works exactly as today, just consuming `all.yaml` instead of `skill-routing.yaml`
- Per-plugin scoping: `make evals PLUGIN=databricks-skills` runs only that plugin's tests
- Skill authors get a validated, documented format for writing evals that skill-creator can also write
- `validate-skill.sh` warns when a skill is missing `evals/evals.json`

**Non-Goals:**
- Changing the runner or its YAML input format
- Publishing the CLI to PyPI (future work)
- Integrating skill-creator's description optimizer loop (future work)
- Output quality / LLM-judge evals (future work)
- Automating plugin assignment for new skills (future work)

## Decisions

### D1: Generated YAMLs are committed to the repo (not gitignored)

Generated files (`evals/test-cases/*.yaml`) are committed so CI can run without needing Python/uv to generate them first, and so diffs are visible in PRs. The generator runs as a pre-commit step and in a separate "generate" make target. Developers run `make evals-generate` after changing any `evals.json`; CI validates that generated files are up-to-date.

**Alternative considered:** Gitignore generated files, always generate in CI before running. Rejected because it adds a required CI step and makes YAML diffs invisible in PRs.

### D2: evals.json format matches Anthropic's skill-creator exactly

```json
[
  {"query": "Trace upstream lineage for main.sales.orders", "should_trigger": true},
  {"query": "What is the weather today?", "should_trigger": false}
]
```

Both `should_trigger: true` and `should_trigger: false` entries are stored. The generator uses only `true` entries for routing test cases. The `false` entries are preserved for future use by the description optimizer (when run_loop.py is wired in).

**Alternative considered:** Only store `should_trigger: true` entries. Rejected because it throws away negative examples that skill-creator needs for description optimization.

### D3: Generated routing test name is derived as `<skill-name>-<slug-of-query>`

Each `should_trigger: true` entry in a skill's `evals.json` becomes one routing test case:
```yaml
- name: databricks-lineage-trace-upstream-lineage-for
  prompt: "Trace upstream lineage for main.sales.orders"
  expected_skill: databricks-lineage
```

The name is `<skill-name>-<first-5-words-of-query-slugified>` truncated to keep YAML readable.

**Alternative considered:** Numeric suffixes (`databricks-lineage-1`, `databricks-lineage-2`). Rejected because name collisions are harder to debug and names are not self-documenting.

### D4: `all.yaml` stitches per-plugin YAMLs via YAML merge, not include

The generator writes all entries into `all.yaml` directly (not YAML anchors or `!!include` which are non-standard). Per-plugin YAMLs are subsets of `all.yaml`. This keeps the runner's YAML parsing unchanged.

### D5: `skill-routing.yaml` is deleted, not kept as alias

The old file is deleted and the Makefile `evals` target updated to use `all.yaml`. There is no backward-compat alias. The migration is one-time and the test coverage is immediately equivalent (existing `skill-routing.yaml` prompts seed the initial `evals.json` files).

### D6: validate-skill.sh warns (not errors) on missing evals.json

Missing `evals/evals.json` is a warning, not a hard error, during this transition. After all existing skills are seeded, this can be promoted to an error in a follow-up.

## Risks / Trade-offs

- **[Generated YAML diffs are noisy in PRs when many skills change]** → Acceptable; the signal (which prompts changed) is exactly what reviewers should see. A custom PR template note can flag this.
- **[Query slug collisions in test names]** → First-5-words slugification is collision-resistant for natural language but not guaranteed. The generator detects duplicates and appends a counter suffix.
- **[skill-creator evals.json may have different field names in future Anthropic updates]** → Format is simple (`query`, `should_trigger`). If Anthropic adds fields, the generator ignores unknown fields. If they rename core fields, the generator breaks visibly at generation time, not silently at test time.
- **[Negative examples (should_trigger: false) must be maintained accurately]** → False entries are not validated by any automated test today. They become valuable only when the description optimizer is wired in. For now, skill authors are responsible for their accuracy.

## Migration Plan

1. Seed `evals/evals.json` for all 10 existing skills using their current `skill-routing.yaml` prompts as `should_trigger: true` entries; add 1-2 `should_trigger: false` entries per skill for basic negative coverage
2. Write and validate `generate-routing-tests.py`
3. Run generator → produces `all.yaml` and per-plugin YAMLs
4. Verify generated `all.yaml` produces identical test results to old `skill-routing.yaml`
5. Delete `skill-routing.yaml`, update Makefile, update docs
6. Commit everything in one PR on `feat/skill-evals-workflow`

**Rollback:** Restore `skill-routing.yaml` from git history and revert Makefile change. Generator and `evals.json` files can remain without breaking anything.
