---
name: guard-setup
description: >
  Explains the destructive-guard plugin: what commands it blocks, how to tune
  rules.conf (add/remove rules, change protected branches, use the override token),
  how to check the audit log, and how to diagnose false positives.
  Use when an operator asks how to configure the destructive command guard, why
  a command was blocked, or how to allow a specific command the guard is blocking.
user-invocable: true
---

# destructive-guard configuration

The `destructive-guard` plugin is a `PreToolUse` hook that blocks unambiguously dangerous Bash commands before the model can execute them. It is pure bash + `jq`, has no network calls, and **fails open**: a malformed `rules.conf`, a missing `jq` binary, or any internal error allows the command through. A guardrail that breaks the agent is a guardrail that gets uninstalled within a day.

## What it blocks (out of the box)

Two severities:

- **HARD_DENY** — patterns that are essentially never legitimate from an autonomous coding agent. Examples: `rm -rf /`, `rm -rf ~/projects/...`, force-push to a protected branch (`main`/`master`/`prod`/`production`), `DROP TABLE`, `TRUNCATE TABLE`, `kubectl delete namespace prod`, `aws s3 ... --recursive s3://`, `curl ... | bash`, `cat ~/.ssh/id_rsa`, `chmod +s`, raw writes to `/dev/sd*`/`/dev/nvme*`.
- **SOFT_DENY** — patterns that are usually destructive but have legitimate edge cases. Examples: `rm -rf` (CWD-scoped — only blocks when the path escapes the project directory), `git clean -fd`, `pkill -9`, `kill -9 1`. These deny with a "here's the safer alternative" suggestion.

`git push --force` is in HARD_DENY, but `git push --force-with-lease` short-circuits the rule and is always allowed — the guard recognises the safe form.

## File layout

```
plugins/destructive-guard/
  scripts/
    guard.sh       # Hook script. Do NOT edit unless changing CORE behaviour.
    rules.conf     # Tunable ruleset. THIS is what you edit.
```

## `rules.conf` format

Sectioned plain text. Sections are introduced by `## SECTION: NAME` markers.

- `## SECTION: SETTINGS` — `KEY=value` pairs.
  - `OVERRIDE_TOKEN_PATTERN=DG-OK-[a-f0-9]{6}` — regex for the per-command override token.
  - `PROTECTED_BRANCHES=main,master,prod,production` — interpolated as a regex alternation into rules that contain the `__PROTECTED_BRANCHES__` token.
  - `PROTECTED_NAMESPACES=prod,production,kube-system` — same, for `__PROTECTED_NAMESPACES__`.
  - `SAFE_PATH_PREFIXES=/tmp/,/var/tmp/` — paths under these are always allowed for CWD-scoped rules.
- `## SECTION: HARD_DENY` and `## SECTION: SOFT_DENY` — one rule per line:

  ```
  <extended-regex>|<short reason>|<category>
  ```

  Categories: `disk`, `git`, `git-force`, `db`, `cloud`, `creds`, `system`, `evasion`, `cwd-scoped`. The `git-force` category is special — guard.sh skips the rule when `--force-with-lease` is in the command. The `cwd-scoped` category (used in SOFT_DENY) only fires when the command's first path argument escapes the project directory.
- `## SECTION: CWD_SCOPED` — marker section, no rules of its own; documents the cwd-scoping behaviour.

Lines starting with `#` are comments. Blank lines are ignored.

## Common operator tasks

### Disable a rule

Comment it out by prefixing with `#`. Example — allow `pkill -9`:

```diff
- \bpkill\s+-9\b|pkill -9 (uncatchable kill)|system
+ # \bpkill\s+-9\b|pkill -9 (uncatchable kill)|system
```

`guard.sh` re-reads `rules.conf` on every invocation, so the change takes effect immediately. No restart.

### Add a new rule

Append to the appropriate `## SECTION:` block. Example — block `vault delete` against a prod path:

```
\bvault\s+delete\s+secret/prod/|vault secret delete in prod|cloud
```

Keep regexes ERE-compatible (`grep -E`). Avoid PCRE features (no `(?!...)`, no `\d`).

### Change protected branches or namespaces

Edit `## SECTION: SETTINGS`:

```
PROTECTED_BRANCHES=main,master,prod,production,release,trunk
PROTECTED_NAMESPACES=prod,production,kube-system,live
```

Both lists are interpolated wherever `__PROTECTED_BRANCHES__` / `__PROTECTED_NAMESPACES__` appears in a rule pattern.

### Override token (one-shot bypass)

Every deny message includes a token of the form `DG-OK-<6 hex chars>`. Re-issuing the same command with the token appended (typically in a shell comment) bypasses **all** guard checks for that single invocation:

```
psql -c "DROP TABLE users;"                          # blocked, token DG-OK-a1b2c3 returned
psql -c "DROP TABLE users; -- DG-OK-a1b2c3"          # allowed, logged as OVERRIDE
```

The check is presence-only — any string matching `OVERRIDE_TOKEN_PATTERN` anywhere in the command unlocks it. The token is a UX gate, not a cryptographic one; the point is to force an explicit "yes, I meant it" loop on the model. Operators wanting stricter overrides can change the prefix per deployment:

```
OVERRIDE_TOKEN_PATTERN=ACME-PROD-OK-[a-f0-9]{6}
```

## Audit log

All blocks and overrides append to `~/.claude/destructive-guard.log`, tab-separated:

```
<iso-timestamp>\t<session_id>\t<HARD|SOFT|OVERRIDE>\t<category>\t<reason>\t<command snippet>
```

Tail it to see what the agent has been blocked from doing recently:

```
tail -f ~/.claude/destructive-guard.log
```

## Diagnosing false positives

1. **Find the matching rule.** The deny message names the reason. Grep `rules.conf` for it. The matching regex is what blocked the command.
2. **Pick a fix:**
   - **One-time pass** — re-issue with the override token from the deny message.
   - **Permanent pass for this project** — comment the rule out, or narrow the pattern (add a path scope, exclude a known-safe form).
   - **Permanent pass org-wide** — patch the rule and submit a PR upstream.
3. **Verify.** `guard.sh` re-reads `rules.conf` on each invocation — no restart. Run any benign command to confirm the agent is unblocked.

## When NOT to add a rule

The guard catches **unambiguous catastrophes**, not style or hygiene issues. Push back on rules that would have a >5% false-positive rate against real dev workflows — a guardrail that fires on legitimate work gets disabled within a day, and then it can't catch the real catastrophe. Style enforcement belongs in repo-level pre-commit hooks; supply-chain checks belong in lockfile-aware tools (Socket, Snyk); long-command heuristics belong nowhere.
