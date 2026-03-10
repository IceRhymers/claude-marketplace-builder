## Context

`runner.py` calls `query()` from the Agent SDK, which is an async generator that yields `AssistantMessage`, `ToolResultMessage`, and `ResultMessage` objects as they stream from the underlying `claude` subprocess. Today the runner consumes the entire generator and only evaluates pass/fail after the `ResultMessage` (end of conversation).

The routing decision is made by the model in its **first substantive turn**: it reads the prompt, decides which skill applies, and emits a `ToolUseBlock(name="Skill", input={skill: "<name>"})` inside an `AssistantMessage`. At this point the routing eval is already determinable. Everything after — the skill loading, tool executions, follow-up turns — is irrelevant to routing correctness and should not run.

## Goals / Non-Goals

**Goals:**
- Stop consuming the async generator as soon as the pass condition is satisfied
- Never allow the skill's own workflow to execute during a routing eval
- Support all three existing pass-condition modes (single, AND, OR)
- Unchanged behavior for tests with no expected skill

**Non-Goals:**
- Changing the YAML test-case format
- Changing how fail cases are handled (still run to max_turns)
- Adding new eval modes
- Changing behavior for integration tests that intentionally run full workflows

## Decisions

### D1: The break happens at the outer async-for level, not the inner block loop

The inner loop iterates over `message.content` blocks. A `break` there only exits the block loop, not the message loop. The correct structure is a flag (`_pass_met`) set inside the inner loop, then checked with a `break` immediately after the inner loop exits:

```python
_pass_met = False
async for message in query(...):
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if block.name == "Skill":
                skills_invoked.append(...)
                if _check_pass(skills_invoked, expected):
                    _pass_met = True
                    break  # exits inner block loop
    if _pass_met:
        break  # exits outer async-for, closes generator
```

**Alternative considered:** Raising a custom exception inside the inner loop to unwind both levels. Rejected — exception-as-control-flow is harder to read and suppresses normal generator cleanup.

### D2: Pass-condition check is extracted into a standalone helper

`_check_pass(skills_invoked, test_case)` returns `True` as soon as the pass condition is satisfied, using the same `skill_matches()` suffix-stripping logic that exists today. This makes the inline check readable and keeps it consistent with the post-run evaluation logic (which is removed once early exit is in place).

### D3: No-expected-skill tests are explicitly excluded from early exit

If `test.expected_skill`, `test.expected_skills`, and `test.expected_skill_one_of` are all absent/empty, the test is asserting that NO skill is invoked. Checking "pass condition met after each skill call" doesn't apply — the pass condition can only be confirmed at the end of the run. These tests run to full completion as today.

### D4: Default timeout reduced to 30s

With early exit, a passing test completes in one model turn (typically 3–8 seconds). 180s was sized for full skill execution. 30s is a comfortable bound for a single routing turn plus network latency. Fail-path tests (model never invokes the right skill) still benefit from a lower bound — `max_turns` caps runaway conversation, and 30s is ample for that.

The `--timeout` CLI flag remains, so callers can override if needed.

### D5: `max_turns` stays at 5 (not reduced to 2)

While most routing decisions happen on turn 1, some models may reason briefly before invoking a skill. `max_turns=5` gives headroom without being expensive, since early exit fires as soon as the skill appears regardless of turn count. Reducing to 2 risks false negatives on models that legitimately take 2 turns to reach a routing decision.

## Affected Code

```
evals/src/skill_evals/runner.py
  run_prompt_and_collect_skills()   — add _check_pass helper, add _pass_met flag + break
  run_test()                        — remove now-redundant post-run pass evaluation block
                                      (the result is already known from the streaming phase)
  main() / argparse                 — change --timeout default from 180 to 30
```

No other files.
