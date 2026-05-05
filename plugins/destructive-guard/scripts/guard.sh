#!/usr/bin/env bash
# destructive-guard hook script.
#
# PreToolUse hook on the Bash tool. Reads the hook payload from stdin, applies
# HARD_DENY then SOFT_DENY rules from rules.conf, and either:
#   - emits empty stdout + exits 0 (allow), or
#   - emits a permissionDecision=deny JSON object (block + reason to model).
#
# Contract:
#   stdin : Claude Code hook payload JSON.
#   stdout: empty (allow) or hook-decision JSON (block).
#   exit  : always 0. We FAIL OPEN on any internal error — a broken guardrail
#           must never break the agent.

set -u  # NB: NOT -e. We explicitly handle errors and never want to abort non-zero.

# Always exit 0, even if a subshell trips ERR.
allow() { exit 0; }
trap 'exit 0' ERR

# --- Hard prerequisite: jq. If missing, allow. ---
command -v jq >/dev/null 2>&1 || allow

CONF="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/scripts/rules.conf"
[[ -r "$CONF" ]] || allow

LOG_FILE="${HOME}/.claude/destructive-guard.log"

# --- Read hook payload ---
PAYLOAD="$(cat 2>/dev/null || true)"
[[ -z "$PAYLOAD" ]] && allow

CMD="$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
[[ -z "$CMD" ]] && allow

SESSION_ID="$(printf '%s' "$PAYLOAD" | jq -r '.session_id // "unknown"' 2>/dev/null || echo unknown)"
CWD="$(printf '%s' "$PAYLOAD" | jq -r '.cwd // empty' 2>/dev/null || true)"
CWD="${CWD:-${CLAUDE_PROJECT_DIR:-$PWD}}"

# --- Load SETTINGS from rules.conf ---
get_setting() {
  awk -F= -v k="$1" '
    /^## SECTION:/ { in_sec = ($0 ~ "## SECTION: SETTINGS"); next }
    in_sec && $1 == k { sub(/^[^=]*=/, ""); print; exit }
  ' "$CONF"
}

OVERRIDE_PATTERN="$(get_setting OVERRIDE_TOKEN_PATTERN)"
[[ -z "$OVERRIDE_PATTERN" ]] && OVERRIDE_PATTERN='DG-OK-[a-f0-9]{6}'
PROTECTED_BRANCHES="$(get_setting PROTECTED_BRANCHES)"
PROTECTED_BRANCHES="${PROTECTED_BRANCHES:-main,master,prod,production}"
PROTECTED_NAMESPACES="$(get_setting PROTECTED_NAMESPACES)"
PROTECTED_NAMESPACES="${PROTECTED_NAMESPACES:-prod,production,kube-system}"
SAFE_PATH_PREFIXES="$(get_setting SAFE_PATH_PREFIXES)"

# Branch / namespace lists -> regex alternations for token interpolation.
BR_ALT="$(printf '%s' "$PROTECTED_BRANCHES" | tr ',' '|')"
NS_ALT="$(printf '%s' "$PROTECTED_NAMESPACES" | tr ',' '|')"

# --- Logger ---
log_line() {
  # severity, category, reason
  local severity="$1" category="$2" reason="$3"
  mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || return 0
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
  local snippet="${CMD:0:200}"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$ts" "$SESSION_ID" "$severity" "$category" "$reason" "$snippet" \
    >>"$LOG_FILE" 2>/dev/null || true
}

# --- Override token check ---
# Presence-only: a string of OVERRIDE_PATTERN shape anywhere in the command
# downgrades any deny to allow + OVERRIDE log.
HAS_OVERRIDE=0
if printf '%s' "$CMD" | grep -Eq "$OVERRIDE_PATTERN" 2>/dev/null; then
  HAS_OVERRIDE=1
fi

if [[ $HAS_OVERRIDE -eq 1 ]]; then
  log_line "OVERRIDE" "override" "override token present; all checks bypassed"
  allow
fi

