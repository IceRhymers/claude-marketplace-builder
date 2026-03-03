# OTEL Metrics Setup Guide

## Overview

The OTEL integration is **optional** and provides deeper Claude Code-specific telemetry
beyond the token counts available in system tables.

## Configuration

Set the `OTEL_TABLE` environment variable in `app.yaml` to the fully-qualified
name of your OTEL metrics table:

```yaml
env:
  - name: OTEL_TABLE
    value: "my_catalog.my_schema.claude_otel_metrics"
```

If left empty, the OTEL page will show a configuration prompt instead.

## Table Schema

The app expects an OTEL metrics table with the standard OpenTelemetry schema:

| Column | Type | Description |
|--------|------|-------------|
| `name` | STRING | Metric name (e.g., `gen_ai.client.token.usage`) |
| `sum.value` | DOUBLE | Metric value for monotonic counters |
| `sum.time_unix_nano` | BIGINT | Timestamp in nanoseconds |
| `sum.attributes` | MAP | Key-value attributes including `user.id` |
| `gauge.value` | DOUBLE | Point-in-time metric value |
| `gauge.attributes` | MAP | Key-value attributes |

## Key Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `gen_ai.client.token.usage` | sum | Token consumption per request |
| `gen_ai.client.operation.duration` | histogram | Request latency |

## Validation

After configuring, verify access:

```python
from setup.validate_access import validate_otel_access
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
ok = validate_otel_access(w, "<warehouse-id>", "my_catalog.my_schema.claude_otel_metrics")
print(f"OTEL access: {'OK' if ok else 'FAILED'}")
```
