#!/bin/bash
set -euo pipefail

# ==============================================================================
# configure-inference.sh — Configure the Claude Code inference backend
#
# Fully self-contained. Runs via curl-pipe-bash or locally from the repo.
#
# Usage:
#   curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/configure-inference.sh | bash
#   make configure
#   bash scripts/configure-inference.sh
#
#   bash scripts/configure-inference.sh --uninstall   # Remove inference env vars
#   make unconfigure
#
# Writes to ~/.claude/settings.json so Claude Code picks up the backend
# automatically. If run from inside the repo, also writes config/inference.env
# for Makefile targets.
#
# Re-run at any time to change your backend configuration.
# ==============================================================================

# All env vars this script may write — union across all backends.
# Used by --uninstall to know what to remove.
INFERENCE_KEYS=(
  ANTHROPIC_BASE_URL
  ANTHROPIC_AUTH_TOKEN
  ANTHROPIC_DEFAULT_OPUS_MODEL
  ANTHROPIC_DEFAULT_SONNET_MODEL
  ANTHROPIC_DEFAULT_HAIKU_MODEL
  ANTHROPIC_CUSTOM_HEADERS
  CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS
  DATABRICKS_HOST
  DATABRICKS_TOKEN
  ANTHROPIC_API_KEY
  CLAUDE_CODE_USE_BEDROCK
  AWS_REGION
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_PROFILE
  CLAUDE_CODE_USE_VERTEX
  CLOUD_ML_PROJECT_ID
  CLOUD_ML_REGION
)

main() {
  local SETTINGS_FILE="$HOME/.claude/settings.json"

  if [ "${1:-}" = "--uninstall" ]; then
    check_prerequisites
    remove_settings "$SETTINGS_FILE" "${INFERENCE_KEYS[@]}"

    # Also remove config/inference.env if running from the repo
    if [ -d "config" ] && [ -f "Makefile" ] && [ -f "config/inference.env" ]; then
      rm -f "config/inference.env"
      echo "  Removed: config/inference.env"
    fi

    echo ""
    echo "  Inference configuration removed. Restart Claude Code for changes to take effect."
    return
  fi

  # -------------------------------------------------------------------------
  # Prerequisites
  # -------------------------------------------------------------------------

  check_prerequisites

  # -------------------------------------------------------------------------
  # Banner & menu
  # -------------------------------------------------------------------------

  clear_screen
  echo "  Claude Code Inference Configuration"
  echo "  =========================================="
  echo ""
  echo "  This configures ~/.claude/settings.json so Claude Code"
  echo "  picks up the backend automatically — no shell sourcing needed."
  echo ""
  local choice
  choice=$(select_menu "  Select a backend:" \
    "Databricks AI Gateway  (recommended)" \
    "Claude Max  (no configuration needed)" \
    "Anthropic Direct API" \
    "AWS Bedrock" \
    "Google Vertex AI" \
    "Custom endpoint")

  # Claude Max needs no env vars — skip straight to confirmation
  if [ "$choice" -eq 1 ]; then
    configure_claude_max
    return
  fi

  # Temp file to collect KEY=VALUE pairs
  local env_file
  env_file=$(mktemp)
  trap "rm -f '$env_file'" EXIT

  local profile_name
  case "$choice" in
    0) profile_name="databricks";  configure_databricks "$env_file" ;;
    2) profile_name="anthropic";   configure_anthropic "$env_file" ;;
    3) profile_name="bedrock";     configure_bedrock "$env_file" ;;
    4) profile_name="vertex";      configure_vertex "$env_file" ;;
    5) profile_name="custom";      configure_custom "$env_file" ;;
  esac

  # -------------------------------------------------------------------------
  # Write to ~/.claude/settings.json
  # -------------------------------------------------------------------------

  write_settings "$SETTINGS_FILE" "$env_file"

  # -------------------------------------------------------------------------
  # If inside the repo, also write config/inference.env
  # -------------------------------------------------------------------------

  write_inference_env "$env_file" "$profile_name"

  # -------------------------------------------------------------------------
  # Done
  # -------------------------------------------------------------------------

  clear_screen
  echo "  Configuration Complete!"
  echo "  =========================================="
  echo ""
  echo "  Your inference backend is now configured."
  echo ""
  echo "  What happens next:"
  echo "    - Claude Code reads ~/.claude/settings.json automatically"
  echo "    - No need to source anything — just run 'claude'"
  echo "    - To reconfigure: run this script again"
  echo ""
}

