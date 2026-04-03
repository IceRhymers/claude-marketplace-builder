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

2. Check if Databricks credentials are available and show token source:
   ```bash
   [ -n "${DATABRICKS_HOST:-}" ] && echo "DATABRICKS_HOST=${DATABRICKS_HOST}" || echo "DATABRICKS_HOST=NOT SET"
   [ -n "${DATABRICKS_TOKEN:-}" ] && echo "DATABRICKS_TOKEN is set" || echo "DATABRICKS_TOKEN=NOT SET"
   [ -n "${DATABRICKS_CONFIG_PROFILE:-}" ] && echo "DATABRICKS_CONFIG_PROFILE=${DATABRICKS_CONFIG_PROFILE}" || echo "DATABRICKS_CONFIG_PROFILE=NOT SET (using DEFAULT)"
   ```

3. Check if OTEL vars exist in `~/.claude/settings.json` and check token age:
   ```bash
   jq '.env | with_entries(select(.key | startswith("OTEL") or . == "CLAUDE_CODE_ENABLE_TELEMETRY"))' ~/.claude/settings.json 2>/dev/null || echo "Could not read settings.json"
   # Check when settings.json was last modified (proxy for token age)
   if [ -f "$HOME/.claude/settings.json" ]; then
     mod_time=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$HOME/.claude/settings.json" 2>/dev/null || stat -c "%y" "$HOME/.claude/settings.json" 2>/dev/null | cut -d. -f1)
     echo "settings.json last modified: $mod_time"
     # Calculate age in minutes
     mod_epoch=$(stat -f "%m" "$HOME/.claude/settings.json" 2>/dev/null || stat -c "%Y" "$HOME/.claude/settings.json" 2>/dev/null)
     now_epoch=$(date +%s)
     age_minutes=$(( (now_epoch - mod_epoch) / 60 ))
     echo "Approximate token age: ${age_minutes} minutes"
     if [ "$age_minutes" -gt 50 ]; then
       echo "WARNING: Token may be near or past the ~1 hour OAuth expiry. Consider restarting Claude Code."
     fi
   fi
   ```

4. Based on findings, guide the user:
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
   - **Token age > 50 minutes**: Restart Claude Code to obtain a fresh OAuth token. OTEL metrics stop exporting silently after ~1 hour without notification.
   - **Token rotation needed**: Re-run `configure-otel.sh` to recompute OTEL headers with the new token.

5. Report the status with clear next steps. Remind the user that:
   - OTEL env vars must be in `~/.claude/settings.json` (not set via hooks) because they are needed before Claude Code starts.
   - The OTEL OAuth token expires after ~1 hour. If the session has been running longer than 50 minutes, recommend restarting Claude Code to restore telemetry export.
   - The active profile is shown by `DATABRICKS_CONFIG_PROFILE` (defaults to `DEFAULT` if unset).
