---
name: complete-task
description: >
  Completes the current development task — runs the test suite, pushes the
  branch to origin, opens a pull request, and updates the project board.
user-invocable: true
allowed-tools:
  - Bash
  - mcp__kanboard__kb_get_task
  - mcp__kanboard__kb_get_all_tasks
  - mcp__kanboard__kb_update_task
  - mcp__kanboard__kb_move_task
  - mcp__kanboard__kb_get_columns
  - mcp__kanboard__kb_create_comment
---

# Complete Task

Wrap up the current development task by running tests, pushing, opening a PR, and updating the board.

## Step 1: Run Tests

1. Detect the test runner (check `Makefile`, `pyproject.toml`, `package.json` in order).
2. Run the full test suite.
3. If there are new regressions, STOP and report. Do not proceed.

## Step 2: Push Branch

1. Check the current branch: `git branch --show-current`
2. If on `main` or `master`, STOP.
3. Push: `git push -u origin <branch>`

## Step 3: Open Pull Request

```bash
gh pr create --title "<task title>" --body "<summary>" --base main
```

Report the PR URL.

## Step 4: Update Board

Move the associated Kanboard task to the Review column and add a comment with the PR URL.

## Rules

- Never force-push.
- Never push directly to main.