# ---------------------------------------------------------------------------
# check_prerequisites — Verify jq is available
# ---------------------------------------------------------------------------

check_prerequisites() {
  local missing=0

  if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required but not installed."
    echo "  macOS:   brew install jq"
    echo "  Ubuntu:  sudo apt-get install jq"
    echo "  Other:   https://jqlang.github.io/jq/download/"
    missing=1
  fi

  if [ "$missing" -ne 0 ]; then
    echo ""
    echo "Please install the missing prerequisites and re-run this script."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# clear_screen — Clear terminal for a fresh "page"
# ---------------------------------------------------------------------------

clear_screen() {
  if command -v tput &>/dev/null; then
    tput clear >/dev/tty 2>/dev/null || printf '\033[2J\033[H' >/dev/tty
  else
    printf '\033[2J\033[H' >/dev/tty
  fi
}

# ---------------------------------------------------------------------------
# Prompt helpers (read from /dev/tty for curl-pipe-bash compatibility)
# ---------------------------------------------------------------------------

prompt_value() {
  local prompt="$1"
  local default="${2:-}"
  local result

  if [ -n "$default" ]; then
    read -p "  ${prompt} [${default}]: " result </dev/tty
    result="${result:-$default}"
  else
    read -p "  ${prompt}: " result </dev/tty
  fi

  echo "$result"
}

prompt_secret() {
  local prompt="$1"

  echo "" >&2
  echo "  $prompt" >&2
  echo "  (Press Enter to skip — you can set this in your shell profile instead)" >&2

  local result
  read -s -p "  Value: " result </dev/tty
  echo "" >&2

  echo "$result"
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

  # Use a persistent file descriptor for /dev/tty so all escape sequences
  # and content go through the same fd in guaranteed order.
  exec 3>/dev/tty

  trap 'printf "\033[?25h\033[0m" >&3; exec 3>&-; return 130' INT TERM

  local selected=0
  local prev_selected=-1
  local key seq

  # Hide cursor
  printf '\033[?25l' >&3

  # Print header (fixed, never redrawn)
  printf '%s\n' "$header" >&3

  # Reserve screen space: print blank lines for the full menu height so any
  # terminal scrolling happens NOW, before we start cursor movement.
  local menu_lines=$(( count + 2 ))   # options + blank + footer
  local j
  for (( j = 0; j < menu_lines; j++ )); do
    printf '\n' >&3
  done
  # Move cursor back up to the start of the options area.
  # These lines are guaranteed to be on-screen since we just printed them.
  printf '\033[%dA' "$menu_lines" >&3

  # Main loop — cursor is always parked at the start of the options area
  while true; do
    if [ "$selected" -ne "$prev_selected" ]; then
      # Draw menu from current position
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

      # Move cursor back to the start of the options area.
      # Cursor is at end of footer (count+1 rows below row 0).
      printf '\r\033[%dA' "$(( count + 1 ))" >&3

      prev_selected=$selected
    fi

    IFS= read -rsn1 key </dev/tty

    if [[ "$key" == "" ]]; then
      # Enter pressed — confirm selection
      break
    elif [[ "$key" == $'\e' ]]; then
      # Read remaining escape sequence bytes.
      # Use -t 1 (not fractional) for bash 3.2 compatibility on macOS.
      IFS= read -rsn2 -t 1 seq </dev/tty || true
      case "$seq" in
        '[A') selected=$(( (selected - 1 + count) % count )) ;;
        '[B') selected=$(( (selected + 1) % count )) ;;
      esac
    fi
  done

  # Move cursor below the menu, show cursor, reset attributes
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

  # Filter to valid profiles, extract name + host + auth_type
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
# resolve_workspace_id — Get numeric workspace ID via SCIM API header
#
# Calls /api/2.0/preview/scim/v2/Me and reads x-databricks-org-id header.
# Returns empty string on failure (missing token, network error, etc.).
# ---------------------------------------------------------------------------

