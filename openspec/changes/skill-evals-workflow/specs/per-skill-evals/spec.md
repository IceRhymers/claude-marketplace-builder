## ADDED Requirements

### Requirement: Every skill directory contains evals/evals.json
Each skill under `plugins/*/skills/<skill-name>/` SHALL contain an `evals/evals.json` file in Anthropic's skill-creator format: a JSON array of objects with `query` (string) and `should_trigger` (boolean) fields. The file MUST contain at least one `should_trigger: true` entry and at least one `should_trigger: false` entry.

#### Scenario: Valid evals.json accepted
- **WHEN** `evals/evals.json` contains `[{"query": "Trace lineage for table X", "should_trigger": true}, {"query": "What is the weather?", "should_trigger": false}]`
- **THEN** `validate-skill.sh` reports no warnings for missing evals

#### Scenario: Missing evals.json triggers warning
- **WHEN** a skill directory exists without `evals/evals.json`
- **THEN** `validate-skill.sh` emits a warning: `WARN: missing evals/evals.json in <skill-path>`

#### Scenario: evals.json with no should_trigger:true entry
- **WHEN** `evals/evals.json` exists but all entries have `"should_trigger": false`
- **THEN** `validate-skill.sh` emits a warning: `WARN: no should_trigger:true entries in <skill-path>/evals/evals.json`

#### Scenario: evals.json with no should_trigger:false entry
- **WHEN** `evals/evals.json` exists but all entries have `"should_trigger": true`
- **THEN** `validate-skill.sh` emits a warning: `WARN: no should_trigger:false entries in <skill-path>/evals/evals.json` (negative examples needed for description optimization)

#### Scenario: Malformed evals.json triggers error
- **WHEN** `evals/evals.json` exists but is not valid JSON or is missing required fields
- **THEN** `validate-skill.sh` emits an error and exits non-zero

---

### Requirement: evals.json is compatible with Anthropic skill-creator
The `evals/evals.json` format SHALL be identical to the format produced and consumed by Anthropic's `skill-creator` plugin, so that skill authors can run `skill-creator`'s description optimization loop locally against committed eval data without format conversion.

#### Scenario: skill-creator can read committed evals.json
- **WHEN** a developer runs skill-creator's `run_eval.py` against a skill with a committed `evals/evals.json`
- **THEN** the script reads the file without errors and runs evaluations correctly

#### Scenario: skill-creator output can be committed directly
- **WHEN** skill-creator writes an `evals/evals.json` to a skill directory
- **THEN** the file can be committed as-is with no transformation required

---

### Requirement: Existing skills are seeded with evals.json on migration
All 10 existing skills SHALL have `evals/evals.json` seeded as part of this change, using their existing `skill-routing.yaml` test prompts as `should_trigger: true` entries plus at least one `should_trigger: false` entry each.

#### Scenario: All existing skills have evals.json after migration
- **WHEN** this change is fully applied
- **THEN** `validate-skill.sh --all` reports no missing-evals warnings for any skill in `plugins/`
