# CI Patterns

Makefile targets, PEX build configuration, and GitHub Actions release workflow for uc-mcp-proxy.

## Makefile Targets

Add to the project root `Makefile`:

```makefile
## Run uc-mcp-proxy unit tests
test-proxy:
	cd uc-mcp-proxy && python -m pytest tests/ -v

## Run proxy tests with coverage report
test-proxy-coverage:
	cd uc-mcp-proxy && python -m pytest tests/ --cov=uc_mcp_proxy --cov-report=term-missing --cov-fail-under=80

## Run only proxy unit tests (fast feedback)
test-proxy-unit:
	cd uc-mcp-proxy && python -m pytest tests/ -m unit -v

## Run only proxy integration tests
test-proxy-integration:
	cd uc-mcp-proxy && python -m pytest tests/ -m integration -v

## Build uc-mcp-proxy PEX executable
build-proxy:
	cd uc-mcp-proxy && bash build/build.sh
```

Add to `.PHONY`:
```makefile
.PHONY: test-proxy test-proxy-coverage test-proxy-unit test-proxy-integration build-proxy
```

## PEX Build Script

Place at `uc-mcp-proxy/build/build.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_DIR/build/output"

mkdir -p "$OUTPUT_DIR"

# Extract version from pyproject.toml
VERSION=$(grep '^version' "$PROJECT_DIR/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')
PEX_OUTPUT="$OUTPUT_DIR/uc-mcp-proxy.pex"

echo "Building uc-mcp-proxy v${VERSION}..."

# Generate pinned requirements from pyproject.toml
REQUIREMENTS_TMP=$(mktemp)
trap "rm -f $REQUIREMENTS_TMP" EXIT

uv pip compile "$PROJECT_DIR/pyproject.toml" --quiet 2>/dev/null > "$REQUIREMENTS_TMP"

# Parse optional flags
SCIE_FLAG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --scie)
            SCIE_FLAG="--scie eager"
            PEX_OUTPUT="$OUTPUT_DIR/uc-mcp-proxy"  # No .pex extension for SCIE
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Build PEX
uv run pex \
    -D "$PROJECT_DIR/src" \
    -r "$REQUIREMENTS_TMP" \
    -e uc_mcp_proxy.__main__:main \
    -o "$PEX_OUTPUT" \
    $SCIE_FLAG

echo "Built: $PEX_OUTPUT"

# Verify it runs
"$PEX_OUTPUT" --help > /dev/null 2>&1 && echo "Verification: OK" || echo "Verification: FAILED"
```

Make executable:
```bash
chmod +x uc-mcp-proxy/build/build.sh
```

## GitHub Actions Release Workflow

Place at `.github/workflows/release-proxy.yml`:

```yaml
name: Release uc-mcp-proxy

on:
  push:
    tags:
      - 'proxy-v*'  # Trigger on tags like proxy-v0.1.0

permissions:
  contents: write  # Needed for creating releases

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        working-directory: uc-mcp-proxy
        run: uv sync --dev

      - name: Run tests
        working-directory: uc-mcp-proxy
        run: uv run pytest tests/ -v --cov=uc_mcp_proxy --cov-fail-under=80

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python 3.11
        run: uv python install 3.11

      - name: Install build dependencies
        working-directory: uc-mcp-proxy
        run: uv sync --dev

      - name: Build PEX
        working-directory: uc-mcp-proxy
        run: bash build/build.sh

      - name: Upload PEX artifact
        uses: actions/upload-artifact@v4
        with:
          name: uc-mcp-proxy-pex
          path: uc-mcp-proxy/build/output/uc-mcp-proxy.pex

  release:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download PEX artifact
        uses: actions/download-artifact@v4
        with:
          name: uc-mcp-proxy-pex
          path: ./artifacts

      - name: Extract version from tag
        id: version
        run: echo "VERSION=${GITHUB_REF_NAME#proxy-v}" >> "$GITHUB_OUTPUT"

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          name: uc-mcp-proxy v${{ steps.version.outputs.VERSION }}
          body: |
            ## uc-mcp-proxy v${{ steps.version.outputs.VERSION }}

            MCP stdio-to-Streamable-HTTP proxy with Databricks OAuth.

            ### Installation

            ```bash
            curl -sL "${{ github.server_url }}/${{ github.repository }}/releases/download/${{ github.ref_name }}/uc-mcp-proxy.pex" \
              -o "${HOME}/.local/bin/uc-mcp-proxy.pex"
            chmod +x "${HOME}/.local/bin/uc-mcp-proxy.pex"
            ```

            ### Usage

            ```bash
            uc-mcp-proxy.pex --profile DEFAULT --url https://your-app.cloud.databricks.com/mcp
            ```
          files: |
            artifacts/uc-mcp-proxy.pex
          fail_on_unmatched_files: true
```

## Tagging a Release

```bash
# After tests pass and you're ready to release:
git tag proxy-v0.1.0
git push origin proxy-v0.1.0

# This triggers the workflow: test → build PEX → create GitHub Release
```

## Install Script Integration

The marketplace `install.sh` should download the proxy PEX during plugin installation:

```bash
# In scripts/install.sh (add after plugin installation):

PROXY_VERSION="0.1.0"
PROXY_URL="${REPO_URL}/releases/download/proxy-v${PROXY_VERSION}/uc-mcp-proxy.pex"
PROXY_DEST="${HOME}/.local/bin/uc-mcp-proxy.pex"

if [ ! -f "$PROXY_DEST" ] || [ "$FORCE_UPDATE" = "true" ]; then
    echo "Downloading uc-mcp-proxy v${PROXY_VERSION}..."
    mkdir -p "$(dirname "$PROXY_DEST")"
    curl -sL "$PROXY_URL" -o "$PROXY_DEST"
    chmod +x "$PROXY_DEST"
    echo "Installed: $PROXY_DEST"
else
    echo "uc-mcp-proxy already installed at $PROXY_DEST"
fi
```

## Local Build & Test Workflow

```bash
# Development cycle:
cd uc-mcp-proxy

# 1. Run tests (fast feedback)
python -m pytest tests/ -m unit -v

# 2. Run full suite with coverage
python -m pytest tests/ --cov=uc_mcp_proxy --cov-report=term-missing

# 3. Build PEX locally
bash build/build.sh

# 4. Test the PEX
build/output/uc-mcp-proxy.pex --help

# 5. Manual integration test (requires Databricks profile)
build/output/uc-mcp-proxy.pex \
  --profile DEFAULT \
  --url https://your-mcp-app.cloud.databricks.com/mcp
```