resolve_workspace_id() {
  local host="$1"
  local token="$2"

  if [ -z "$token" ] || [ -z "$host" ]; then
    echo ""
    return
  fi

  local headers
  headers=$(curl -sI -m 10 \
    -H "Authorization: Bearer ${token}" \
    "${host}/api/2.0/preview/scim/v2/Me" 2>/dev/null) || { echo ""; return; }

  local org_id
  org_id=$(echo "$headers" | grep -i 'x-databricks-org-id' | head -1 | tr -d '\r' | awk '{print $2}') || { echo ""; return; }

  echo "$org_id"
}

# ---------------------------------------------------------------------------
# Profile configurators — each writes KEY=VALUE lines to the env file
# ---------------------------------------------------------------------------

configure_databricks() {
  local env_file="$1"

  clear_screen
  echo "  Databricks AI Gateway"
  echo "  =========================================="
  echo ""
  echo "  Uses the AI Gateway URL: https://{workspace_id}.ai-gateway.cloud.databricks.com/anthropic"
  echo ""

  local use_manual=true
  local workspace_url=""
  local auth_token=""
  local selected_profile_name=""

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
      # User selected a CLI profile
      local selected_name="${profile_names[$profile_choice]}"
      local selected_host="${profile_hosts[$profile_choice]}"
      selected_profile_name="$selected_name"

      # Strip trailing slash from host
      selected_host="${selected_host%/}"
      workspace_url="$selected_host"

      echo "  Using profile: $selected_name"
      echo "  Host: $selected_host"

      # Try to get auth token from the CLI
      local env_json
      env_json=$(databricks auth env --profile "$selected_name" --output json 2>/dev/null) || env_json=""

      if [ -n "$env_json" ]; then
        auth_token=$(echo "$env_json" | jq -r '.env.DATABRICKS_TOKEN // empty' 2>/dev/null) || auth_token=""
      fi

      if [ -z "$auth_token" ]; then
        echo ""
        echo "  WARNING: Could not retrieve token for profile '$selected_name'."
        echo "  The token may be expired. Try: databricks auth login --profile $selected_name"
        echo ""
        auth_token=$(prompt_secret "Databricks PAT or OAuth token (ANTHROPIC_AUTH_TOKEN)")
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
    echo "  You only need to provide your Databricks workspace URL."
    echo ""

    workspace_url=$(prompt_value "Databricks workspace URL (e.g., https://my-workspace.cloud.databricks.com)" "")

    if [ -z "$workspace_url" ]; then
      echo "  ERROR: Workspace URL is required."
      exit 1
    fi

    # Strip trailing slash
    workspace_url="${workspace_url%/}"

    auth_token=$(prompt_secret "Databricks PAT or OAuth token (ANTHROPIC_AUTH_TOKEN)")
  fi

  # Resolve workspace ID via SCIM API
  echo ""
  echo "  Resolving workspace ID..."
  local workspace_id
  workspace_id=$(resolve_workspace_id "$workspace_url" "$auth_token")

  if [ -z "$workspace_id" ]; then
    echo "  Could not auto-detect workspace ID."
    workspace_id=$(prompt_value "Databricks workspace ID (numeric, e.g., 1444828305810485)" "")
    if [ -z "$workspace_id" ]; then
      echo "  ERROR: Workspace ID is required."
      exit 1
    fi
  else
    echo "  Workspace ID: $workspace_id"
  fi

  local base_url="https://${workspace_id}.ai-gateway.cloud.databricks.com/anthropic"
  echo ""
  echo "  ANTHROPIC_BASE_URL: $base_url"

  {
    echo "ANTHROPIC_BASE_URL=${base_url}"
    if [ -n "$auth_token" ]; then
      echo "ANTHROPIC_AUTH_TOKEN=${auth_token}"
    fi
    echo "ANTHROPIC_DEFAULT_OPUS_MODEL=databricks-claude-opus-4-6"
    echo "ANTHROPIC_DEFAULT_SONNET_MODEL=databricks-claude-sonnet-4-5"
    echo "ANTHROPIC_DEFAULT_HAIKU_MODEL=databricks-claude-haiku-4-5"
    echo "ANTHROPIC_CUSTOM_HEADERS=x-databricks-use-coding-agent-mode: true"
    echo "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1"
    echo "DATABRICKS_HOST=${workspace_url}"
    if [ -n "$auth_token" ]; then
      echo "DATABRICKS_TOKEN=${auth_token}"
    fi
    if [ -n "$selected_profile_name" ]; then
      echo "DATABRICKS_CONFIG_PROFILE=${selected_profile_name}"
    fi
  } > "$env_file"

  # -------------------------------------------------------------------------
  # Offer token refresh method: proxy (recommended), shell wrapper, or skip
  # -------------------------------------------------------------------------

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Token Refresh Method"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "  OAuth tokens expire after ~1 hour. Choose how to handle refresh:"
  echo ""

  local refresh_choice
  refresh_choice=$(select_menu "  Token refresh method:" \
    "claude-db proxy (recommended)  — Refreshes tokens per-request. Works for inference + OTEL." \
    "Shell wrapper                  — Refreshes tokens at session start only." \
    "Skip                           — Manual token management.")

  case "$refresh_choice" in
    0) install_claude_db_proxy "$selected_profile_name" ;;
    1) install_token_refresh_wrapper ;;
    2)
      echo ""
      echo "  Skipped. To configure manually later, run: make configure"
      echo ""
      ;;
  esac
}

