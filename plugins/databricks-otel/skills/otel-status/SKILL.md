---
name: otel-status
description: >
  Check whether Claude Code OTEL telemetry is configured correctly for export
  to Databricks. Use this when telemetry is not appearing in the target Unity
  Catalog table, or to verify OTEL setup after running configure-otel.sh.
user-invocable: true
allowed-tools: Bash, Read
---

# OTEL Status

Diagnose whether OTEL telemetry env vars are configured in the current Claude Code session.

## Execution

1. Check if the required OTEL env vars are set:
   ```bash
   echo "CLAUDE_CODE_ENABLE_TELEMETRY=${CLAUDE_CODE_ENABLE_TELEMETRY:-NOT SET}"
   echo "OTEL_METRICS_EXPORTER=${OTEL_METRICS_EXPORTER:-NOT SET}"
   echo "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL=${OTEL_EXPORTER_OTLP_METRICS_PROTOCOL:-NOT SET}"
   [ -n "${OTEL_EXPORTER_OTLP_METRICS_ENDPOINT:-}" ] && echo "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT is set" || echo "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=NOT SET"
   [ -n "${OTEL_EXPORTER_OTLP_METRICS_HEADERS:-}" ] && echo "OTEL_EXPORTER_OTLP_METRICS_HEADERS is set" || echo "OTEL_EXPORTER_OTLP_METRICS_HEADERS=NOT SET"
   ```

2. Check if Databricks credentials are available:
   ```bash
   [ -n "${DATABRICKS_HOST:-}" ] && echo "DATABRICKS_HOST=${DATABRICKS_HOST}" || echo "DATABRICKS_HOST=NOT SET"
   [ -n "${DATABRICKS_TOKEN:-}" ] && echo "DATABRICKS_TOKEN is set" || echo "DATABRICKS_TOKEN=NOT SET"
   [ -n "${DATABRICKS_CONFIG_PROFILE:-}" ] && echo "DATABRICKS_CONFIG_PROFILE=${DATABRICKS_CONFIG_PROFILE}" || echo "DATABRICKS_CONFIG_PROFILE=NOT SET"
   ```

3. Check if OTEL vars exist in `~/.claude/settings.json`:
   ```bash
   jq '.env | with_entries(select(.key | startswith("OTEL") or . == "CLAUDE_CODE_ENABLE_TELEMETRY"))' ~/.claude/settings.json 2>/dev/null || echo "Could not read settings.json"
   ```

4. Detect token type and check token age:
   ```bash
   # Detect whether using a PAT or OAuth
   if [ -n "${DATABRICKS_TOKEN:-}" ] && ! databricks auth token --profile "${DATABRICKS_CONFIG_PROFILE:-DEFAULT}" >/dev/null 2>&1; then
     echo "Token type: PAT (DATABRICKS_TOKEN env var set, no working CLI profile)"
     echo "PATs are long-lived (typically 90 days). No restart-based refresh needed."
   elif [ -n "${DATABRICKS_CONFIG_PROFILE:-}" ] && databricks auth token --profile "${DATABRICKS_CONFIG_PROFILE}" >/dev/null 2>&1; then
     echo "Token type: OAuth (CLI profile ${DATABRICKS_CONFIG_PROFILE} active)"
     echo "OAuth tokens expire after ~1 hour. Restart Claude Code if telemetry stops."
   elif [ -n "${DATABRICKS_TOKEN:-}" ]; then
     echo "Token type: PAT (DATABRICKS_TOKEN env var set)"
     echo "PATs are long-lived (typically 90 days). No restart-based refresh needed."
   else
     echo "Token type: Unknown — neither DATABRICKS_TOKEN nor a working CLI profile detected"
   fi
   ```

5. Based on findings, guide the user:
   - **OTEL vars missing from settings.json**: Run the configure script:
     ```bash
     bash scripts/configure-otel.sh
     # Or: make configure-otel
     ```
   - **OTEL vars in settings.json but not in env**: Restart Claude Code — settings.json is read at startup.
   - **Databricks credentials missing**: Run inference configuration first:
     ```bash
     bash scripts/configure-inference.sh
     # Or: make configure
     ```
   - **Token rotation needed (OAuth)**: Restart Claude Code to obtain a fresh OAuth token.
   - **Token rotation needed (PAT)**: Your PAT is long-lived. If expired, generate a new PAT in Databricks and re-run `configure-otel.sh`.

6. Report the status with clear next steps. Remind the user:
   - OTEL env vars must be in `~/.claude/settings.json` (not set via hooks) because they are needed before Claude Code starts.
   - If using OAuth (via claude-db or CLI profile), token expires after ~1 hour. Restart Claude Code to refresh.
   - If using a PAT, token is long-lived (typically 90 days). Check your workspace PAT settings for exact expiry.