# --- Section extractor ---
section() {
  awk -v sec="$1" '
    /^## SECTION:/ { in_sec = ($0 ~ "## SECTION: " sec); next }
    in_sec && /^[^#[:space:]]/ && NF { print }
  ' "$CONF"
}

# --- Path-escape check (for cwd-scoped rules) ---
# Returns 0 (true) if the first path-shaped arg in the command escapes $CWD
# AND is not under any SAFE_PATH_PREFIXES entry.
path_escapes_cwd() {
  local cmd="$1" p resolved
  p="$(printf '%s' "$cmd" | grep -oE '(/[A-Za-z0-9._/~$-]+|~/[A-Za-z0-9._/~$-]*|\$HOME/[A-Za-z0-9._/-]*|\.\./[A-Za-z0-9._/-]*)' 2>/dev/null | head -1)"
  [[ -z "$p" ]] && return 1   # no absolute path -> not escaping
  p="${p//\$HOME/$HOME}"
  p="${p/#\~/$HOME}"
  resolved="$(cd "$CWD" 2>/dev/null && cd "$(dirname "$p")" 2>/dev/null && printf '%s/%s' "$(pwd)" "$(basename "$p")")"
  resolved="${resolved:-$p}"
  [[ "$resolved" == "$CWD"* ]] && return 1
  local IFS=','
  for pre in $SAFE_PATH_PREFIXES; do
    pre="${pre//\$HOME/$HOME}"
    pre="${pre//\$TMPDIR/${TMPDIR:-/tmp}}"
    [[ -z "$pre" ]] && continue
    [[ "$resolved" == "$pre"* ]] && return 1
  done
  return 0
}

# --- Decision emitter (deny) ---
emit_deny() {
  local severity="$1" category="$2" reason="$3" suggestion="$4"
  local msg="[GUARDRAIL/${severity}] Blocked: ${reason}."
  [[ -n "$suggestion" ]] && msg="${msg} ${suggestion}"
  msg="${msg} If intentional, re-issue the command with an override token of the form ${OVERRIDE_PATTERN} appended (e.g. in a comment)."
  log_line "$severity" "$category" "$reason"
  jq -n \
    --arg reason "$msg" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}' \
    2>/dev/null || printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$reason"
  exit 0
}

# --- Rule line parser ---
# A rule line is "<regex>|<reason>|<category>". The regex may itself contain |
# characters (alternation). We split from the RIGHT: category is the last
# field, reason is the second-to-last, and pattern is everything before that.
parse_rule() {
  local line="$1"
  RULE_CATEGORY="${line##*|}"
  local rest="${line%|*}"
  RULE_REASON="${rest##*|}"
  RULE_PATTERN="${rest%|*}"
}

# --- Process HARD_DENY rules ---
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  parse_rule "$line"
  [[ -z "$RULE_PATTERN" ]] && continue
  # Special-case: git-force category — short-circuit if --force-with-lease present.
  if [[ "$RULE_CATEGORY" == "git-force" ]]; then
    if printf '%s' "$CMD" | grep -qE -- '--force-with-lease' 2>/dev/null; then
      continue
    fi
  fi
  # Token interpolation.
  pat="${RULE_PATTERN//__PROTECTED_BRANCHES__/$BR_ALT}"
  pat="${pat//__PROTECTED_NAMESPACES__/$NS_ALT}"
  if printf '%s' "$CMD" | grep -Eq "$pat" 2>/dev/null; then
    emit_deny "HARD" "$RULE_CATEGORY" "$RULE_REASON" ""
  fi
done < <(section HARD_DENY)

# --- Process SOFT_DENY rules ---
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  parse_rule "$line"
  [[ -z "$RULE_PATTERN" ]] && continue
  pat="${RULE_PATTERN//__PROTECTED_BRANCHES__/$BR_ALT}"
  pat="${pat//__PROTECTED_NAMESPACES__/$NS_ALT}"
  if printf '%s' "$CMD" | grep -Eq "$pat" 2>/dev/null; then
    if [[ "$RULE_CATEGORY" == "cwd-scoped" ]]; then
      path_escapes_cwd "$CMD" || continue
    fi
    suggestion=""
    case "$RULE_CATEGORY" in
      git)         suggestion="Safer alternative: use a non-destructive form (e.g. git stash) or scope to a specific path." ;;
      db)          suggestion="Safer alternative: run against a test DSN, wrap in a transaction, or add an explicit WHERE clause." ;;
      cwd-scoped)  suggestion="Safer alternative: scope the path to inside the project directory, or list specific files instead of -r." ;;
      disk)        suggestion="Safer alternative: narrow the scope to specific files." ;;
      system)      suggestion="Safer alternative: target a specific PID or process name without -9." ;;
      *)           suggestion="" ;;
    esac
    emit_deny "SOFT" "$RULE_CATEGORY" "$RULE_REASON" "$suggestion"
  fi
done < <(section SOFT_DENY)

# --- Allow ---
allow
