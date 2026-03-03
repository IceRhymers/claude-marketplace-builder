# Test Infrastructure

Complete pytest configuration and shared fixtures for uc-mcp-proxy TDD.

## pyproject.toml Configuration

The proxy's `pyproject.toml` at `uc-mcp-proxy/pyproject.toml`:

```toml
[project]
name = "uc-mcp-proxy"
version = "0.1.0"
description = "MCP stdio-to-Streamable-HTTP proxy with Databricks OAuth"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.8",
    "databricks-sdk>=0.30.0",
    "httpx",
    "anyio",
]

[project.scripts]
uc-mcp-proxy = "uc_mcp_proxy.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/uc_mcp_proxy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Pure unit tests with no external dependencies",
    "integration: Tests that exercise the full proxy flow with mocked transports",
]
addopts = "-v --tb=short --strict-markers"
pythonpath = ["src"]

[tool.coverage.run]
source = ["uc_mcp_proxy"]
branch = true
omit = ["tests/*"]

[tool.coverage.report]
show_missing = true
fail_under = 80
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.",
    "if TYPE_CHECKING:",
]
```

## Dev Dependencies

Install via uv for development:

```bash
cd uc-mcp-proxy
uv sync --dev
```

Or add a `[project.optional-dependencies]` section:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-randomly>=3.15",
    "anyio[trio]>=4.0",       # anyio test backend
    "pex>=2.16",              # PEX builder
]
```

## conftest.py Template

Place at `uc-mcp-proxy/tests/conftest.py`:

```python
"""Shared fixtures for uc-mcp-proxy tests."""

from __future__ import annotations

import pytest
import httpx
import anyio
from contextlib import asynccontextmanager
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Databricks SDK fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_workspace_client():
    """Mock WorkspaceClient with OAuth token access.

    Simulates the SDK's authenticate() method which returns
    fresh auth headers on each call.
    """
    client = MagicMock()
    client.config.host = "https://test-workspace.cloud.databricks.com"
    client.config.authenticate.return_value = {
        "Authorization": "Bearer test-oauth-token"
    }
    return client


# ---------------------------------------------------------------------------
# Stream fixtures (real anyio memory streams, not mocks)
# ---------------------------------------------------------------------------

@pytest.fixture
def memory_stream_pair():
    """Factory: create a (send, recv) memory object stream pair.

    Usage:
        send, recv = memory_stream_pair(buffer=16)
    """
    def _make(buffer: int = 16):
        return anyio.create_memory_object_stream(buffer)
    return _make


@pytest.fixture
def stdio_streams(memory_stream_pair):
    """Simulated stdio transport streams.

    Returns (test_send, proxy_read, proxy_write, test_recv):
    - test_send: test writes here to simulate Claude Code input
    - proxy_read: proxy reads from here (stdio read side)
    - proxy_write: proxy writes here (stdio write side)
    - test_recv: test reads here to verify proxy output to Claude Code
    """
    test_send, proxy_read = memory_stream_pair()
    proxy_write, test_recv = memory_stream_pair()
    return test_send, proxy_read, proxy_write, test_recv


@pytest.fixture
def http_streams(memory_stream_pair):
    """Simulated HTTP transport streams.

    Returns (test_send, proxy_read, proxy_write, test_recv):
    - test_send: test writes here to simulate remote server responses
    - proxy_read: proxy reads from here (HTTP read side)
    - proxy_write: proxy writes here (HTTP write side)
    - test_recv: test reads here to verify proxy sent to remote server
    """
    test_send, proxy_read = memory_stream_pair()
    proxy_write, test_recv = memory_stream_pair()
    return test_send, proxy_read, proxy_write, test_recv


# ---------------------------------------------------------------------------
# Transport mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_stdio_server(stdio_streams):
    """Async context manager replacing mcp.server.stdio.stdio_server.

    Yields (read_stream, write_stream) from the proxy's perspective.
    """
    _, proxy_read, proxy_write, _ = stdio_streams

    @asynccontextmanager
    async def _mock():
        yield (proxy_read, proxy_write)

    return _mock


@pytest.fixture
def mock_http_client(http_streams):
    """Async context manager replacing mcp.client.streamable_http.streamablehttp_client.

    Yields (read_stream, write_stream, get_session_id) from the proxy's perspective.
    Captures the http_client kwarg for auth verification.
    """
    _, proxy_read, proxy_write, _ = http_streams
    captured = {}

    @asynccontextmanager
    async def _mock(url, *, http_client=None, terminate_on_close=True):
        captured["url"] = url
        captured["http_client"] = http_client
        captured["terminate_on_close"] = terminate_on_close
        yield (proxy_read, proxy_write, lambda: "mock-session-id")

    _mock.captured = captured
    return _mock


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def databricks_auth(mock_workspace_client):
    """Pre-configured DatabricksAuth instance."""
    from uc_mcp_proxy import DatabricksAuth
    return DatabricksAuth(mock_workspace_client)


# ---------------------------------------------------------------------------
# Sample message fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_jsonrpc_request():
    """A sample JSON-RPC request dict (tools/list)."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }


@pytest.fixture
def sample_jsonrpc_response():
    """A sample JSON-RPC response dict (tools/list result)."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {
                    "name": "chat_postmessage",
                    "description": "Sends a message to a Slack channel",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["channel"],
                    },
                }
            ]
        },
    }
```

## Directory Init Files

Create `__init__.py` files for test discovery:

```bash
touch uc-mcp-proxy/tests/__init__.py
touch uc-mcp-proxy/tests/unit/__init__.py
touch uc-mcp-proxy/tests/integration/__init__.py
```

## Running Tests

From the `uc-mcp-proxy/` directory:

```bash
# Run all tests
python -m pytest tests/ -v

# Run only unit tests (fast feedback)
python -m pytest tests/ -m unit -v

# Run only integration tests
python -m pytest tests/ -m integration -v

# Run tests for a specific module
python -m pytest tests/unit/test_auth.py -v

# Run with coverage
python -m pytest tests/ --cov=uc_mcp_proxy --cov-report=term-missing

# Run with coverage threshold (fails if under 80%)
python -m pytest tests/ --cov=uc_mcp_proxy --cov-fail-under=80
```

Or use the Makefile from the repo root:

```bash
make test-proxy
make test-proxy-coverage
```
