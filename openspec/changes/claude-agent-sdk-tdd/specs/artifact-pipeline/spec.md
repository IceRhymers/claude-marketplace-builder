## ADDED Requirements

### Requirement: Test coverage for artifact pipeline scripts
The system SHALL have shell script tests (via `bats` or inline bash assertions in CI) and/or Python tests for the `build-artifact.sh` behavior that are written before the script is authored.

## Test Requirements

The following test scenarios MUST be validated before `scripts/build-artifact.sh` and `.github/workflows/publish-artifact.yml` are written. Shell script tests use a temporary directory fixture; GitHub Actions tests use `act` locally or are validated via PR CI runs.

#### Scenario: build-artifact.sh creates versioned tarball with correct layout
- **WHEN** `./build-artifact.sh v1.2.3` is run in a directory containing `skills/getting-started/SKILL.md` and `.mcp.json`
- **THEN** `dist/v1.2.3.tar.gz` is created and extracting it yields `v1.2.3/skills/getting-started/SKILL.md` and `v1.2.3/.mcp.json` at the expected paths

#### Scenario: build-artifact.sh exits non-zero without version argument
- **WHEN** `./build-artifact.sh` is called without arguments
- **THEN** the script exits with a non-zero code and prints a usage message to stderr

#### Scenario: build-artifact.sh warns but succeeds with no SKILL.md files
- **WHEN** `./build-artifact.sh v1.0.0` is called in a directory with no `skills/` subdirectories
- **THEN** the script exits `0`, `dist/v1.0.0.tar.gz` is created containing only `.mcp.json`, and a warning is written to stderr

#### Scenario: latest.json written with correct schema after build
- **WHEN** `./build-artifact.sh v1.2.3` completes successfully
- **THEN** `dist/latest.json` exists and contains `{"version": "v1.2.3", "path": "artifacts/v1.2.3", "published_at": "<iso8601>"}` with all three keys present

#### Scenario: GitHub Actions publish-artifact.yml runs test job before publish job
- **WHEN** a commit is pushed to `main` and the workflow runs
- **THEN** the workflow `test` job completes before the `publish` job starts, and if `test` fails the `publish` job is skipped (validated via `needs: test` in the workflow YAML)

#### Scenario: GitHub Actions workflow fails clearly when secrets missing
- **WHEN** `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, or `VOLUME_PATH` secrets are not configured in the repository
- **THEN** the workflow step that uses those secrets fails with an explicit error message and no partial artifact is uploaded

#### Scenario: Manual workflow_dispatch with explicit version uses provided version string
- **WHEN** the workflow is triggered manually with `version: v2.0.0-rc1` input
- **THEN** the artifact is named `v2.0.0-rc1.tar.gz` and `latest.json` contains `"version": "v2.0.0-rc1"`
