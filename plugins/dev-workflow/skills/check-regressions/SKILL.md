---
name: check-regressions
description: >
  Runs the full test suite and reports pass/fail counts, identifying
  new regressions versus pre-existing failures.
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# Check Regressions

You are running a regression check on the current project. Follow these steps exactly.

## Step 1: Detect the Test Runner

Look for these files in order and use the first match:

| File | Command |
|---|---|
| `Makefile` with a `test` target | `make test` |
| `pytest.ini` or `pyproject.toml` with `[tool.pytest]` | `pytest --tb=short -q` |
| `package.json` with a `test` script | `npm test` |
| `Cargo.toml` | `cargo test` |
| `go.mod` | `go test ./...` |

If none of these exist, tell the user you could not detect a test runner and ask them to specify one.

## Step 2: Get Baseline Failures

Before running tests, check if there are known failures from the previous commit:

```bash
git stash --include-untracked 2>/dev/null
# run test suite here, capture output
git stash pop 2>/dev/null
```

If `git stash` has nothing to stash (clean working tree), skip the stash/pop and just note that baseline = current HEAD.

## Step 3: Run the Full Test Suite

Run the detected test command. Capture the full output including exit code.

## Step 4: Parse and Report

Report the following clearly:

- **Total tests:** count
- **Passed:** count
- **Failed:** count (list each failing test name)
- **New regressions:** tests that fail now but passed at the previous commit (or "None")
- **Pre-existing failures:** tests that were already failing before your changes (or "None")

## Step 5: Verdict

- If there are *zero new regressions*: report "Regression check: CLEAN" even if there are pre-existing failures (note them separately).
- If there are *new regressions*: report "Regression check: FAILED — N new regression(s)" and list them.

## Rules

- Always run the *full* suite, not a subset.
- Never modify test files or source files during a regression check.
- If tests take longer than 5 minutes, report that and suggest the user run a targeted subset.
- Report raw numbers — do not editorialize about test quality.