# ---------------------------------------------------------------------------
# install_claude_db_proxy — Install or guide the user to install claude-db
# ---------------------------------------------------------------------------

install_claude_db_proxy() {
  local profile_name="${1:-}"
  local bin_dir="$HOME/.claude/bin"
  local bin_path="$bin_dir/claude-db"

  echo ""
  echo "  claude-db proxy"
  echo ""

  # Check if already installed
  if [ -x "$bin_path" ]; then
    echo "  claude-db is already installed at $bin_path"
    echo ""
    _claude_db_ensure_path "$bin_dir"
    return
  fi

  # Try to build from source if Go is available and we're in the repo
  if command -v go &>/dev/null && [ -d "tools/claude-db" ] && [ -f "tools/claude-db/go.mod" ]; then
    echo "  Go toolchain found. Building claude-db from source..."
    if make build-claude-db 2>/dev/null && make install-claude-db 2>/dev/null; then
      echo ""
      echo "  claude-db installed to $bin_path"
      echo ""
      _claude_db_ensure_path "$bin_dir"
      return
    else
      echo "  WARNING: Build failed. Falling back to manual instructions."
    fi
  fi

  # Fallback: print download instructions
  echo "  claude-db is not installed. To install:"
  echo ""
  echo "  Option A — Build from source (requires Go 1.22+):"
  echo "    git clone https://github.com/IceRhymers/claude-marketplace-builder"
  echo "    cd claude-marketplace-builder"
  echo "    make build-claude-db && make install-claude-db"
  echo ""
  echo "  Option B — Download pre-built binary:"
  echo "    https://github.com/IceRhymers/claude-marketplace-builder/releases"
  echo "    Copy the binary to: $bin_path"
  echo "    chmod +x $bin_path"
  echo ""
  echo "  Then add to PATH:"
  echo "    export PATH=\"$bin_dir:\$PATH\""
  echo ""
  echo "  Usage (drop-in replacement for 'claude'):"
  if [ -n "$profile_name" ]; then
    echo "    claude-db --profile $profile_name"
  else
    echo "    claude-db"
  fi
  echo ""
}

# _claude_db_ensure_path — Add ~/.claude/bin to PATH in the user's rc file if needed
_claude_db_ensure_path() {
  local bin_dir="$1"

  # Detect shell rc file
  local rc_file
  local shell_name
  shell_name="${SHELL##*/}"
  case "$shell_name" in
    zsh)  rc_file="$HOME/.zshrc" ;;
    bash) rc_file="$HOME/.bashrc" ;;
    *)    rc_file="$HOME/.bashrc" ;;
  esac

  # Skip if already in PATH or already in rc file
  if echo "$PATH" | grep -qF "$bin_dir"; then
    return
  fi
  if [ -f "$rc_file" ] && grep -qF "$bin_dir" "$rc_file" 2>/dev/null; then
    return
  fi

  {
    echo ""
    echo "# claude-db proxy — add to PATH"
    echo "export PATH=\"$bin_dir:\$PATH\""
  } >> "$rc_file"

  echo "  Added $bin_dir to PATH in $rc_file"
  echo "  Run: source $rc_file"
  echo ""
}

