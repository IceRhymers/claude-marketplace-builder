# Mock Patterns

Complete mocking templates for external dependencies in the uc-mcp-proxy.

## 1. Mocking Databricks WorkspaceClient

Always patch where the client is **imported**, not where it is **defined**.

### Token Injection (Primary Use Case)

```python
from unittest.mock import patch, MagicMock

@patch("uc_mcp_proxy.__main__.WorkspaceClient")
def test_creates_client_with_profile(MockClient):
    """Verify WorkspaceClient is constructed with the correct profile."""
    mock_client = MockClient.return_value
    mock_client.config.authenticate.return_value = {
        "Authorization": "Bearer test-token"
    }

    # Invoke proxy initialization
    from uc_mcp_proxy.__main__ import create_auth
    auth = create_auth(profile="MY_PROFILE")

    MockClient.assert_called_once_with(profile="MY_PROFILE")
```

### Simulating Token Refresh

```python
def test_each_request_gets_fresh_token(mock_workspace_client):
    """Verify authenticate() is called per-request, not cached."""
    mock_workspace_client.config.authenticate.side_effect = [
        {"Authorization": "Bearer token-1"},
        {"Authorization": "Bearer token-2"},
    ]

    from uc_mcp_proxy import DatabricksAuth
    auth = DatabricksAuth(mock_workspace_client)

    import httpx
    r1 = httpx.Request("POST", "https://example.com/mcp")
    next(auth.sync_auth_flow(r1))
    assert r1.headers["Authorization"] == "Bearer token-1"

    r2 = httpx.Request("POST", "https://example.com/mcp")
    next(auth.sync_auth_flow(r2))
    assert r2.headers["Authorization"] == "Bearer token-2"

    assert mock_workspace_client.config.authenticate.call_count == 2
```

### Expired Refresh Token

```python
from databricks.sdk.errors import PermissionDenied

def test_handles_expired_refresh_token(mock_workspace_client):
    """When refresh token is expired, SDK raises an error."""
    mock_workspace_client.config.authenticate.side_effect = PermissionDenied(
        "Token expired. Run: databricks auth login --profile DEFAULT"
    )

    from uc_mcp_proxy import DatabricksAuth
    auth = DatabricksAuth(mock_workspace_client)

    import httpx
    request = httpx.Request("POST", "https://example.com/mcp")
    flow = auth.sync_auth_flow(request)

    with pytest.raises(PermissionDenied):
        next(flow)
```

## 2. Mocking httpx.Auth Flow

The `httpx.Auth` subclass uses a generator protocol. Test it by stepping the generator.

### Sync Auth Flow

```python
import httpx

def test_sync_auth_flow(mock_workspace_client):
    """Test the sync generator protocol."""
    from uc_mcp_proxy import DatabricksAuth
    auth = DatabricksAuth(mock_workspace_client)

    request = httpx.Request("POST", "https://example.com/mcp")
    flow = auth.sync_auth_flow(request)

    # Step 1: get the modified request
    authed_request = next(flow)
    assert "Authorization" in authed_request.headers

    # Step 2: verify flow completes (no retry/challenge)
    with pytest.raises(StopIteration):
        flow.send(httpx.Response(200))
```

### Async Auth Flow

```python
import httpx
import pytest

@pytest.mark.anyio
async def test_async_auth_flow(mock_workspace_client):
    """Test the async generator protocol."""
    from uc_mcp_proxy import DatabricksAuth
    auth = DatabricksAuth(mock_workspace_client)

    request = httpx.Request("POST", "https://example.com/mcp")
    flow = auth.async_auth_flow(request)

    authed_request = await flow.__anext__()
    assert authed_request.headers["Authorization"] == "Bearer test-oauth-token"
```

## 3. Mocking MCP Transports

Both `stdio_server` and `streamablehttp_client` are async context managers that yield stream pairs. Mock them with `anyio.create_memory_object_stream`.

### stdio_server Mock

```python
from contextlib import asynccontextmanager
from unittest.mock import patch
import anyio

@asynccontextmanager
async def fake_stdio_server():
    """Replacement for mcp.server.stdio.stdio_server."""
    send_in, recv_in = anyio.create_memory_object_stream(16)
    send_out, recv_out = anyio.create_memory_object_stream(16)
    # Yields (read_stream, write_stream) from the server's perspective
    yield (recv_in, send_out)

# Usage in tests:
@patch("uc_mcp_proxy.__main__.stdio_server", side_effect=fake_stdio_server)
async def test_something(mock_stdio):
    ...
```

### streamablehttp_client Mock

```python
@asynccontextmanager
async def fake_http_client(url, *, http_client=None, terminate_on_close=True):
    """Replacement for mcp.client.streamable_http.streamablehttp_client."""
    send_in, recv_in = anyio.create_memory_object_stream(16)
    send_out, recv_out = anyio.create_memory_object_stream(16)
    # Yields (read_stream, write_stream, get_session_id)
    yield (recv_in, send_out, lambda: "mock-session-id")

# Usage:
@patch("uc_mcp_proxy.__main__.streamablehttp_client", side_effect=fake_http_client)
async def test_something(mock_http):
    ...
```

