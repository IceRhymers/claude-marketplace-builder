## 1. Refactor runner to support early exit

- [x] 1.1 Extract `_check_pass(skills_invoked: list[str], test: TestCase) -> bool` helper — returns `True` when the pass condition for the given test is already satisfied by the current invoked set; returns `False` for tests with no expected skill
- [x] 1.2 Add `_pass_met` flag inside `run_prompt_and_collect_skills()` — set to `True` in the inner block loop immediately after `_check_pass` returns `True`, then `break` out of the inner loop
- [x] 1.3 Add outer `if _pass_met: break` immediately after the inner block loop exits — this closes the async generator and stops the Claude subprocess
- [x] 1.4 Verify the `ResultMessage` collection still works correctly — when early exit fires before a `ResultMessage` arrives, `result_info` will be empty; ensure this is handled gracefully (no KeyError on `session_id`, `total_cost_usd`, etc.)
- [x] 1.5 Remove the now-redundant post-run pass/fail evaluation block from `run_test()` — the pass condition is already resolved during streaming; the `invoked_set` and evaluation logic at the bottom of `run_test()` can be simplified to just use what was returned

## 2. Update default timeout

- [x] 2.1 Change `--timeout` argparse default from `180` to `30` in `main()`
- [x] 2.2 Update the `--timeout` help string to note "default: 30 (reduced from 180 — passing tests now exit after one turn)"

## 3. Tests

- [x] 3.1 Add unit test: `expected_skill` — assert generator is broken after matching skill appears (mock the async generator, verify it received `aclose()` or equivalent)
- [x] 3.2 Add unit test: intermediate non-matching skill does NOT trigger early exit
- [x] 3.3 Add unit test: `expected_skills` AND — does not exit until all required skills seen
- [x] 3.4 Add unit test: `expected_skill_one_of` OR — exits on first match from the list
- [x] 3.5 Add unit test: no expected skill — generator runs to completion, no early exit
- [x] 3.6 Add unit test: prefixed skill name (`plugin:skill`) matches unprefixed `expected_skill` via suffix stripping

## 4. Final verification

- [x] 4.1 Run existing test suite — confirm zero regressions
- [x] 4.2 Confirm `_check_pass` returns `False` for all no-expected-skill tests
- [x] 4.3 Confirm `--timeout` default is 30 in `runner.py` and reflected in `skill-evals --help` output
- [x] 4.4 Commit on `feat/skill-evals-workflow`
