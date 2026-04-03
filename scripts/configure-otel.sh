#!/bin/bash
set -euo pipefail

# ==============================================================================
# configure-otel.sh — Configure Claude Code OTEL telemetry to Databricks
#
# Fully self-contained. Runs via curl-pipe-bash or locally from the repo.
#
# Usage:
#   curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/configure-otel.sh | bash
#   make configure-otel
#   bash scripts/configure-otel.sh
#
#   bash scripts/configure-otel.sh --uninstall   # Remove OTEL env vars
#   make unconfigure-otel
#
# Computes OTEL env vars from your Databricks credentials and merges them
# into ~/.claude/settings.json. OTEL vars must be present before Claude Code
# starts (SessionStart hooks are too late), so settings.json is the only
# mechanism that works.
#
# Re-run at any time (e.g., after token rotation) to recompute headers.
# ==============================================================================

# Keys written by this script — used by --uninstall to know what to remove
OTEL_KEYS=(
  CLAUDE_CODE_ENABLE_TELEMETRY
  OTEL_METRICS_EXPORTER
  OTEL_EXPORTER_OTLP_METRICS_PROTOCOL
  OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
  OTEL_EXPORTER_OTLP_METRICS_HEADERS
)

main() {
  local SETTINGS_FILE="$HOME/.claude/settings.json"

  if [ "${1:-}" = "--uninstall" ]; then
    check_prerequisites
    remove_settings "$SETTINGS_FILE" "${OTEL_KEYS[@]}"
    echo ""
    echo "  OTEL configuration removed. Restart Claude Code for changes to take effect."
    return
  fi

  # -------------------------------------------------------------------------
  # Prerequisites
  # -------------------------------------------------------------------------

  check_prerequisites

  # -------------------------------------------------------------------------
  # Resolve Databricks credentials
  # -------------------------------------------------------------------------

  local db_host="" db_token="" uc_table
  local use_manual=true

  # Try to detect Databricks CLI profiles
  local profiles_json cli_found
  profiles_json=$(detect_databricks_profiles) && cli_found=0 || cli_found=$?

  local profile_count
  profile_count=$(echo "$profiles_json" | jq 'length' 2>/dev/null) || profile_count=0

  if [ "$cli_found" -eq 0 ] && [ "$profile_count" -gt 0 ]; then
    # Build menu options from profiles
    local -a menu_options=()
    local -a profile_names=()
    local -a profile_hosts=()
    local i

    for i in $(seq 0 $(( profile_count - 1 ))); do
      local pname phost
      pname=$(echo "$profiles_json" | jq -r ".[$i].name")
      phost=$(echo "$profiles_json" | jq -r ".[$i].host")
      profile_names+=("$pname")
      profile_hosts+=("$phost")
      menu_options+=("${pname}  (${phost})")
    done
    menu_options+=("Enter manually")

    local profile_choice
    profile_choice=$(select_menu "  Select a Databricks profile:" "${menu_options[@]}")

    if [ "$profile_choice" -lt "$profile_count" ]; then
      local selected_name="${profile_names[$profile_choice]}"
      local selected_host="${profile_hosts[$profile_choice]}"

      selected_host="${selected_host%/}"
      db_host="$selected_host"

      echo "  Using profile: $selected_name"
      echo "  Host: $selected_host"

      # Try to get auth token from the CLI
      local env_json
      env_json=$(databricks auth env --profile "$selected_name" --output json 2>/dev/null) || env_json=""

      if [ -n "$env_json" ]; then
        db_token=$(echo "$env_json" | jq -r '.env.DATABRICKS_TOKEN // empty' 2>/dev/null) || db_token=""
      fi

      if [ -z "$db_token" ]; then
        echo ""
        echo "  WARNING: Could not retrieve token for profile '$selected_name'."
        echo "  The token may be expired. Try: databricks auth login --profile $selected_name"
        echo ""
        db_token=$(prompt_secret "Databricks PAT or OAuth token (DATABRICKS_TOKEN)")
      fi

      use_manual=false
    fi
  elif [ "$cli_found" -ne 0 ]; then
    echo "  Databricks CLI not found — entering configuration manually."
    echo ""
  else
    echo "  No valid Databricks CLI profiles found."
    echo "  Tip: run 'databricks auth login' to set up a profile."
    echo ""
  fi

  # Manual flow
  if [ "$use_manual" = true ]; then
    db_host=$(resolve_setting "$SETTINGS_FILE" "DATABRICKS_HOST" "")
    db_token=$(resolve_setting "$SETTINGS_FILE" "DATABRICKS_TOKEN" "")

    if [ -z "$db_host" ]; then
      echo ""
      echo "  Databricks workspace URL is required."
      db_host=$(prompt_value "DATABRICKS_HOST (e.g., https://my-workspace.cloud.databricks.com)")
    fi

    if [ -z "$db_host" ]; then
      echo "  ERROR: DATABRICKS_HOST is required. Run 'make configure' first or provide it here."
      exit 1
    fi

    if [ -z "$db_token" ]; then
      echo ""
      echo "  Databricks token is required."
      db_token=$(prompt_secret "DATABRICKS_TOKEN (PAT or OAuth token)")
    fi

    if [ -z "$db_token" ]; then
      echo "  ERROR: DATABRICKS_TOKEN is required. Run 'make configure' first or provide it here."
      exit 1
    fi
  fi

  # Strip trailing slash from host
  db_host="${db_host%/}"

  # UC table — settings.json, then env var, then default
  uc_table=$(resolve_setting "$SETTINGS_FILE" "CLAUDE_OTEL_UC_TABLE" "")
  uc_table="${uc_table:-${CLAUDE_OTEL_UC_TABLE:-main.claude_telemetry.claude_otel_metrics}}"

  # -------------------------------------------------------------------------
  # Compute OTEL env vars and write to settings.json
  # -------------------------------------------------------------------------

  local env_file
  env_file=$(mktemp)
  trap "rm -f '$env_file'" EXIT

  {
    echo "CLAUDE_CODE_ENABLE_TELEMETRY=1"
    echo "OTEL_METRICS_EXPORTER=otlp"
    echo "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL=http/protobuf"
    echo "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=${db_host}/api/2.0/otel/v1/metrics"
    echo "OTEL_EXPORTER_OTLP_METRICS_HEADERS=content-type=application/x-protobuf,Authorization=Bearer ${db_token},X-Databricks-UC-Table-Name=${uc_table}"
  } > "$env_file"

  write_settings "$SETTINGS_FILE" "$env_file"

  # -------------------------------------------------------------------------
  # Done
  # -------------------------------------------------------------------------

  echo ""
  echo "  OTEL Configuration Complete!"
  echo "  =========================================="
  echo ""
  echo "  Telemetry will export to: ${uc_table}"
  echo "  Endpoint: ${db_host}/api/2.0/otel/v1/metrics"
  echo ""
  echo "  Restart Claude Code for changes to take effect."
  echo ""
  echo "  To reconfigure (e.g., after token rotation):"
  echo "    make configure-otel"
  echo "    — or re-run this script"
  echo ""
}

