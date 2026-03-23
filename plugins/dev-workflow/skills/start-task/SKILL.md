---
name: start-task
description: >
  Runs the OpenSpec TDD workflow for a Kanboard task — writes spec,
  RED tests, GREEN implementation, regression checks, and opens a PR.
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Agent
  - mcp__kanboard__kb_get_task
  - mcp__kanboard__kb_get_all_tasks
  - mcp__kanboard__kb_search_tasks
  - mcp__kanboard__kb_update_task
  - mcp__kanboard__kb_move_task
  - mcp__kanboard__kb_get_columns
  - mcp__kanboard__kb_get_board
  - mcp__kanboard__kb_get_all_comments
  - mcp__kanboard__kb_create_comment
  - mcp__kanboard__kb_get_all_subtasks
  - mcp__kanboard__kb_create_subtask
---

# Start Task — OpenSpec + TDD Workflow

You are executing a structured development workflow. Follow every phase in order. Do not skip phases. Commit after each phase boundary.

## Phase 0: Gather Context

1. **Identify the task.** If the user gave a Kanboard task ID (e.g. `#3`, `task 14`), fetch it with `mcp__kanboard__kb_get_task`. If Kanboard tools are unavailable or the user described the task in words, use that description directly.
2. **Read the repo.** Scan the project to understand:
   - Language / framework (check `package.json`, `pyproject.toml`, `Makefile`, `Cargo.toml`, etc.)
   - Existing test infrastructure (test directories, test runner config)
   - Key source files related to the task
   - Any existing `openspec/` directory
3. **Move the Kanboard task** to the "In Progress" column if Kanboard tools are available. First call `mcp__kanboard__kb_get_columns` for the project to find the correct column ID, then `mcp__kanboard__kb_move_task`.

## Phase 1: Write the OpenSpec

Create the spec file at `openspec/specs/<task-slug>/spec.md` where `<task-slug>` is a kebab-case name derived from the task title.

The spec MUST contain these sections:

```
# <Task Title>

## Summary
One-paragraph description of what this task delivers.

## Acceptance Criteria
- [ ] AC1: ...
- [ ] AC2: ...
- [ ] AC3: ...

## TDD Phases

### Phase RED — Write Failing Tests
For each AC, list the test(s) to write:
- Test: `test_<name>` — asserts <behavior>
- Test: `test_<name>` — asserts <behavior>

### Phase GREEN — Implement
For each AC, describe the minimal implementation:
- Implement <component> to satisfy AC1
- Implement <component> to satisfy AC2

### Phase REFACTOR (optional)
Any cleanup, extraction, or performance work after GREEN passes.

## Files to Touch
- `src/...`
- `tests/...`
```

Commit the spec: `git add openspec/ && git commit -m "openspec: add spec for <task-slug>"`

## Phase 2: RED — Write Failing Tests

1. Write all tests listed in the spec's RED section. Place them in the project's conventional test directory.
2. Stage and commit the tests: `git add tests/ && git commit -m "red: add failing tests for <task-slug>"`
3. Run the full test suite to confirm:
   - The NEW tests fail (this is expected and required)
   - All EXISTING tests still pass (no regressions introduced by test code alone)
4. If existing tests also fail, investigate immediately — your test file may have import side effects or syntax errors. Fix before proceeding.

## Phase 3: GREEN — Implement

1. Write the minimum code to make all failing tests pass. Follow the spec's GREEN section.
2. After implementation, run the full test suite.
3. If all tests pass (both new and existing): commit with `git commit -m "green: implement <task-slug>"`
4. If tests still fail: iterate on the implementation. Do not move on until the suite is fully green.

## Phase 4: REFACTOR (optional)

If the spec has a REFACTOR section or you see clear improvements:
1. Refactor while keeping tests green.
2. Run full suite after each change.
3. Commit: `git commit -m "refactor: clean up <task-slug>"`

## Phase 5: Finalize

1. Run the full test suite one final time. Report the results.
2. If Kanboard is available, move the task to the "Review" column.
3. Push the branch and open a PR targeting `main` (or `master`, whichever exists).
4. Add a comment to the Kanboard task with the PR URL using `mcp__kanboard__kb_create_comment`.
5. Report the PR URL to the user.

## Important Rules

- **Never skip RED.** Tests must exist and fail before you write implementation code.
- **Commit at phase boundaries.** The git history should clearly show spec → red → green → refactor.
- **Detect the test runner.** Check for `Makefile` (`make test`), `pytest.ini`/`pyproject.toml` (`pytest`), `package.json` (`npm test`), `Cargo.toml` (`cargo test`), etc. Use whatever the project already uses.
- **Use Agent tool for parallelism** when writing tests for independent ACs, or when implementing independent components.
- **If the task is ambiguous**, ask the user for clarification before writing the spec. Do not guess at acceptance criteria.
