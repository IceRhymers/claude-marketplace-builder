#!/bin/bash
set -euo pipefail

# Require Databricks auth — skip silently if not configured
if [ -z "${DATABRICKS_HOST:-}" ] || [ -z "${DATABRICKS_TOKEN:-}" ] || [ -z "${CLAUDE_ENV_FILE:-}" ]; then
  echo "EXIT"
  exit 0
fi

# Shared destination — override via CLAUDE_OTEL_UC_TABLE env var if needed
UC_TABLE="${CLAUDE_OTEL_UC_TABLE:-main.claude_telemetry.claude_otel_metrics}"

# Strip trailing slash from host
DB_HOST="${DATABRICKS_HOST%/}"

cat >> "$CLAUDE_ENV_FILE" <<EOF
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_METRICS_PROTOCOL="http/protobuf"
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="${DB_HOST}/api/2.0/otel/v1/metrics"
export OTEL_EXPORTER_OTLP_METRICS_HEADERS="content-type=application/x-protobuf,Authorization=Bearer ${DATABRICKS_TOKEN},X-Databricks-UC-Table-Name=${UC_TABLE}"
EOF

exit 0
