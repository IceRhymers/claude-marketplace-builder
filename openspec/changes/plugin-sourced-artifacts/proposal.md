## Why

The cowork app maintains its own `cowork/skills/` directory and a custom `build-artifact.sh` pipeline to package skills into a Volume-hosted artifact. But this repo already has a full plugin-based skill marketplace under `plugins/*/skills/` — the same skills we author and distribute via `marketplace.json`. Having two separate skill authoring/packaging paths creates duplication, drift risk, and confusion about where skills should live. The plugin definition should be the single source of truth for the cowork artifact.

## What Changes

- **BREAKING**: Remove `cowork/skills/` directory entirely — it is no longer the skill source
- Rewrite `cowork/scripts/build-artifact.sh` to package skills from `plugins/*/skills/` (the marketplace plugin tree) instead of `cowork/skills/`
- Source `.mcp.json` from `plugins/databricks-mcp/.mcp.json` instead of a cowork-local copy
- Add MCP config templating so that env-var placeholders (e.g., `${SLACK_MCP_URL}`, `${DATABRICKS_HOST}`) are resolved at runtime via the existing `substitute_token()` path, adapting it for the app's deployment env vars (not just `${ACCESS_TOKEN}`)
- Update `cowork/references/volume-setup.md` to reflect the new artifact source
- Update the Makefile `build-artifact` target if paths change

## Capabilities

### New Capabilities
- `plugin-artifact-builder`: Build the Volume artifact directly from the marketplace plugin tree, selecting which plugins/skills to include and generating manifest.json from the plugin definitions

### Modified Capabilities
- `mcp-env-substitution`: Extend the existing `substitute_token()` to handle arbitrary env-var placeholders beyond just `${ACCESS_TOKEN}`, since the plugin `.mcp.json` uses `${SLACK_MCP_URL}`, `${DATABRICKS_HOST}`, `${DATABRICKS_TOKEN}`, etc.

## Impact

- **`cowork/skills/`**: Deleted entirely
- **`cowork/scripts/build-artifact.sh`**: Rewritten to read from `plugins/` tree
- **`cowork/app/core/skills.py`**: `substitute_token()` generalized for arbitrary env vars
- **`cowork/references/volume-setup.md`**: Updated docs
- **`cowork/Makefile`**: `build-artifact` target updated for new script interface
- **No runtime API changes**: The Volume artifact format (`latest.json`, `manifest.json`, skills dirs, `.mcp.json`) stays identical — only the source changes
