# Installation Guide

## Prerequisites

- **git** — [Install git](https://git-scm.com/downloads)
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code`
- **jq** — [Install jq](https://jqlang.github.io/jq/download/) (used by the install script to discover plugins)
- **Repository access** — You must have access to the IceRhymers skills repository

## One-Line Install

```bash
curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/install.sh | bash
```

This will:
1. Clone the repository to `~/.claude-skills/icerhymers`
2. Register the marketplace with Claude Code
3. Install all skill plugins

## Manual Install

If you prefer to install manually:

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

## Inference Configuration

After installation, configure which inference backend Claude Code should use.

### Quick setup (no repo clone needed)

```bash
curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/configure-inference.sh | bash
```

### For marketplace developers (working in this repo)

```bash
make configure
```

Both write to `~/.claude/settings.json` so Claude Code picks up the backend automatically — run once, done. When run from within the repo, `make configure` also generates `config/inference.env` for Makefile targets (evals, etc.). The Makefile auto-sources this file when it exists.

### Manual setup

If you prefer not to use the interactive script, set the env vars directly in your shell profile. The most common setup for Databricks:

```bash
# Add to ~/.bashrc or ~/.zshrc
export ANTHROPIC_BASE_URL="https://your-workspace.cloud.databricks.com/serving-endpoints/anthropic"
export ANTHROPIC_AUTH_TOKEN="your-databricks-pat"
export ANTHROPIC_DEFAULT_OPUS_MODEL="databricks-claude-opus-4-6"
export ANTHROPIC_DEFAULT_SONNET_MODEL="databricks-claude-sonnet-4-5"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="databricks-claude-haiku-4-5"
```

For other backends, see the profile templates in `config/profiles/` for the required environment variables.

## Verifying Installation

After installation, check installed plugins:

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