# ---------------------------------------------------------------------------
# install_token_refresh_wrapper — Copy refresh script and patch shell rc file
# ---------------------------------------------------------------------------

install_token_refresh_wrapper() {
  local scripts_dir="$HOME/.claude/scripts"
  local target="$scripts_dir/refresh-databricks-token.sh"

  # Locate the source refresh script (works both from repo and curl-pipe-bash)
  local source_script=""
  # Check relative to this script's location first
  local this_dir
  this_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || this_dir=""
  if [ -n "$this_dir" ] && [ -f "$this_dir/refresh-databricks-token.sh" ]; then
    source_script="$this_dir/refresh-databricks-token.sh"
  fi

  # Install the refresh script
  mkdir -p "$scripts_dir"

  if [ -n "$source_script" ]; then
    cp "$source_script" "$target"
  else
    # Fallback: download from repo if running via curl-pipe-bash
    if command -v curl &>/dev/null; then
      curl -sSL \
        "https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/refresh-databricks-token.sh" \
        -o "$target" 2>/dev/null || {
        echo ""
        echo "  WARNING: Could not download refresh-databricks-token.sh."
        echo "  Please copy it manually to: $target"
        echo ""
        return
      }
    else
      echo ""
      echo "  WARNING: Could not install refresh script (curl not available)."
      echo "  Please copy scripts/refresh-databricks-token.sh to: $target"
      echo ""
      return
    fi
  fi

  chmod +x "$target"

  # Detect shell and rc file
  local rc_file
  local shell_name
  shell_name="${SHELL##*/}"
  case "$shell_name" in
    zsh)  rc_file="$HOME/.zshrc" ;;
    bash) rc_file="$HOME/.bashrc" ;;
    *)    rc_file="$HOME/.bashrc" ;;
  esac

  # Back up rc file
  if [ -f "$rc_file" ]; then
    local backup="${rc_file}.bak.$(date +%Y%m%d)"
    cp "$rc_file" "$backup"
    echo "  Backed up: $backup"
  fi

  # Duplicate detection — skip if wrapper already present
  if [ -f "$rc_file" ] && grep -q 'refresh-databricks-token.sh' "$rc_file" 2>/dev/null; then
    echo ""
    echo "  Token refresh wrapper already present in $rc_file — skipping."
    echo ""
    return
  fi

  # Append the claude() wrapper function
  {
    echo ""
    echo "# Claude Code — automatic Databricks token refresh"
    echo "claude() {"
    echo "  if [ -x \"\$HOME/.claude/scripts/refresh-databricks-token.sh\" ]; then"
    echo "    bash \"\$HOME/.claude/scripts/refresh-databricks-token.sh\" 2>/dev/null || true"
    echo "  fi"
    echo "  command claude \"\$@\""
    echo "}"
  } >> "$rc_file"

  echo ""
  echo "  Token refresh wrapper installed!"
  echo "    Script:  $target"
  echo "    Added to: $rc_file"
  echo ""
  echo "  Run the following to activate in your current session:"
  echo "    source $rc_file"
  echo ""
}

configure_anthropic() {
  local env_file="$1"

  clear_screen
  echo "  Anthropic Direct"
  echo "  =========================================="
  echo ""

  local api_key
  api_key=$(prompt_secret "Anthropic API key (ANTHROPIC_API_KEY)")

  : > "$env_file"
  if [ -n "$api_key" ]; then
    echo "ANTHROPIC_API_KEY=${api_key}" > "$env_file"
  fi
}

