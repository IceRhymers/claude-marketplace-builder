# Lakebase Setup Guide

## Prerequisites

- Databricks workspace with Lakebase enabled
- Service principal with appropriate permissions
- Databricks SDK configured

## Creating a Lakebase Project

### Automated (Recommended)

```bash
cd plugins/databricks-skills/skills/usage-limits
python -m scripts.setup_lakebase --name usage-limits
```

### Manual (via SDK)

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Create project
project = w.postgres.create_project(name="usage-limits")

# Create endpoint
endpoint = w.postgres.create_endpoint(
    project_name=project.name,
    branch_name="main",
)

# Use these values in app.yaml env vars
print(f"PGHOST: {endpoint.host}")
print(f"PGDATABASE: {endpoint.database}")
print(f"LAKEBASE_ENDPOINT: {endpoint.endpoint}")
```

## Environment Variables

Set these in `app.yaml`:

| Variable | Description | Example |
|----------|-------------|---------|
| `PGHOST` | Lakebase hostname | `abc123.cloud.databricks.com` |
| `PGDATABASE` | Database name | `databricks_postgres` |
| `PGUSER` | Service principal client ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `LAKEBASE_ENDPOINT` | Endpoint path | `projects/usage-limits/branches/main/endpoints/ep-1` |

## Schema Initialization

The app automatically creates tables on first startup via `init_schema()`.
To initialize manually:

```bash
cd app && python -m setup.init_schema
```

## Tables Created

1. `budget_configs` — Per-user/group budget limits
2. `default_budgets` — Fallback budget limits
3. `blacklist` — Users over-budget with expiry tracking
4. `managed_endpoints` — Endpoints being monitored
5. `permission_snapshots` — Original user permissions (before revocation)
6. `audit_log` — Enforcement action history
7. `app_config` — App settings
