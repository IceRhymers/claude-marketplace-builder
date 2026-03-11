## NEW Requirements

### Requirement: generate-routing-tests.py walks all plugin skills and emits YAMLs
`evals/scripts/generate-routing-tests.py` SHALL walk all `plugins/*/skills/<skill-name>/evals/evals.json` files, extract every `should_trigger: true` entry, and emit:
- One per-plugin YAML at `evals/test-cases/<plugin-name>.yaml` containing only that plugin's test cases
- One stitched catalog YAML at `evals/test-cases/all.yaml` containing every test case from every plugin

The script SHALL be runnable standalone (`python evals/scripts/generate-routing-tests.py`) and via `make evals-generate`. It SHALL exit non-zero if any `evals.json` file fails to parse.

#### Scenario: Generator produces per-plugin YAML
- **WHEN** `generate-routing-tests.py` is run with two plugins each having one skill with one `should_trigger: true` entry
- **THEN** two per-plugin YAML files are written, each containing only its plugin's test case

#### Scenario: Generator produces all.yaml
- **WHEN** `generate-routing-tests.py` is run against the full `plugins/` tree
- **THEN** `evals/test-cases/all.yaml` contains every `should_trigger: true` entry across all plugins

#### Scenario: Only should_trigger:true entries are included
- **WHEN** a skill's `evals.json` contains both `true` and `false` entries
- **THEN** the generated YAML contains only the `true` entries; `false` entries are silently skipped

#### Scenario: Skills with no evals.json are skipped with a warning
- **WHEN** a skill directory has no `evals/evals.json`
- **THEN** the generator prints `WARN: skipping <skill-path> — missing evals/evals.json` and continues

#### Scenario: Malformed evals.json causes non-zero exit
- **WHEN** any `evals/evals.json` is not valid JSON or is missing required fields
- **THEN** the generator prints an error message and exits with code 1

---

### Requirement: Generated test case names are derived deterministically from skill and query
Each generated test case SHALL have a `name` field derived as `<skill-name>-<first-5-words-of-query-slugified>` (words joined with hyphens, lowercased, non-alphanumeric characters stripped). Names SHALL be truncated so the full name does not exceed 80 characters.

If two entries in the same YAML file would produce the same name, the generator SHALL append a counter suffix (`-2`, `-3`, etc.) to subsequent duplicates.

#### Scenario: Name derived from skill and query
- **WHEN** skill is `databricks-lineage` and query is `"Trace upstream lineage for main.sales.orders"`
- **THEN** generated name is `databricks-lineage-trace-upstream-lineage-for`

#### Scenario: Name collision resolved with counter
- **WHEN** two entries from the same skill produce the same 5-word slug
- **THEN** the first keeps the base name; the second gets `-2` appended

---

### Requirement: Generated YAML format is compatible with the existing runner
Each test case in the generated YAML SHALL have exactly the fields the existing `runner.py` requires:
```yaml
- name: <derived-name>
  prompt: "<query string>"
  expected_skill: <skill-name>
```

No additional fields SHALL be emitted. The `expected_skill` value SHALL match the directory name of the skill (e.g., `databricks-lineage`).

#### Scenario: Runner reads generated YAML without modification
- **WHEN** `runner.py` is pointed at a generated per-plugin or `all.yaml` file
- **THEN** it parses and executes all test cases without errors

---

### Requirement: make evals-generate runs the generator and validates output is up-to-date
`make evals-generate` SHALL run `generate-routing-tests.py` and report any skills that were skipped due to missing `evals.json`. In CI, a separate `make evals-check-generated` target SHALL diff the working-tree YAMLs against a fresh generator run and fail if they differ, ensuring committed YAMLs are never stale.

#### Scenario: evals-check-generated fails on stale YAML
- **WHEN** an `evals.json` is modified but `make evals-generate` has not been re-run
- **THEN** `make evals-check-generated` exits non-zero with a diff showing the stale entries
