## ADDED Requirements

### Requirement: Agent pool keyed by conversation_id
The system SHALL maintain an in-memory `AgentPool` that maps `conversation_id` strings to initialized `ClaudeAgent` instances, so that subsequent turns in the same conversation reuse the same agent with its accumulated context.

#### Scenario: First message in a conversation spawns agent
- **WHEN** a streaming request arrives for a `conversation_id` that has no entry in the pool
- **THEN** the pool creates a new `ClaudeAgent` configured with the current skill set and the user's MCP connections, stores it keyed by `conversation_id`, and returns it for use

#### Scenario: Subsequent message reuses existing agent
- **WHEN** a streaming request arrives for a `conversation_id` that already has an entry in the pool
- **THEN** the pool returns the existing agent without re-initializing it, preserving in-memory conversation context

### Requirement: TTL-based agent eviction via APScheduler
The system SHALL evict agents from the pool after a configurable idle TTL (default 30 minutes), freeing resources for inactive conversations. Eviction SHALL be performed by a background APScheduler job on a fixed interval.

#### Scenario: Idle agent evicted after TTL
- **WHEN** an agent has not been accessed for longer than the configured TTL
- **THEN** the APScheduler job removes it from the pool on the next eviction sweep and closes its MCP connections gracefully

#### Scenario: Active agent not evicted
- **WHEN** an agent is accessed within the TTL window
- **THEN** its last-accessed timestamp is updated and it is not evicted on the next sweep

#### Scenario: Eviction interval configurable via env var
- **WHEN** the `AGENT_TTL_MINUTES` environment variable is set
- **THEN** the AgentPool uses that value (in minutes) as the idle TTL; the eviction sweep runs at half that interval

### Requirement: User-scoped MCP connections on agent spawn
The system SHALL configure each newly spawned agent with MCP server connections authenticated with the spawning user's `X-Forwarded-Access-Token`, so tool invocations (e.g., Slack) act as that user, not the app service principal.

#### Scenario: MCP connections use user token
- **WHEN** a new agent is spawned for `user_id=alice@example.com`
- **THEN** the agent's MCP transport headers include `Authorization: Bearer <alice's access token>` for every configured MCP server

#### Scenario: Agents for different users have isolated MCP sessions
- **WHEN** two users have active agents in the pool simultaneously
- **THEN** each agent's MCP connections carry only that user's token; no cross-user credential sharing occurs

### Requirement: Graceful shutdown of all agents
The system SHALL close all active agent MCP connections and clear the pool when the FastAPI application shuts down (lifespan `shutdown` event).

#### Scenario: Shutdown drains pool
- **WHEN** the FastAPI lifespan `shutdown` event fires
- **THEN** the AgentPool iterates all entries, calls `close()` on each agent's MCP connections, and clears the pool dictionary

### Requirement: Agent spawn failure is surfaced to caller
The system SHALL propagate agent initialization errors (e.g., MCP server unreachable) as a structured HTTP error rather than silently returning a broken agent.

#### Scenario: MCP connection fails during spawn
- **WHEN** spawning a new agent and an MCP server connection cannot be established
- **THEN** the pool does not store the failed agent, and the streaming endpoint returns `503 Service Unavailable` with `{"detail": "Agent initialization failed: <reason>"}`

## Test Requirements

Tests MUST be written in `tests/unit/test_agent_pool.py` BEFORE `core/agent_pool.py` is implemented (RED phase). All tests mock `ClaudeAgent` construction using `unittest.mock.patch`.

Required test scenarios:
- Empty pool: `get_or_create` on a new conversation_id constructs exactly one `ClaudeAgent`
- Same conversation_id: second `get_or_create` call returns the same agent (constructor called once)
- `evict_stale(ttl_minutes=0)` empties pool and calls `close()` on each agent
- Agent accessed within TTL is not evicted by `evict_stale`
- Two users with different conversation_ids produce two isolated agents in the pool
- `shutdown()` calls `close()` on all agents and empties `_pool`
- `ClaudeAgent` constructor raises → pool stays empty, exception propagates as 503
