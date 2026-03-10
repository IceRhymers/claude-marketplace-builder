## Why

The eval runner currently runs each test to full completion — after the model invokes the target skill, the skill's workflow executes for several more turns, reads files, potentially runs scripts, and produces real output before the runner records a result. For routing evals this is entirely wasted work: the only thing being measured is whether the correct skill was invoked, not what it produced. The full run wastes API tokens, adds 30–180 seconds per test, and risks creating real side effects (file writes, external API calls) inside the eval harness.

## What Changes

- Modify `evals/src/skill_evals/runner.py` to check the pass condition **inline during streaming**, immediately after each `Skill` ToolUseBlock is received
- When the pass condition is met, `break` out of the `async for` loop over the Agent SDK generator — the skill is never actually executed
- The three pass-condition modes short-circuit independently:
  - `expected_skill` — stop as soon as that skill appears in the invoked set
  - `expected_skills` (AND) — stop as soon as all required skills have been invoked
  - `expected_skill_one_of` (OR) — stop as soon as any one of the listed skills appears
- Tests with no expected skill (testing that nothing is invoked) still run to completion — there is no early pass condition to satisfy
- Default `timeout` reduced from 180s to 30s, since passing tests now complete in a single model turn
- No changes to YAML format, generated test cases, or any other file

## Capabilities

### Modified Capabilities
- `eval-runner`: The routing eval runner stops as soon as the pass condition is satisfied rather than running the full skill workflow. Fail-path behavior is unchanged — tests that never invoke the expected skill still exhaust `max_turns` before recording a fail.

## Impact

- **`evals/src/skill_evals/runner.py`**: Pass-condition check moved inline into the streaming loop; `break` added on pass; default timeout reduced to 30s
- **`evals/src/skill_evals/runner_test.py`** (or equivalent): Tests updated to cover early-exit behavior
- No other files changed
