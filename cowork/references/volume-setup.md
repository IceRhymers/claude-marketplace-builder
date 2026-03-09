# Unity Catalog Volume Setup

The `cowork` reads skill definitions and MCP configuration from a Databricks Unity Catalog Volume. This document describes the expected Volume path convention and how to set it up.

## Volume Path Convention

The `SKILLS_VOLUME_PATH` environment variable should point to a Unity Catalog Volume path following this convention:

```
/Volumes/<catalog>/<schema>/<volume_name>
```

Example:
```
/Volumes/main/claude_agent/marketplace
```

## Directory Layout

```
/Volumes/catalog/schema/marketplace/
├── latest.json                    # Points to current artifact version
└── artifacts/
    └── v1.2.3/                    # Versioned artifact directory
        ├── skills/
        │   ├── getting-started/
        │   │   └── SKILL.md
        │   ├── databricks-lineage/
        │   │   ├── SKILL.md
        │   │   └── scripts/
        │   └── ...
        ├── .mcp.json              # Merged from all plugin .mcp.json files
        └── manifest.json
```

## latest.json Schema

```json
{
  "version": "v1.2.3",
  "path": "artifacts/v1.2.3",
  "published_at": "2024-01-01T00:00:00Z"
}
```

- `version`: Semantic version or git SHA
- `path`: Path to the artifact directory **relative to** `SKILLS_VOLUME_PATH`
- `published_at`: ISO 8601 UTC timestamp

## Artifact Source

The artifact is built from the marketplace plugin tree at `plugins/*/` in the repo root. The build script:

1. Discovers plugins by reading each `plugins/<name>/.claude-plugin/plugin.json`
2. Copies all skill directories from each plugin's `skills/` path
3. Merges `.mcp.json` files from all plugin roots into a single MCP config
4. Generates `manifest.json` with skill metadata

This means **skills are authored in `plugins/*/skills/`** — the same location used by the Claude Code plugin system. There is no separate skill directory in the cowork app.

## MCP Configuration

The merged `.mcp.json` may contain `${VAR}` placeholders that are resolved at runtime:

- `${ACCESS_TOKEN}` — replaced with the user's OAuth token
- `${DATABRICKS_HOST}`, `${GENIE_SPACE_ID}`, etc. — resolved from app environment variables
- `${VAR:-default}` — uses `default` if `VAR` is not set in the environment

## One-Time Setup

1. Create the Unity Catalog Volume (requires `CREATE VOLUME` privilege on the schema):

   ```sql
   CREATE VOLUME main.claude_agent.marketplace;
   ```

2. Set `SKILLS_VOLUME_PATH` in `app/app.yml`:

   ```yaml
   - name: SKILLS_VOLUME_PATH
     value: "/Volumes/main/claude_agent/marketplace"
   ```

3. Build and publish the initial skills artifact:

   ```bash
   cd cowork
   make build-artifact VERSION=v0.1.0
   # Upload to the volume (requires Databricks CLI)
   databricks fs cp dist/v0.1.0.tar.gz /Volumes/main/claude_agent/marketplace/artifacts/v0.1.0/v0.1.0.tar.gz
   databricks fs cp dist/latest.json /Volumes/main/claude_agent/marketplace/latest.json
   ```

## Hot Reload

The app checks `latest.json` every `SKILLS_RELOAD_INTERVAL_SECONDS` (default: 60 seconds). To deploy a new skill set without restarting the app:

1. Build and publish a new artifact with a new version string
2. Upload the tarball to `artifacts/<new-version>/`
3. Overwrite `latest.json` with the new version pointer
4. The app automatically picks it up within 60 seconds

## Permissions

The app service principal (Databricks App identity) needs `READ FILES` on the Volume:

```sql
GRANT READ FILES ON VOLUME main.claude_agent.marketplace TO `cowork`;
```
