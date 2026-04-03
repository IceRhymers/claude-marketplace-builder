# Installation Guide

## Prerequisites

- **git** — [Install git](https://git-scm.com/downloads)
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code`
- **jq** — [Install jq](https://jqlang.github.io/jq/download/) (used by setup scripts)
- **Repository access** — You must have access to the IceRhymers skills repository

## Step 1: Set Up Inference

> **Already have Claude Code working?** If you can run `claude` and get responses (e.g., you're on Claude Max or already configured a backend), skip to [Step 2](#step-2-install-the-marketplace).

Claude Code needs an inference backend before it can do anything. Run the interactive setup:

```bash
curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/configure-inference.sh | bash
```

This walks you through connecting Claude Code to one of:

| Backend | Best for |
|---------|----------|
| **Databricks AI Gateway** | Teams using Databricks (auto-detects CLI profiles, supports OAuth + PAT) |
| **Claude Max** | Individual subscribers — zero config needed |
| **Anthropic Direct API** | Direct API key access |
| **AWS Bedrock** | AWS-native deployments |
| **Google Vertex AI** | GCP-native deployments |
| **Custom endpoint** | Proxies, self-hosted, or other setups |

The script writes to `~/.claude/settings.json` so Claude Code picks up the backend automatically — no shell sourcing needed. Re-run at any time to change backends.

**OAuth vs PAT:** The Databricks profile now supports OAuth as the primary auth method (via `databricks auth login`). Personal Access Tokens (PATs) remain supported as a fallback for environments without Databricks CLI. If you use OAuth, the configure script can set up an automatic token refresh wrapper so tokens stay fresh across long sessions.

### Manual inference setup

If you prefer not to use the interactive script, set env vars directly in your shell profile. Example for Databricks using OAuth:

```bash
# Add to ~/.bashrc or ~/.zshrc
export ANTHROPIC_BASE_URL="https://your-workspace.cloud.databricks.com/serving-endpoints/anthropic"
export DATABRICKS_CONFIG_PROFILE="DEFAULT"   # profile from `databricks auth login`
# ANTHROPIC_AUTH_TOKEN is populated by the token refresh wrapper when using OAuth
export ANTHROPIC_DEFAULT_OPUS_MODEL="databricks-claude-opus-4-6"
export ANTHROPIC_DEFAULT_SONNET_MODEL="databricks-claude-sonnet-4-5"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="databricks-claude-haiku-4-5"
export ANTHROPIC_CUSTOM_HEADERS="x-databricks-use-coding-agent-mode: true"
export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS="1"
```

For PAT-based auth (no Databricks CLI), replace the `DATABRICKS_CONFIG_PROFILE` line with:
```bash
export ANTHROPIC_AUTH_TOKEN="your-databricks-pat"
```

For other backends, see the profile templates in `config/profiles/`.

## Step 2: Install the Marketplace

### One-line install

```bash
curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/install.sh | bash
```

This will:
1. Clone the repository to `~/.claude-skills/icerhymers`
2. Register the marketplace with Claude Code
3. Install all skill plugins

### Manual install

```bash
# Clone the repository
git clone https://github.com/IceRhymers/claude-marketplace-builder ~/.claude-skills/icerhymers

# Register the marketplace
claude plugin marketplace add ~/.claude-skills/icerhymers

# Install plugins
claude plugin install icerhymers-databricks-skills@icerhymers-marketplace
claude plugin install icerhymers-internal-skills@icerhymers-marketplace
claude plugin install icerhymers-marketplace-management@icerhymers-marketplace
claude plugin install icerhymers-specialized-tools@icerhymers-marketplace
```

### For marketplace developers

If you're working in this repo, use `make configure` instead of the curl command for inference setup — it also generates `config/inference.env` for Makefile targets (evals, etc.).

## Step 3: Enable OTEL Telemetry (Optional)

If your team uses Databricks for telemetry, configure Claude Code to export OTEL metrics to a Unity Catalog table:

```bash
curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/configure-otel.sh | bash
```

Or from within the repo:

```bash
make configure-otel
```

This reads your Databricks credentials from `~/.claude/settings.json` (set during Step 1), computes the OTEL endpoint URL and auth headers, and merges them back into settings.json. Restart Claude Code for the changes to take effect.

**Why not a plugin hook?** OTEL env vars must be present before Claude Code starts — `SessionStart` hooks fire too late. The `settings.json` `env` block is loaded at process startup, which is the only mechanism that works.

**Token rotation:** Re-run `configure-otel.sh` after updating your Databricks token to recompute the OTEL headers.

**OTEL Token Lifetime:** OTEL metrics use an OAuth token that expires after ~1 hour. After expiry, metrics stop exporting silently. For complete telemetry coverage during long sessions, restart Claude Code approximately every hour. A future update may add mid-session token refresh.

**Verify:** Use `/otel-status` inside Claude Code to check whether OTEL is configured correctly.

## Verifying Installation

```bash
claude plugin list
```

## Updating

### Option 1: Inside Claude Code

```
/update-skills
```

### Option 2: Manual

```bash
cd ~/.claude-skills/icerhymers && git pull origin main
```

## Troubleshooting

### "Repository not found" or "Permission denied"

Make sure you have access to the IceRhymers skills repository. Check with your team admin.

### "claude: command not found"

Install the Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
```

### Skills not showing up

1. Verify the marketplace is registered: `claude plugin marketplace list`
2. Verify plugins are installed: `claude plugin list`
3. Try reinstalling:
   ```bash
   bash ~/.claude-skills/icerhymers/scripts/install.sh
   ```
