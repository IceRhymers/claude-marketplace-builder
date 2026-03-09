# Claude Agent SDK Setup

This app uses the Anthropic Python SDK to power the streaming chat agent.

## Installation

The SDK is included in `pyproject.toml`:

```
anthropic[bedrock]>=0.40
```

Install via:

```bash
uv sync
```

## Configuration

The agent is configured in `core/agent_pool.py` via the `build_agent()` function. It uses the `anthropic.Anthropic()` client which reads credentials from environment variables:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Or configure via Databricks AI Gateway by setting:

```
ANTHROPIC_API_KEY=<gateway-key>
ANTHROPIC_BASE_URL=https://<workspace>.azuredatabricks.net/serving-endpoints/<endpoint>
```

## Agent Lifecycle

Agents are managed by the `AgentPool` class in `core/agent_pool.py`:

1. **First request**: `AgentPool.get_or_create()` calls `build_agent()` with the current skills system prompt and MCP configuration, stores the agent keyed by `conversation_id`.
2. **Subsequent requests**: Returns the cached agent without re-initialization.
3. **TTL eviction**: APScheduler runs `evict_stale()` every `AGENT_TTL_MINUTES / 2` minutes.
4. **Shutdown**: `AgentPool.shutdown()` closes all agents on app shutdown.

## Streaming

The `core/agent_pool.py:SimpleAgent.stream()` method uses the Anthropic Messages API with streaming:

```python
with client.messages.stream(
    model="claude-sonnet-4-5",
    max_tokens=4096,
    system=system_prompt,
    messages=history,
) as stream:
    for text in stream.text_stream:
        yield {"type": "text_delta", "text": text}
yield {"type": "done"}
```

## Conversation History

Each agent maintains an in-memory `_history` list of `{"role": ..., "content": ...}` dicts. On TTL eviction, this history is lost (users will get a "cold start" next turn, loading history from the database if needed).
