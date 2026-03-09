## MODIFIED Requirements

### Requirement: make evals uses all.yaml by default
The `evals` Makefile target SHALL invoke `runner.py` against `evals/test-cases/all.yaml` instead of `evals/test-cases/skill-routing.yaml`. The old `skill-routing.yaml` file SHALL be deleted; the `evals` target SHALL fail if only the old file exists.

#### Scenario: make evals runs full catalog gate
- **WHEN** `make evals` is invoked with no arguments
- **THEN** `runner.py` executes all test cases from `evals/test-cases/all.yaml`
- **AND** the exit code reflects pass/fail of the full catalog routing gate

#### Scenario: skill-routing.yaml no longer exists
- **WHEN** the migration is applied
- **THEN** `evals/test-cases/skill-routing.yaml` does not exist in the repository
- **AND** `make evals` succeeds using `all.yaml`

---

### Requirement: make evals PLUGIN=<name> runs only that plugin's tests
The `evals` target SHALL accept an optional `PLUGIN=<plugin-name>` variable. When set, `runner.py` SHALL be invoked against `evals/test-cases/<plugin-name>.yaml` instead of `all.yaml`. If the per-plugin YAML does not exist, `make evals PLUGIN=<name>` SHALL print an error and exit non-zero.

#### Scenario: Per-plugin scoped run
- **WHEN** `make evals PLUGIN=databricks-skills` is invoked
- **THEN** `runner.py` executes only the test cases in `evals/test-cases/databricks-skills.yaml`
- **AND** test cases from other plugins are not executed

#### Scenario: Unknown plugin name fails fast
- **WHEN** `make evals PLUGIN=nonexistent-plugin` is invoked
- **THEN** make exits non-zero with a message indicating the YAML file was not found

---

### Requirement: evals/test-cases/skill-routing.yaml is permanently deleted
`evals/test-cases/skill-routing.yaml` SHALL be removed from the repository as part of this change. Its test prompts SHALL be preserved by migrating them into the per-skill `evals/evals.json` files as `should_trigger: true` entries before deletion.

#### Scenario: All old test cases preserved in generated all.yaml
- **WHEN** the migration is complete
- **THEN** every prompt that existed in `skill-routing.yaml` appears as a `should_trigger: true` entry in the corresponding skill's `evals.json`
- **AND** the generated `all.yaml` contains equivalent test cases with equivalent `expected_skill` values

---

### Requirement: CI validates that generated YAMLs are up-to-date
CI SHALL run `make evals-check-generated` before `make evals`. If generated YAMLs are stale (not matching what the generator would produce from current `evals.json` files), CI SHALL fail with a clear message instructing developers to run `make evals-generate` and commit the result.

#### Scenario: CI fails on stale generated YAML
- **WHEN** a developer modifies an `evals.json` but does not re-run `make evals-generate`
- **THEN** CI fails at the `evals-check-generated` step
- **AND** the failure message instructs the developer to run `make evals-generate` and commit

#### Scenario: CI passes when generated YAMLs are current
- **WHEN** all `evals.json` files and generated YAMLs are in sync
- **THEN** `make evals-check-generated` exits zero and CI proceeds to `make evals`
