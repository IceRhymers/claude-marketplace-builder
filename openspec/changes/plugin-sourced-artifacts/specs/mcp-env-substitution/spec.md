## ADDED Requirements

### Requirement: Substitute arbitrary env-var placeholders in MCP config
The `substitute_token()` function (or its replacement) SHALL resolve all `${VARIABLE_NAME}` patterns in MCP server configuration values, not just `${ACCESS_TOKEN}`.

#### Scenario: ACCESS_TOKEN substitution still works
- **WHEN** MCP config contains `"Authorization": "Bearer ${ACCESS_TOKEN}"` and access_token is `"tok123"`
- **THEN** the result contains `"Authorization": "Bearer tok123"`

#### Scenario: Environment variable substitution
- **WHEN** MCP config contains `"url": "${DATABRICKS_HOST}/api/2.0/mcp/genie/${GENIE_SPACE_ID}"` and env has `DATABRICKS_HOST=https://myhost.cloud.databricks.com` and `GENIE_SPACE_ID=abc123`
- **THEN** the result contains `"url": "https://myhost.cloud.databricks.com/api/2.0/mcp/genie/abc123"`

#### Scenario: Unresolvable placeholder with default
- **WHEN** MCP config contains `"${SLACK_MCP_URL:-https://default.example.com/mcp/}"` and `SLACK_MCP_URL` is not set in the environment
- **THEN** the result uses the default value `https://default.example.com/mcp/`

#### Scenario: Unresolvable placeholder without default
- **WHEN** MCP config contains `"${MISSING_VAR}"` and `MISSING_VAR` is not set and no default is specified
- **THEN** the placeholder is left as-is (`${MISSING_VAR}`) and a warning is logged

### Requirement: Token takes precedence over env for ACCESS_TOKEN
The user's OAuth `access_token` parameter SHALL always be used for `${ACCESS_TOKEN}`, even if an `ACCESS_TOKEN` environment variable exists.

#### Scenario: ACCESS_TOKEN env var ignored in favor of parameter
- **WHEN** `os.environ["ACCESS_TOKEN"]` is `"env-token"` and `access_token` parameter is `"oauth-token"`
- **THEN** `${ACCESS_TOKEN}` resolves to `"oauth-token"`