configure_bedrock() {
  local env_file="$1"

  clear_screen
  echo "  AWS Bedrock"
  echo "  =========================================="
  echo ""

  local aws_region
  aws_region=$(prompt_value "AWS region (e.g., us-east-1)" "us-east-1")

  local auth_choice
  auth_choice=$(select_menu "  Authentication method:" \
    "AWS access key + secret key" \
    "AWS CLI profile name" \
    "Skip (use instance role, SSO, or env vars)")

  {
    echo "CLAUDE_CODE_USE_BEDROCK=1"
    echo "AWS_REGION=${aws_region}"
  } > "$env_file"

  case "$auth_choice" in
    0)
      local aws_access_key aws_secret_key
      aws_access_key=$(prompt_secret "AWS Access Key ID")
      aws_secret_key=$(prompt_secret "AWS Secret Access Key")
      [ -n "$aws_access_key" ] && echo "AWS_ACCESS_KEY_ID=${aws_access_key}" >> "$env_file"
      [ -n "$aws_secret_key" ] && echo "AWS_SECRET_ACCESS_KEY=${aws_secret_key}" >> "$env_file"
      ;;
    1)
      local aws_profile
      aws_profile=$(prompt_value "AWS profile name" "default")
      echo "AWS_PROFILE=${aws_profile}" >> "$env_file"
      ;;
  esac
}

configure_vertex() {
  local env_file="$1"

  clear_screen
  echo "  Google Vertex AI"
  echo "  =========================================="
  echo ""

  local gcp_project
  gcp_project=$(prompt_value "GCP Project ID" "")

  if [ -z "$gcp_project" ]; then
    echo "  ERROR: GCP Project ID is required."
    exit 1
  fi

  local gcp_region
  gcp_region=$(prompt_value "GCP region (e.g., us-east5)" "us-east5")

  {
    echo "CLAUDE_CODE_USE_VERTEX=1"
    echo "CLOUD_ML_PROJECT_ID=${gcp_project}"
    echo "CLOUD_ML_REGION=${gcp_region}"
  } > "$env_file"

  echo ""
  echo "  Make sure you have authenticated with: gcloud auth application-default login"
}

configure_custom() {
  local env_file="$1"

  clear_screen
  echo "  Custom Endpoint"
  echo "  =========================================="
  echo ""

  local base_url
  base_url=$(prompt_value "Custom base URL" "")

  if [ -z "$base_url" ]; then
    echo "  ERROR: Base URL is required."
    exit 1
  fi

  local auth_token
  auth_token=$(prompt_secret "Auth token (ANTHROPIC_AUTH_TOKEN)")

  {
    echo "ANTHROPIC_BASE_URL=${base_url}"
    if [ -n "$auth_token" ]; then
      echo "ANTHROPIC_AUTH_TOKEN=${auth_token}"
    fi
  } > "$env_file"
}

configure_claude_max() {
  clear_screen
  echo "  Claude Max"
  echo "  =========================================="
  echo ""
  echo "  Claude Max includes inference — no additional configuration needed."
  echo ""
  echo "  Just make sure you're signed in:"
  echo "    1. Run 'claude' in your terminal"
  echo "    2. Sign in with your Anthropic account when prompted"
  echo ""
  echo "  That's it! Claude Code will use your Max subscription automatically."
  echo ""
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
    # Skip empty lines and comments
    [[ -z "$key" || "$key" == \#* ]] && continue
    env_json=$(echo "$env_json" | jq --arg k "$key" --arg v "$value" '. + {($k): $v}')
  done < "$env_file"

  # Back up existing settings before modifying
  if [ -f "$settings_file" ]; then
    local backup="${settings_file}.backup"
    cp "$settings_file" "$backup"
    echo "  Backed up: $backup"

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

# ---------------------------------------------------------------------------
# write_inference_env — If run from inside the repo, write config/inference.env
# ---------------------------------------------------------------------------

write_inference_env() {
  local env_file="$1"
  local profile_name="$2"

  # Detect repo by looking for config/ dir and Makefile in the current directory
  if [ -d "config" ] && [ -f "Makefile" ]; then
    local output="config/inference.env"
    mkdir -p config

    {
      echo "# Generated by configure-inference.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "# Profile: $profile_name"
      echo "# Re-run 'make configure' or 'bash scripts/configure-inference.sh' to change."
      echo ""
      cat "$env_file"
    } > "$output"

    echo "  Also written to: $output (for Makefile targets)"
  fi
}

# Wrap in main() for curl-pipe-bash safety
main "$@"
