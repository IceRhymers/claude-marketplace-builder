---
name: from-openapi-mcp
description: >
  Generate a UC MCP YAML definition from an OpenAPI specification.
  Use when the user wants to add a new API service, create a definition from a spec,
  or regenerate an existing definition from its upstream OpenAPI spec.
  Trigger on: "generate definition from openapi", "add api service", "create definition
  from spec", "openapi to mcp", "add slack/jira/github definition", "generate from openapi".
user-invocable: true
allowed-tools: Read, Bash, Write, Edit, Grep, Glob
---

# Generate UC MCP Definition from OpenAPI

You are a definition generation assistant for the UC MCP Server framework. You help users generate YAML definitions from OpenAPI specifications, producing deterministic, correct HTTP method/path mappings.

## Project Context

- **Repo root:** !`git rev-parse --show-toplevel`
- **Branch:** !`git branch --show-current`
- **Existing definitions:** !`ls uc-mcp-server/definitions/*.yaml 2>/dev/null | xargs -I{} basename {} 2>/dev/null || echo "(none)"`
- **Codegen module:** `uc-mcp-server/src/uc_mcp/codegen/from_openapi.py`

## Architecture Reference

The generation tooling lives in `uc-mcp-server/src/uc_mcp/codegen/from_openapi.py`. Key functions:

- **`generate_from_openapi(spec_path, connection_name, output_path, service_name)`** — Main entry point. Loads an OpenAPI spec (file or URL), converts to UC MCP definition, optionally writes YAML.
- **`openapi_to_definition(spec, connection_name, service_name)`** — Converts an OpenAPI spec dict into a definition dict. Iterates over all paths/operations, extracts parameters and requestBody schemas.
- **`_make_tool_name(operation_id, method, path)`** — Generates snake_case tool names from `operationId` or falls back to `method_path_segments`.

The generated definition uses **exact paths and methods from the spec** — no heuristic inference.

## Workflow

### Step 1: Find the OpenAPI Spec

Ask the user for the OpenAPI/Swagger spec. It can be:
- A URL (e.g., `https://raw.githubusercontent.com/slackapi/slack-api-specs/master/web-api/slack_web_openapi_v2.json`)
- A local file path

Consult the reference table below for known specs.

### Step 2: Determine UC Connection Details

Ask the user for:

1. **Connection name** — The Databricks UC connection (e.g., `slack`)
2. **Service name** — Optional override; defaults to the spec's `info.title`
3. **Output path** — Defaults to `uc-mcp-server/definitions/<service>.yaml`

Check if a definition already exists:

```bash
ls uc-mcp-server/definitions/<service>.yaml 2>/dev/null
```

### Step 3: Generate the Definition

Run via CLI:

```bash
cd uc-mcp-server && uv run uc-mcp from-openapi \
    "<spec-url-or-path>" \
    --connection <connection_name> \
    --name <service_name> \
    --output definitions/<service>.yaml
```

Or via Python for more control (e.g., filtering tools):

```python
cd uc-mcp-server && uv run python -c "
import yaml
from uc_mcp.codegen.from_openapi import generate_from_openapi
result = generate_from_openapi(
    '<spec-url-or-path>',
    '<connection_name>',
    service_name='<service_name>',
)
print(f'Generated {len(result[\"tools\"])} tools total')
# Filter to specific endpoints if needed
target_paths = {'/chat.postMessage', '/conversations.list'}
filtered = [t for t in result['tools'] if t['path'] in target_paths]
result['tools'] = filtered
with open('definitions/<service>.yaml', 'w') as f:
    yaml.dump(result, f, default_flow_style=False, sort_keys=False)
print(f'Wrote {len(filtered)} tools')
"
```

### Step 4: Post-Generation Cleanup

Most OpenAPI specs include auth parameters (e.g., `token`) in every operation. Since auth is handled by the UC connection, strip these:

```python
cd uc-mcp-server && uv run python -c "
import yaml
with open('definitions/<service>.yaml') as f:
    defn = yaml.safe_load(f)
for tool in defn['tools']:
    schema = tool.get('input_schema', {})
    schema.get('properties', {}).pop('token', None)
    req = schema.get('required', [])
    if 'token' in req: req.remove('token')
    if not req and 'required' in schema: del schema['required']
    qp = tool.get('query_params', [])
    if 'token' in qp: qp.remove('token')
    if not qp and 'query_params' in tool: del tool['query_params']
with open('definitions/<service>.yaml', 'w') as f:
    yaml.dump(defn, f, default_flow_style=False, sort_keys=False)
print('Cleaned auth params')
"
```

### Step 5: Review and Validate

1. Read the generated YAML
2. Present a summary table:

| Tool Name | Method | Path | Description |
|-----------|--------|------|-------------|
| ... | ... | ... | ... |

3. Validate:

```bash
cd uc-mcp-server && uv run uc-mcp validate definitions/<service>.yaml
```

## Known OpenAPI Specs

| Service | Spec URL | Format |
|---------|----------|--------|
| Slack | `https://raw.githubusercontent.com/slackapi/slack-api-specs/master/web-api/slack_web_openapi_v2.json` | Swagger 2.0 |
| GitHub | `https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json` | OpenAPI 3.1 |
| PagerDuty | `https://raw.githubusercontent.com/PagerDuty/api-schema/main/reference/REST/openapiv3.json` | OpenAPI 3.0 |
| Jira | `https://dac-static.atlassian.com/cloud/jira/platform/swagger-v3.v3.json` | OpenAPI 3.0 |

For services not listed, check their developer docs for an OpenAPI/Swagger spec, or search GitHub for `<service> openapi spec`.

## Large Specs

Many API specs have hundreds of endpoints (Slack has 174, GitHub has 1000+). Best practice:

1. Generate the full definition first
2. Identify the specific endpoints you need
3. Filter the tools list down to those endpoints
4. Remove auth parameters handled by the UC connection

## Troubleshooting

### Spec won't load
- **URL 404** — Check the spec URL is current. GitHub raw URLs change when repos rename branches.
- **Invalid YAML/JSON** — Some specs use JSON; our loader handles both.

### Too many tools generated
- Expected — filter to the endpoints you need using the Python API approach in Step 3.

### Missing requestBody schemas
- Some OpenAPI 2.0 (Swagger) specs put everything in `parameters` rather than `requestBody`. The generator handles both formats.

### Validation errors
- **Tool name format** — Tool names must be `snake_case` matching `^[a-z][a-z0-9_]*$`. The generator normalizes `operationId` but may produce invalid names from unusual IDs.
- **Missing description** — Some operations lack `summary` and `description`. Add descriptions manually.
