## MODIFIED Requirements

### Requirement: Runner stops as soon as the pass condition is met
`run_prompt_and_collect_skills()` SHALL break out of the async generator loop immediately after the pass condition is satisfied — that is, after the invoked skill set meets the test's expected outcome. The skill's own workflow SHALL NOT execute during a routing eval.

The pass condition is checked after each `Skill` ToolUseBlock is received, using the same suffix-stripping matching logic (`skill_matches()`) as the existing post-run evaluation.

#### Scenario: expected_skill — stops on first matching invocation
- **WHEN** a test has `expected_skill: databricks-lineage`
- **AND** the model emits `ToolUseBlock(name="Skill", input={skill: "databricks-lineage"})` in turn 1
- **THEN** the runner breaks out of the generator immediately
- **AND** no further turns execute
- **AND** the test is recorded as PASS

#### Scenario: expected_skill — does not stop on non-matching intermediate invocations
- **WHEN** a test has `expected_skill: databricks-lineage`
- **AND** the model invokes `onboarding` on turn 1, then `databricks-lineage` on turn 2
- **THEN** the runner does NOT stop after turn 1 (wrong skill)
- **AND** the runner stops after turn 2 (correct skill found)
- **AND** the test is recorded as PASS

#### Scenario: expected_skills AND — stops only when all required skills have appeared
- **WHEN** a test has `expected_skills: [databricks-lineage, databricks-workspace-files]`
- **AND** `databricks-lineage` is invoked on turn 1
- **THEN** the runner does NOT stop (second required skill not yet seen)
- **AND** when `databricks-workspace-files` is invoked on turn 2, the runner stops immediately
- **AND** the test is recorded as PASS

#### Scenario: expected_skill_one_of OR — stops on first matching invocation from the list
- **WHEN** a test has `expected_skill_one_of: [databricks-lineage, databricks-workspace-files]`
- **AND** `databricks-lineage` is invoked on turn 1
- **THEN** the runner stops immediately
- **AND** the test is recorded as PASS without waiting for the second skill

#### Scenario: no expected skill — runs to completion
- **WHEN** a test has no `expected_skill`, `expected_skills`, or `expected_skill_one_of`
- **THEN** the runner does NOT apply early exit logic
- **AND** the generator runs to completion (up to `max_turns`)
- **AND** the test passes if no skill was invoked, fails otherwise

#### Scenario: pass condition never met — runs to max_turns then records fail
- **WHEN** a test has `expected_skill: databricks-lineage`
- **AND** the model never invokes `databricks-lineage` within `max_turns`
- **THEN** the runner exhausts the generator naturally
- **AND** the test is recorded as FAIL with `actual: "<whatever was invoked or null>"`

---

### Requirement: skill_matches() suffix logic is preserved for early-exit checks
The early-exit pass condition SHALL use the same `skill_matches()` helper as the existing evaluation logic, so that both prefixed (`plugin:skill`) and unprefixed (`skill`) names match correctly.

#### Scenario: prefixed skill name matches unprefixed expected
- **WHEN** `expected_skill: databricks-lineage`
- **AND** the model invokes `icerhymers-databricks-skills:databricks-lineage`
- **THEN** the early-exit check fires (match found via suffix stripping)
- **AND** the test records PASS

---

### Requirement: Default timeout reduced to 30s
The `--timeout` CLI flag default SHALL be 30 seconds (previously 180). A passing test exits in one model turn (typically under 10 seconds); 30s provides headroom for network latency without the 3-minute wait that was appropriate for full skill execution.

The `--timeout` flag SHALL still be overridable on the CLI for callers with unusual requirements.

#### Scenario: passing test completes well within 30s
- **WHEN** the model invokes the expected skill on turn 1
- **THEN** the test completes in the time of a single API round-trip
- **AND** no timeout is triggered

#### Scenario: timeout still applies to fail-path tests
- **WHEN** the model does not invoke the expected skill and `max_turns` is not reached before `timeout`
- **THEN** the test is recorded as a timeout failure with `error: "Timed out after 30s"`
