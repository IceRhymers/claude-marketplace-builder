## ADDED Requirements

### Requirement: Test coverage for AgentPool
The system SHALL have `tests/unit/test_agent_pool.py` covering all AgentPool behaviors before `agent_pool.py` is implemented.

## Test Requirements

The following test scenarios MUST be implemented as pytest tests in `tests/unit/test_agent_pool.py` before `core/agent_pool.py` is written. All tests use `mock_skills_config` and a mocked `ClaudeAgent` constructor.

#### Scenario: First message spawns a new agent
- **WHEN** `await pool.get_or_create("conv-1", "alice@example.com", "token-a")` is called on an empty pool
- **THEN** the test asserts the returned object is the mock `ClaudeAgent` and the pool's internal dict contains an entry for `"conv-1"`

#### Scenario: Second call for same conversation_id reuses existing agent
- **WHEN** `get_or_create` is called twice for the same `conversation_id`
- **THEN** the mock `ClaudeAgent` constructor is called exactly once (verified via `assert ClaudeAgent.call_count == 1`)

#### Scenario: TTL eviction removes stale entries
- **WHEN** `evict_stale(ttl_minutes=0)` is called (zero TTL so all entries are stale)
- **THEN** the pool's internal dict is empty after the call and the mock agent's `close()` method was called

#### Scenario: Active agent not evicted within TTL
- **WHEN** an agent was accessed within the TTL window and `evict_stale(ttl_minutes=30)` is called
- **THEN** the pool's internal dict still contains the entry

#### Scenario: Cross-user isolation — agents keyed by conversation_id
- **WHEN** `get_or_create("conv-1", "alice@example.com", "token-a")` and `get_or_create("conv-2", "bob@example.com", "token-b")` are both called
- **THEN** the pool contains two separate entries and each agent was constructed with the correct user token

#### Scenario: Shutdown drains pool and closes all agents
- **WHEN** `await pool.shutdown()` is called with two active agents
- **THEN** both agents' `close()` methods were called and `pool._pool` is empty

#### Scenario: MCP spawn failure does not persist broken agent
- **WHEN** the `ClaudeAgent` constructor raises `ConnectionError("MCP unreachable")`
- **THEN** `get_or_create` raises a `503`-equivalent exception and the pool dict contains no entry for that conversation
