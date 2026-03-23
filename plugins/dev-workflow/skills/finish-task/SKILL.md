---
name: finish-task
description: >
  Finishes the current task — runs regression check, pushes the branch,
  opens a PR, and moves the Kanboard task to Review.
user-invocable: true
allowed-tools:
  - Bash
  - mcp__kanboard__kb_get_task
  - mcp__kanboard__kb_get_all_tasks
  - mcp__kanboard__kb_search_tasks
  - mcp__kanboard__kb_update_task
  - mcp__kanboard__kb_move_task
  - mcp__kanboard__kb_get_columns
  - mcp__kanboard__kb_get_board
  - mcp__kanboard__kb_create_comment
---

# Finish Task

You are wrapping up the current development task. Follow these steps in order.

## Step 1: Run Full Regression Check

Run the project's test suite to confirm everything is green:

1. Detect the test runner (check `Makefile`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod` in that order).
2. Run the full suite.
3. If there are *any* new regressions (tests that should pass but don't), STOP. Report the failures and do not proceed. Tell the user to fix them first.
4. Pre-existing failures are acceptable — note them but continue.

## Step 2: Push the Branch

1. Check the current branch name with `git branch --show-current`.
2. If on `main` or `master`, STOP — tell the user they should be on a feature branch.
3. Push: `git push -u origin <branch-name>`

## Step 3: Open a Pull Request

1. Determine the default branch (`main` or `master`) by checking `git remote show origin` or `git branch -r`.
2. Open a PR using the `gh` CLI:
   ```bash
   gh pr create --title "<task title>" --body "<summary of changes and test results>" --base <default-branch>
   ```
3. Capture and report the PR URL.

## Step 4: Update Kanboard

If Kanboard tools are available and a task ID is known (from the branch name, commit messages, or the user):

1. Get the project columns with `mcp__kanboard__kb_get_columns` to find the "Review" column ID.
2. Move the task to Review with `mcp__kanboard__kb_move_task`.
3. Add a comment to the task with the PR URL using `mcp__kanboard__kb_create_comment`.

If no Kanboard task is associated, skip this step and tell the user.

## Step 5: Report

Tell the user:
- Test results (pass/fail counts)
- PR URL
- Kanboard status (moved to Review, or skipped)

## Rules

- Never force-push.
- Never push to `main`/`master` directly.
- If `gh` CLI is not available, give the user a manual PR URL they can open in the browser.
- If the regression check fails, do not push or open a PR. The task is not finished.
