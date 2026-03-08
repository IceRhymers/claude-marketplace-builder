## ADDED Requirements

### Requirement: Build artifact shell script
The system SHALL provide `claude-agent-app/scripts/build-artifact.sh` that collects all SKILL.md files from a configurable source directory and a `.mcp.json` config file, bundles them into a versioned tarball (e.g., `v1.2.3.tar.gz`), and writes the tarball to a local `dist/` directory.

#### Scenario: Successful artifact build
- **WHEN** `build-artifact.sh` is invoked with a valid version argument (e.g., `./build-artifact.sh v1.2.3`)
- **THEN** the script collects all `**/SKILL.md` files and `.mcp.json`, creates `dist/v1.2.3.tar.gz` containing them with their relative directory structure preserved, and exits `0`

#### Scenario: Missing version argument
- **WHEN** `build-artifact.sh` is invoked without a version argument
- **THEN** the script prints a usage message to stderr and exits with a non-zero code

#### Scenario: No SKILL.md files found
- **WHEN** the source directory contains no SKILL.md files
- **THEN** the script builds an artifact containing only `.mcp.json` (if present), logs a warning, and exits `0`

### Requirement: Upload artifact to Databricks Volume
The system SHALL provide logic (via `build-artifact.sh` or a companion script) to upload the generated tarball to `{VOLUME_PATH}/artifacts/<version>/` using the Databricks CLI (`databricks fs cp`), then write/overwrite `{VOLUME_PATH}/latest.json` with the new version and relative path.

#### Scenario: Artifact uploaded successfully
- **WHEN** upload is invoked with a valid `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, and `VOLUME_PATH`
- **THEN** the tarball is copied to `{VOLUME_PATH}/artifacts/<version>/`, `latest.json` is updated, and the script exits `0`

#### Scenario: Upload fails due to bad credentials
- **WHEN** `DATABRICKS_TOKEN` is invalid
- **THEN** the script propagates the Databricks CLI error and exits non-zero without updating `latest.json`

### Requirement: GitHub Actions workflow for artifact publish
The system SHALL include `.github/workflows/publish-artifact.yml` that triggers on pushes to `main` (or manual `workflow_dispatch`), builds the artifact with the script, and uploads it to the Databricks Volume using repository secrets.

#### Scenario: Workflow triggered on main push
- **WHEN** a commit is pushed to the `main` branch
- **THEN** the workflow checks out the repository, runs `build-artifact.sh` with a version derived from the git tag or `GITHUB_SHA` short hash, and uploads to the Volume

#### Scenario: Manual workflow dispatch with explicit version
- **WHEN** the workflow is manually triggered with `version` input provided
- **THEN** the script uses that exact version string for the artifact name and `latest.json` update

#### Scenario: Required secrets missing
- **WHEN** `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, or `VOLUME_PATH` secrets are not configured
- **THEN** the workflow step fails with a clear error message; no partial artifact is uploaded

### Requirement: Versioned artifact directory layout
The tarball SHALL unpack into a directory structure `<version>/` containing:
- `skills/<skill-name>/SKILL.md` for each skill
- `.mcp.json` at the top level of the versioned directory

#### Scenario: Unpacked artifact has expected layout
- **WHEN** the tarball for `v1.2.3` is extracted
- **THEN** the resulting directory contains `v1.2.3/skills/*/SKILL.md` and `v1.2.3/.mcp.json`

### Requirement: latest.json schema
The system SHALL write `latest.json` with the schema `{"version": "<semver-or-sha>", "path": "artifacts/<version>", "published_at": "<iso8601>"}` so the application can parse it reliably.

#### Scenario: latest.json content after publish
- **WHEN** version `v1.2.3` is published
- **THEN** `latest.json` contains `{"version": "v1.2.3", "path": "artifacts/v1.2.3", "published_at": "<current UTC timestamp>"}`

## Test Requirements

Shell script behavior MUST be validated by a test harness (`scripts/test-build-artifact.sh`) written BEFORE `build-artifact.sh` is authored (RED phase). GitHub Actions workflow structure is validated by reviewing YAML against the required `needs: test` constraint before the workflow file is created.

Required test scenarios:
- `./build-artifact.sh v1.2.3` with `skills/getting-started/SKILL.md` and `.mcp.json` present → `dist/v1.2.3.tar.gz` created; extracting yields `v1.2.3/skills/getting-started/SKILL.md` and `v1.2.3/.mcp.json`
- `./build-artifact.sh` (no version argument) → exit code non-zero, usage message on stderr
- `./build-artifact.sh v1.0.0` with no SKILL.md files → exit code `0`, tarball contains only `.mcp.json`, warning on stderr
- After successful `./build-artifact.sh v1.2.3` → `dist/latest.json` contains keys `version`, `path`, `published_at`
- GitHub Actions `publish-artifact.yml` YAML must have `needs: test` on the publish job (verified by grep on the YAML file)
- GitHub Actions `publish-artifact.yml` YAML must define a `workflow_dispatch` trigger with a `version` input (verified by grep)
- Manual dispatch with `version: v2.0.0-rc1` → artifact named `v2.0.0-rc1.tar.gz` and `latest.json` version field is `v2.0.0-rc1`
