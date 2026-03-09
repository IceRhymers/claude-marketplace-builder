## Context

The cowork Databricks App runs a Claude Agent SDK-backed chat interface. At runtime, it loads skills and MCP server configs from a versioned artifact on a Unity Catalog Volume (`SKILLS_VOLUME_PATH`). Currently, the artifact is built from a separate `cowork/skills/` directory via `scripts/build-artifact.sh`, but the repo's actual skill marketplace lives under `plugins/*/skills/` with metadata in each plugin's `plugin.json` and a root `marketplace.json`.

The result is two parallel skill trees — one authoritative (the marketplace plugins) and one derivative (cowork/skills). Only the `getting-started` skill exists in `cowork/skills/` today, and it's not even in the marketplace.

## Goals / Non-Goals

**Goals:**
- Single source of truth: the marketplace `plugins/` tree is the only place skills are authored
- `build-artifact.sh` reads from `plugins/` and produces the same Volume artifact format (no runtime changes)
- MCP `.mcp.json` sourced from `plugins/databricks-mcp/.mcp.json` with env-var placeholders resolved at runtime
- Generalize `substitute_token()` to handle arbitrary `${VAR}` patterns, not just `${ACCESS_TOKEN}`

**Non-Goals:**
- Changing the Volume artifact format (`latest.json`, `manifest.json`, skills dirs, `.mcp.json`)
- Changing how the runtime loads/reloads from the Volume (the `SkillsConfig` / `reload_if_changed` path is untouched)
- Adding new skills or MCP servers as part of this change
- Automating the Volume upload (that stays manual via `databricks fs cp`)

## Decisions

### 1. Build script reads plugin.json files to discover skills

The build script will walk `plugins/*/` directories, read each `.claude-plugin/plugin.json` to get the skill list, and copy skill directories from each plugin's `skills/` path. This keeps the manifest generation driven by the same metadata the Claude Code plugin system uses.

**Alternative considered**: Globbing `plugins/*/skills/*/SKILL.md` without reading plugin.json. Rejected because plugin.json is the authoritative registry and some plugins may have non-skill content in their skills dir.

### 2. MCP config merged from plugin .mcp.json files

The build script will look for `.mcp.json` at each plugin root and merge all `mcpServers` entries into a single `.mcp.json` in the artifact. Currently only `plugins/databricks-mcp/.mcp.json` has MCP servers.

**Alternative considered**: Hardcoding the MCP source path. Rejected because the merge approach naturally supports future plugins adding their own MCP servers.

### 3. Generalize substitute_token() to substitute all ${VAR} patterns

Instead of only replacing `${ACCESS_TOKEN}`, the function will regex-match `${...}` patterns and resolve them from a provided env dict. `${ACCESS_TOKEN}` remains a special case resolved from the user's OAuth token; all others come from `os.environ`. This covers `${SLACK_MCP_URL}`, `${DATABRICKS_HOST}`, `${DATABRICKS_TOKEN}`, `${GENIE_SPACE_ID}`, etc.

**Alternative considered**: Resolving env vars at artifact build time. Rejected because the same artifact must work across environments (dev/prod) and the MCP URLs/tokens are deployment-specific.

### 4. Remove cowork/skills/ entirely

The `getting-started` skill either moves to an appropriate marketplace plugin or is dropped. Since it's a generic onboarding skill for the cowork app specifically, it could go into a new `plugins/cowork/` plugin or into `plugins/internal-skills/`. Decision: move it to `plugins/internal-skills/skills/getting-started/` since it's an internal onboarding concern.

## Risks / Trade-offs

- **[Build script depends on plugin structure]** → If plugin directory conventions change, the build script breaks. Mitigation: the script reads `plugin.json` metadata rather than hardcoding paths, so it adapts to renames.
- **[MCP merge conflicts]** → If two plugins define the same MCP server name, last-write-wins. Mitigation: unlikely today (only one MCP plugin), and the build script can warn on duplicates.
- **[Env var resolution at runtime means missing vars = broken MCP]** → If `DATABRICKS_HOST` isn't set, the MCP URL is literally `${DATABRICKS_HOST}/api/...`. Mitigation: `substitute_token()` already logs warnings; we can add startup validation for required env vars.