# ---------------------------------------------------------------------------
# check_prerequisites — Verify jq is available
# ---------------------------------------------------------------------------

check_prerequisites() {
  if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required but not installed."
    echo "  macOS:   brew install jq"
    echo "  Ubuntu:  sudo apt-get install jq"
    echo "  Other:   https://jqlang.github.io/jq/download/"
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# select_menu — Arrow-key navigable terminal menu
#
# Usage:  choice=$(select_menu "Header" "Option A" "Option B" "Option C")
# Returns 0-based index of the selected option on stdout.
# All visual output goes to /dev/tty so it works in curl-pipe-bash.
# Falls back to numbered read -p input when tput is unavailable.
# ---------------------------------------------------------------------------

select_menu() {
  local header="$1"; shift
  local -a options=("$@")
  local count=${#options[@]}

  # Fallback: numbered input when tput is unavailable
  if ! command -v tput &>/dev/null; then
    echo "$header" >/dev/tty
    local i
    for i in "${!options[@]}"; do
      echo "    $((i + 1))) ${options[$i]}" >/dev/tty
    done
    echo "" >/dev/tty
    local num
    read -p "  Choose [1-${count}] (default: 1): " num </dev/tty
    num="${num:-1}"
    echo $(( num - 1 ))
    return
  fi

  exec 3>/dev/tty

  trap 'printf "\033[?25h\033[0m" >&3; exec 3>&-; return 130' INT TERM

  local selected=0
  local prev_selected=-1
  local key seq

  # Hide cursor
  printf '\033[?25l' >&3

  # Print header (fixed, never redrawn)
  printf '%s\n' "$header" >&3

  local menu_lines=$(( count + 2 ))
  local j
  for (( j = 0; j < menu_lines; j++ )); do
    printf '\n' >&3
  done
  printf '\033[%dA' "$menu_lines" >&3

  while true; do
    if [ "$selected" -ne "$prev_selected" ]; then
      local i
      for i in "${!options[@]}"; do
        if [ "$i" -eq "$selected" ]; then
          printf '\033[2K\033[7m  > %s\033[0m\n' "${options[$i]}" >&3
        else
          printf '\033[2K    %s\n' "${options[$i]}" >&3
        fi
      done
      printf '\033[2K\n' >&3
      printf '\033[2K  Use arrow keys, Enter to select' >&3

      printf '\r\033[%dA' "$(( count + 1 ))" >&3

      prev_selected=$selected
    fi

    IFS= read -rsn1 key </dev/tty

    if [[ "$key" == "" ]]; then
      break
    elif [[ "$key" == $'\e' ]]; then
      IFS= read -rsn2 -t 1 seq </dev/tty || true
      case "$seq" in
        '[A') selected=$(( (selected - 1 + count) % count )) ;;
        '[B') selected=$(( (selected + 1) % count )) ;;
      esac
    fi
  done

  printf '\033[%dB\r\n' "$(( count + 1 ))" >&3
  printf '\033[?25h\033[0m' >&3

  exec 3>&-
  trap - INT TERM

  echo "$selected"
}

