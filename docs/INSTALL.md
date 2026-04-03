# Installation Guide

## Prerequisites

- **git** — [Install git](https://git-scm.com/downloads)
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code`
- **jq** — [Install jq](https://jqlang.github.io/jq/download/) (used by setup scripts)
- **Repository access** — You must have access to the IceRhymers skills repository

## Step 1: Set Up Inference

Claude Code needs a Databricks AI Gateway connection before it can do anything. There are two paths — choose based on your needs:

| Feature | PAT Token | claude-db Proxy |
|---|---|---|
| AI Gateway inference | Yes | Yes |
| OTEL telemetry export | Yes | Yes |
| MCP servers (Slack, Genie) | Requires separate `databricks auth login` | Yes (automatic) |
| Budget enforcement | Yes (via env var) | Yes (automatic) |
| Token refresh | Manual (regenerate PAT) | Automatic (OAuth) |
| Setup complexity | Low | Medium |

### Option A: PAT Token (Recommended for simplicity)

Run the interactive setup:

```bash
make configure
```

This calls `scripts/configure-inference.sh`, which detects existing Databricks CLI profiles or prompts for manual entry (workspace URL + PAT token). The script auto-resolves your workspace ID and writes settings to `~/.claude/settings.json` — no shell sourcing needed.

For MCP servers (Slack, Genie) and budget enforcement, also run:

```bash
databricks auth login --profile DEFAULT
```

For OTEL telemetry, run:

```bash
make configure-otel
```

### Option B: claude-db Proxy (Recommended for automatic credential management)

Build and install the proxy:

```bash
make install-claude-db
```

Then use `claude-db` instead of `claude`. The proxy handles the full OAuth token lifecycle automatically for inference, OTEL, and all plugins — no manual token management needed. Supports `--profile`, `--otel`, and `--upstream` flags.

### Existing user cleanup

Users who previously installed the shell wrapper may have:

- `~/.claude/scripts/refresh-databricks-token.sh`
- A `claude()` function in their `.bashrc`/`.zshrc`

These are now obsolete. Optionally remove:

```bash
rm -f ~/.claude/scripts/refresh-databricks-token.sh
# Remove the claude() function from your shell rc file
```

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

If you're working in this repo, use `make configure` for inference setup — it also generates `config/inference.env` for Makefile targets (evals, etc.).

## Step 3: Enable OTEL Telemetry (Optional)

If your team uses Databricks for telemetry, configure Claude Code to export OTEL metrics to a Unity Catalog table:

```bash
make configure-otel
```

This reads your Databricks credentials from `~/.claude/settings.json` (set during Step 1), computes the OTEL endpoint URL and auth headers, and merges them back into settings.json. Restart Claude Code for the changes to take effect.

**Why not a plugin hook?** OTEL env vars must be present before Claude Code starts — `SessionStart` hooks fire too late. The `settings.json` `env` block is loaded at process startup, which is the only mechanism that works.

**Token rotation:** Re-run `configure-otel.sh` after updating your Databricks PAT to recompute the OTEL headers. With `claude-db`, token rotation is handled automatically.

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
