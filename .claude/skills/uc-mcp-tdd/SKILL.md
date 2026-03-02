---
name: uc-mcp-tdd
description: >
  Guide TDD (test-driven development) workflow for the UC MCP Server framework.
  Use when developing new features, adapters, definitions, or bug fixes in uc-mcp-server/.
  Covers writing failing tests first, implementing minimum code to pass, refactoring,
  and validating YAML definitions. Trigger on: "add a tool", "new adapter", "new definition",
  "fix uc-mcp", "test uc-mcp", "uc mcp server", "TDD for mcp".
user-invocable: true
allowed-tools: Read, Bash, Write, Edit, Grep, Glob
---

# UC MCP Server TDD Workflow

You are a TDD coach for the UC MCP Server framework at `uc-mcp-server/`. Follow Red-Green-Refactor strictly: write failing tests first, then implement the minimum code to pass, then refactor.

## Project Context

- Root: \!`git rev-parse --show-toplevel`
- Branch: \!`git branch --show-current`
- Test status: \!`cd uc-mcp-server && uv run pytest --tb=no -q 2>&1 | tail -5`

## Architecture

```
uc-mcp-server/
├── src/uc_mcp/
│   ├── __main__.py        CLI entry point (serve, validate, from-openapi, build)
│   ├── schema.py          YAML definition validation (jsonschema + dataclasses)
│   ├── connection.py      UCConnection wrapping w.serving_endpoints.http_request()
│   ├── engine.py          Dynamic tool registration: YAML → MCP tools
│   ├── server.py          Assembles MCP Server from definition + connection
│   └── codegen/
│       └── from_openapi.py  OpenAPI spec → YAML definition
├── definitions/           YAML adapter definitions (the "code" for each service)
│   ├── _schema.yaml       JSON Schema governing all definitions
│   └── slack.yaml         Slack tools (7 tools)
├── tests/
│   ├── conftest.py        Shared fixtures (mock WorkspaceClient, paths)
│   ├── test_schema.py     Schema validation
│   ├── test_connection.py UCConnection with mocked Databricks SDK
│   ├── test_engine.py     Dynamic tool registration + handler execution
│   ├── test_server.py     Integration: YAML → running MCP server
│   ├── test_from_openapi.py  OpenAPI → YAML conversion
│   └── fixtures/          Test YAML definitions
└── build/build.sh         PEX builder
```

## Module Dependency Chain

Changes flow downward. Always start tests at the lowest affected layer.

```
schema.py          ← Foundation: dataclasses + validation
    ↓
connection.py      ← Transport: UCConnection wraps Databricks SDK
    ↓
engine.py          ← Core: dynamic tool registration from parsed YAML
    ↓
server.py          ← Assembly: wires engine + connection into FastMCP
    ↓
__main__.py        ← CLI: subcommands calling the above
    ↓
codegen/*.py       ← Generation: OpenAPI spec → YAML definitions
```

## TDD Cycle

### Phase 1: RED (Write Failing Test)

Before writing ANY implementation code:

1. **Identify** the feature, bug fix, or behavior to add
2. **Find** the correct test file from the mapping:

   | Change Area | Test File | Source File |
   |------------|-----------|-------------|
   | YAML schema, dataclasses, validation | `test_schema.py` | `schema.py` |
   | HTTP transport, request/response | `test_connection.py` | `connection.py` |
   | Tool registration, path building, response formatting | `test_engine.py` | `engine.py` |
   | FastMCP assembly, end-to-end | `test_server.py` | `server.py` |
   | OpenAPI conversion | `test_from_openapi.py` | `codegen/from_openapi.py` |

3. **Write** the test with a descriptive name: `test_<behavior>_<scenario>`
4. **Run** the test to confirm it FAILS:
   ```bash
   cd uc-mcp-server && uv run pytest tests/test_<module>.py -k "test_name" -v
   ```
5. **Verify** it fails for the RIGHT reason (expected behavior not implemented), not an import error or fixture problem

### Phase 2: GREEN (Minimum Implementation)

1. Write the MINIMUM code to make the failing test pass
2. Do NOT add extra functionality, error handling, or "nice to haves"
3. Run ONLY the failing test:
   ```bash
   cd uc-mcp-server && uv run pytest tests/test_<module>.py -k "test_name" -v
   ```
4. If it passes, move to Phase 3
5. If it still fails, iterate — do not write more tests yet

### Phase 3: REFACTOR

1. Review the implementation:
   - Remove duplication
   - Improve naming
   - Add type annotations to public functions
   - Add docstrings to public functions
2. Run the FULL test suite to catch regressions:
   ```bash
   cd uc-mcp-server && uv run pytest -v
   ```
3. All tests must remain green after refactoring
4. If any test breaks, fix the refactor — do not modify the test

### Repeat

Go back to Phase 1 for the next piece of functionality. Each cycle should be small (1 behavior, 1 test, 1 implementation).

## Common Workflows

### Adding a New YAML Definition (e.g., Jira, PagerDuty)

1. **Write the definition** at `uc-mcp-server/definitions/<service>.yaml`
2. **Validate** it:
   ```bash
   cd uc-mcp-server && uv run uc-mcp validate definitions/<service>.yaml
   ```
