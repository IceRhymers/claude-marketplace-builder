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
        │   └── getting-started/
        │       └── SKILL.md
        └── .mcp.json
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

3. Publish the initial skills artifact:

   ```bash
   cd cowork
   ./scripts/build-artifact.sh v0.1.0
   # Then upload to the volume (requires Databricks CLI)
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
