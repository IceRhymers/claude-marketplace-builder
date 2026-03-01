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
# Writes to ~/.claude/settings.json so Claude Code picks up the backend
# automatically. If run from inside the repo, also writes config/inference.env
# for Makefile targets.
#
# Re-run at any time to change your backend configuration.
# ==============================================================================

main() {
  local SETTINGS_FILE="$HOME/.claude/settings.json"

  # -------------------------------------------------------------------------
  # Prerequisites
  # -------------------------------------------------------------------------

  check_prerequisites

  # -------------------------------------------------------------------------
  # Banner & menu
  # -------------------------------------------------------------------------

  echo "=========================================="
  echo "  Claude Code Inference Configuration"
  echo "=========================================="
  echo ""
  echo "  Select which backend Claude Code should use for inference."
  echo ""
  echo "  This configures ~/.claude/settings.json so Claude Code picks"
  echo "  up the backend automatically — no shell sourcing needed."
  echo ""
  echo "  Backends:"
  echo "    1) Databricks AI Gateway  (recommended)"
  echo "    2) Anthropic Direct"
  echo "    3) AWS Bedrock"
  echo "    4) Google Vertex AI"
  echo "    5) Custom endpoint"
  echo ""

  local choice
  read -p "  Choose a backend [1-5] (default: 1): " choice </dev/tty
  choice="${choice:-1}"

  # Temp file to collect KEY=VALUE pairs
  local env_file
  env_file=$(mktemp)
  trap "rm -f '$env_file'" EXIT

  local profile_name
  case "$choice" in
    1) profile_name="databricks";  configure_databricks "$env_file" ;;
    2) profile_name="anthropic";   configure_anthropic "$env_file" ;;
    3) profile_name="bedrock";     configure_bedrock "$env_file" ;;
    4) profile_name="vertex";      configure_vertex "$env_file" ;;
    5) profile_name="custom";      configure_custom "$env_file" ;;
    *)
      echo "  Invalid choice: $choice"
      exit 1
      ;;
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

  echo ""
  echo "=========================================="
  echo "  Configuration Complete!"
  echo "=========================================="
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
# Profile configurators — each writes KEY=VALUE lines to the env file
# ---------------------------------------------------------------------------

configure_databricks() {
  local env_file="$1"

  echo ""
  echo "  Databricks AI Gateway Configuration"
  echo "  ------------------------------------"
  echo ""
  echo "  The endpoint path /serving-endpoints/anthropic is fixed."
  echo "  You only need to provide your Databricks workspace URL."
  echo ""

  local workspace_url
  workspace_url=$(prompt_value "Databricks workspace URL (e.g., https://my-workspace.cloud.databricks.com)" "")

  if [ -z "$workspace_url" ]; then
    echo "  ERROR: Workspace URL is required."
    exit 1
  fi

  # Strip trailing slash
  workspace_url="${workspace_url%/}"

  local base_url="${workspace_url}/serving-endpoints/anthropic"
  echo ""
  echo "  ANTHROPIC_BASE_URL: $base_url"

  local auth_token
  auth_token=$(prompt_secret "Databricks PAT or OAuth token (ANTHROPIC_AUTH_TOKEN)")

  {
    echo "ANTHROPIC_BASE_URL=${base_url}"
    if [ -n "$auth_token" ]; then
      echo "ANTHROPIC_AUTH_TOKEN=${auth_token}"
    fi
    echo "ANTHROPIC_DEFAULT_OPUS_MODEL=databricks-claude-opus-4-6"
    echo "ANTHROPIC_DEFAULT_SONNET_MODEL=databricks-claude-sonnet-4-5"
    echo "ANTHROPIC_DEFAULT_HAIKU_MODEL=databricks-claude-haiku-4-5"
  } > "$env_file"
}

configure_anthropic() {
  local env_file="$1"

  echo ""
  echo "  Anthropic Direct Configuration"
  echo "  -------------------------------"
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

  echo ""
  echo "  AWS Bedrock Configuration"
  echo "  --------------------------"
  echo ""

  local aws_region
  aws_region=$(prompt_value "AWS region (e.g., us-east-1)" "us-east-1")

  echo ""
  echo "  Authentication method:"
  echo "    1) AWS access key + secret key"
  echo "    2) AWS CLI profile name"
  echo "    3) Skip (use instance role, SSO, or env vars)"
  echo ""

  local auth_choice
  read -p "  Choose [1-3] (default: 3): " auth_choice </dev/tty
  auth_choice="${auth_choice:-3}"

  {
    echo "CLAUDE_CODE_USE_BEDROCK=1"
    echo "AWS_REGION=${aws_region}"
  } > "$env_file"

  case "$auth_choice" in
    1)
      local aws_access_key aws_secret_key
      aws_access_key=$(prompt_secret "AWS Access Key ID")
      aws_secret_key=$(prompt_secret "AWS Secret Access Key")
      [ -n "$aws_access_key" ] && echo "AWS_ACCESS_KEY_ID=${aws_access_key}" >> "$env_file"
      [ -n "$aws_secret_key" ] && echo "AWS_SECRET_ACCESS_KEY=${aws_secret_key}" >> "$env_file"
      ;;
    2)
      local aws_profile
      aws_profile=$(prompt_value "AWS profile name" "default")
      echo "AWS_PROFILE=${aws_profile}" >> "$env_file"
      ;;
  esac
}

configure_vertex() {
  local env_file="$1"

  echo ""
  echo "  Google Vertex AI Configuration"
  echo "  --------------------------------"
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

  echo ""
  echo "  Custom Endpoint Configuration"
  echo "  -------------------------------"
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
    tmp=$(mktemp)
    jq --argjson new_env "$env_json" '.env = ((.env // {}) + $new_env)' "$settings_file" > "$tmp"
    mv "$tmp" "$settings_file"
  else
    jq -n --argjson env "$env_json" '{env: $env}' > "$settings_file"
  fi

  echo ""
  echo "  Written to: $settings_file"
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