# ---------------------------------------------------------------------------
# detect_databricks_profiles — Detect valid Databricks CLI profiles
#
# Prints a JSON array of valid profiles to stdout.
# Returns 0 if databricks CLI is found, 1 if not.
# ---------------------------------------------------------------------------

detect_databricks_profiles() {
  if ! command -v databricks &>/dev/null; then
    echo "[]"
    return 1
  fi

  local raw_profiles
  raw_profiles=$(databricks auth profiles --output json 2>/dev/null) || {
    echo "[]"
    return 0
  }

  local filtered
  filtered=$(echo "$raw_profiles" | jq -c '
    [.profiles // [] | .[] | select(.valid == true) | {name, host, auth_type}]
  ' 2>/dev/null) || {
    echo "[]"
    return 0
  }

  echo "$filtered"
  return 0
}

# ---------------------------------------------------------------------------
# resolve_setting — Read a value from settings.json env block, fall back to env
# ---------------------------------------------------------------------------

resolve_setting() {
  local settings_file="$1"
  local key="$2"
  local default="$3"

  # Try settings.json first
  if [ -f "$settings_file" ]; then
    local val
    val=$(jq -r ".env.${key} // empty" "$settings_file" 2>/dev/null) || val=""
    if [ -n "$val" ]; then
      echo "$val"
      return
    fi
  fi

  # Fall back to environment
  local env_val="${!key:-}"
  if [ -n "$env_val" ]; then
    echo "$env_val"
    return
  fi

  echo "$default"
}

# ---------------------------------------------------------------------------
# Prompt helpers (read from /dev/tty for curl-pipe-bash compatibility)
# ---------------------------------------------------------------------------

prompt_value() {
  local prompt="$1"
  local result
  read -p "  ${prompt}: " result </dev/tty
  echo "$result"
}

prompt_secret() {
  local prompt="$1"
  echo "" >&2
  echo "  $prompt" >&2
  echo "  (Press Enter to skip)" >&2
  local result
  read -s -p "  Value: " result </dev/tty
  echo "" >&2
  echo "$result"
}

# ---------------------------------------------------------------------------
# write_settings — Merge env vars into ~/.claude/settings.json
# ---------------------------------------------------------------------------

write_settings() {
  local settings_file="$1"
  local env_file="$2"

  mkdir -p "$(dirname "$settings_file")"

  # Build a JSON object from KEY=VALUE lines
  local env_json="{}"
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    env_json=$(echo "$env_json" | jq --arg k "$key" --arg v "$value" '. + {($k): $v}')
  done < "$env_file"

  if [ -f "$settings_file" ]; then
    local tmp
    tmp=$(mktemp -p "$(dirname "$settings_file")")
    jq --argjson new_env "$env_json" '.env = ((.env // {}) + $new_env)' "$settings_file" > "$tmp"
    mv "$tmp" "$settings_file"
  else
    jq -n --argjson env "$env_json" '{env: $env}' > "$settings_file"
  fi

  echo ""
  echo "  Written to: $settings_file"
}

# ---------------------------------------------------------------------------
# remove_settings — Remove specified keys from ~/.claude/settings.json .env
# ---------------------------------------------------------------------------

remove_settings() {
  local settings_file="$1"
  shift
  local -a keys_to_remove=("$@")

  if [ ! -f "$settings_file" ]; then
    echo "  No settings file found at $settings_file — nothing to remove."
    return
  fi

  # Build a JSON array of key names
  local keys_json="[]"
  for k in "${keys_to_remove[@]}"; do
    keys_json=$(echo "$keys_json" | jq --arg k "$k" '. + [$k]')
  done

  # Identify which keys are actually present
  local present_keys
  present_keys=$(jq -r --argjson keys "$keys_json" '
    .env // {} | to_entries[] | select(.key as $k | $keys | index($k)) | .key
  ' "$settings_file" 2>/dev/null) || present_keys=""

  if [ -z "$present_keys" ]; then
    echo "  No matching env vars found in $settings_file — nothing to remove."
    return
  fi

  # Remove the keys
  local tmp
  tmp=$(mktemp -p "$(dirname "$settings_file")")
  jq --argjson keys "$keys_json" '
    .env |= (if . then with_entries(select(.key as $k | $keys | index($k) | not)) else . end)
    | if .env == {} or .env == null then del(.env) else . end
  ' "$settings_file" > "$tmp"
  mv "$tmp" "$settings_file"

  echo "  Removed from $settings_file:"
  while IFS= read -r k; do
    echo "    - $k"
  done <<< "$present_keys"
}

# Wrap in main() for curl-pipe-bash safety
main "$@"