### Verifying HTTP Client Auth Configuration

```python
@patch("uc_mcp_proxy.__main__.streamablehttp_client")
@patch("uc_mcp_proxy.__main__.stdio_server")
@pytest.mark.anyio
async def test_http_client_receives_auth(mock_stdio, mock_http):
    """Verify the httpx.AsyncClient passed to streamablehttp_client has our auth."""
    from contextlib import asynccontextmanager

    captured_kwargs = {}

    @asynccontextmanager
    async def capture_http(url, **kwargs):
        captured_kwargs.update(kwargs)
        send, recv = anyio.create_memory_object_stream(16)
        yield (recv, send, lambda: None)

    mock_http.side_effect = capture_http
    mock_stdio.side_effect = fake_stdio_server

    # Run proxy briefly, then cancel
    # ... (see integration test patterns)

    assert "http_client" in captured_kwargs
    assert captured_kwargs["http_client"].auth is not None
```

## 4. Testing Stream Bridging with Real Streams

The bridge logic (`copy_stream`) should be tested with **real anyio memory streams**, not mocks. This validates actual async message passing.

### Basic Copy Test

```python
import anyio
import pytest

@pytest.mark.anyio
async def test_copy_stream_forwards_messages():
    """Messages written to source appear on dest."""
    from uc_mcp_proxy.__main__ import copy_stream

    source_send, source_recv = anyio.create_memory_object_stream(16)
    dest_send, dest_recv = anyio.create_memory_object_stream(16)

    async with anyio.create_task_group() as tg:
        tg.start_soon(copy_stream, source_recv, dest_send)

        await source_send.send("message-1")
        await source_send.send("message-2")
        source_send.close()  # Signal end of stream

    # Read what arrived at dest
    results = []
    async with dest_recv:
        async for msg in dest_recv:
            results.append(msg)

    assert results == ["message-1", "message-2"]
```

### Graceful Close

```python
@pytest.mark.anyio
async def test_copy_stream_handles_source_close():
    """When source closes, copy_stream exits without error."""
    from uc_mcp_proxy.__main__ import copy_stream

    source_send, source_recv = anyio.create_memory_object_stream(4)
    dest_send, dest_recv = anyio.create_memory_object_stream(4)

    # Close source immediately
    source_send.close()

    # Should complete without raising
    await copy_stream(source_recv, dest_send)
```

### Bidirectional Bridge

```python
@pytest.mark.anyio
async def test_bridge_bidirectional(stdio_streams, http_streams):
    """Full roundtrip: message goes stdio->http, response comes http->stdio."""
    from uc_mcp_proxy.__main__ import bridge

    stdio_send, stdio_recv, stdio_write, stdio_read = stdio_streams
    http_send, http_recv, http_write, http_read = http_streams

    async with anyio.create_task_group() as tg:
        tg.start_soon(bridge, stdio_recv, stdio_write, http_recv, http_write)

        # Claude -> Remote
        await stdio_send.send("request")
        forwarded = await http_read.receive()
        assert forwarded == "request"

        # Remote -> Claude
        await http_send.send("response")
        returned = await stdio_read.receive()
        assert returned == "response"

        # Shutdown
        stdio_send.close()
        http_send.close()
```

## 5. Mocking CLI Arguments

```python
from unittest.mock import patch
import sys

def test_requires_url_argument():
    """Proxy fails without --url."""
    with patch.object(sys, "argv", ["uc-mcp-proxy"]):
        with pytest.raises(SystemExit) as exc_info:
            from uc_mcp_proxy.__main__ import main
            main()
        assert exc_info.value.code == 2  # argparse error

def test_default_profile_is_none():
    """Without --profile, profile defaults to None (SDK default chain)."""
    with patch.object(sys, "argv", ["uc-mcp-proxy", "--url", "https://example.com/mcp"]):
        with patch("uc_mcp_proxy.__main__.asyncio.run") as mock_run:
            from uc_mcp_proxy.__main__ import main
            main()
            args = mock_run.call_args
            # Verify profile=None was passed to run()
```

## Anti-Patterns

**Do NOT mock `anyio.create_memory_object_stream`** — use real streams:

```python
# BAD — mocking the stream primitives
@patch("anyio.create_memory_object_stream")
def test_bridge(mock_stream):
    ...

# GOOD — use real streams, they're in-memory and fast
@pytest.mark.anyio
async def test_bridge():
    send, recv = anyio.create_memory_object_stream(16)
    ...
```

**Do NOT mock `copy_stream` when testing `bridge`:**

```python
# BAD — mocking internal function
@patch("uc_mcp_proxy.__main__.copy_stream")
async def test_bridge(mock_copy):
    ...

# GOOD — test bridge end-to-end with real streams
async def test_bridge(stdio_streams, http_streams):
    ...
```

**Do NOT use `asyncio.sleep()` in tests** — use anyio event primitives:

```python
# BAD
await asyncio.sleep(0.1)  # race condition

# GOOD
await anyio.sleep(0)  # yield control, deterministic
```