3. **Copy to fixtures** at `tests/fixtures/<service>_definition.yaml`
4. **TDD cycle** — add tests to `test_schema.py`:
   ```python
   def test_load_<service>_definition(self, fixtures_dir):
       defn = load_definition(fixtures_dir / "<service>_definition.yaml")
       assert defn.name == "<service>"
       assert len(defn.tools) == <N>
   ```
5. **TDD cycle** — add tests to `test_engine.py` for any new patterns (e.g., new response format, auth headers)
6. **TDD cycle** — add integration test to `test_server.py`:
   ```python
   def test_build_server_with_<service>_definition(self, fixtures_dir, mock_workspace_client):
       with patch("uc_mcp.connection.WorkspaceClient", return_value=mock_workspace_client):
           mcp = build_server(fixtures_dir / "<service>_definition.yaml")
       assert "<service>" in mcp.name
   ```
7. **Run full suite**: `cd uc-mcp-server && uv run pytest -v`

### Adding a New Schema Feature (e.g., auth config, rate limits)

1. **Update** `definitions/_schema.yaml` with the new field
2. **TDD cycle** on `test_schema.py`:
   - Test that valid definitions with the new field pass
   - Test that invalid values are rejected
3. **TDD cycle** on `test_engine.py` or `test_connection.py` (if the feature affects runtime behavior)
4. **Update** affected YAML definitions and fixtures

### Adding a New Engine Feature (e.g., pagination, retry)

1. Follow the dependency chain: does this need schema changes first?
2. **TDD cycle** on the lowest affected layer
3. Work upward through the chain

### Generating from OpenAPI Spec

1. **Run** generation:
   ```bash
   cd uc-mcp-server && uv run uc-mcp from-openapi <spec-url-or-file> --connection <conn-name> --name <service> -o definitions/<service>.yaml
   ```
2. **Review** the generated YAML — filter to only the tools you need, strip auth params (e.g., `token`) handled by UC connection
3. **Validate**: `uv run uc-mcp validate definitions/<service>.yaml`
4. Follow "Adding a New YAML Definition" workflow above

### Building a .pex

```bash
cd uc-mcp-server && bash build/build.sh definitions/<service>.yaml
# With bundled Python interpreter:
cd uc-mcp-server && bash build/build.sh definitions/<service>.yaml --scie
```

## Test Fixtures

All test YAML files live in `uc-mcp-server/tests/fixtures/`:

| File | Purpose |
|------|---------|
| `simple_definition.yaml` | Minimal valid definition (2 tools, GET + POST) |
| `slack_definition.yaml` | Real-world Slack example with response config |
| `invalid_definitions/` | Files that MUST fail validation |

When adding a fixture, also add at least one test that loads it.

## Commands Reference

```bash
# Install deps
cd uc-mcp-server && uv sync

# Run all tests
cd uc-mcp-server && uv run pytest -v

# Run one test file
cd uc-mcp-server && uv run pytest tests/test_engine.py -v

# Run one test by name
cd uc-mcp-server && uv run pytest -k "test_build_path_simple" -v

# Run with coverage
cd uc-mcp-server && uv run pytest --cov=uc_mcp --cov-report=term-missing

# Validate a definition
cd uc-mcp-server && uv run uc-mcp validate definitions/slack.yaml

# Serve (manual testing against a real Databricks workspace)
cd uc-mcp-server && uv run uc-mcp serve definitions/slack.yaml -v

# Generate from OpenAPI spec
cd uc-mcp-server && uv run uc-mcp from-openapi spec.json --connection conn-name -o output.yaml

# Build .pex
cd uc-mcp-server && bash build/build.sh definitions/slack.yaml

# Makefile shortcuts (from repo root)
make uc-mcp-test
make uc-mcp-test FILTER=test_engine
make uc-mcp-coverage
make uc-mcp-validate DEF=uc-mcp-server/definitions/slack.yaml
```

## Per-Feature Checklist

- [ ] Failing test written and confirmed RED
- [ ] Minimum implementation passes the test (GREEN)
- [ ] Full test suite passes after refactor
- [ ] Type annotations on public functions
- [ ] Docstring on public functions
- [ ] If new YAML schema fields: `_schema.yaml` updated
- [ ] If new definition: fixture added to `tests/fixtures/`
- [ ] If new definition: validation test added to `test_schema.py`
- [ ] If new runtime behavior: engine/connection test added

## Anti-Patterns

### Writing implementation before the test
Do not write `engine.py` code and then add tests after. The test MUST exist and fail BEFORE the implementation.

### Making tests pass by weakening assertions
If a test is hard to pass, fix the implementation — not the test. The test represents the desired behavior.

### Skipping the full suite after refactoring
Always run `uv run pytest -v` after any refactor. A passing single test does not guarantee no regressions.

### Over-engineering in the GREEN phase
The GREEN phase is about MINIMUM code. Add abstractions, error handling, and optimizations only in the REFACTOR phase, and only if tests justify them.

### Modifying multiple layers at once
Change one module at a time. If you need to change `schema.py` and `engine.py`, do two TDD cycles — one for each.
