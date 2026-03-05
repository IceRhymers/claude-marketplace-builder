# Lakebase Setup Guide

## Prerequisites

- Databricks workspace with Lakebase enabled
- Service principal with appropriate permissions
- Databricks SDK configured

## Creating a Lakebase Provisioned Instance

### Via DABs (Recommended)

The `resources/lakebase.yml` bundle config manages the Lakebase Provisioned instance
and catalog automatically. Just deploy the bundle:

```bash
cd usage-limits
databricks bundle deploy -t dev
```

This creates:
- A `database_instances` resource (`usage-limits`) with CU_1 capacity
- A `database_catalogs` resource (`usage_limits`) linked to the instance

### Manual (via SDK)

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Create a Lakebase Provisioned instance
instance = w.database.create_instance(
    name="usage-limits",
    capacity="CU_1",
)

# Create a catalog on the instance
catalog = w.database.create_catalog(
    database_instance_name=instance.name,
    name="usage_limits",
    database_name="databricks_postgres",
    create_database_if_not_exists=True,
)

print(f"Instance: {instance.name}")
print(f"Catalog: {catalog.name}")
```

## Environment Variables

The app `database` resource in `resources/app.yml` auto-injects standard PG env vars.
Set these in `app.yaml`:

| Variable | Description | Source |
|----------|-------------|--------|
| `PGHOST` | Lakebase hostname | Auto-injected from `usage-limits-db` |
| `PGDATABASE` | Database name | Auto-injected from `usage-limits-db` |
| `PGUSER` | Service principal client ID | Injected at connect time via `WorkspaceClient.config.client_id` |
| `LAKEBASE_INSTANCE` | Instance name for credential generation | Hardcoded in `app.yml` |

## Credential Generation

The app uses `database.generate_database_credential()` with the instance name
to get short-lived OAuth tokens for PostgreSQL connections. This is handled
automatically by `OAuthConnection` in `core/db.py`.

## Schema Initialization

The app automatically creates tables on first startup via `init_schema()`.

## Tables Created

1. `budget_configs` — Per-user/group budget limits
2. `default_budgets` — Fallback budget limits
3. `warnings` — Users over-budget with expiry tracking
4. `audit_log` — Enforcement action history
5. `app_config` — App settings
