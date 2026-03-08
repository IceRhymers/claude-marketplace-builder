## MODIFIED Requirements

### Capability: `agent-pool` — history hydration on cache miss

#### Requirement: Inject conversation history into freshly spawned agents
The system SHALL hydrate the `_history` list of a newly spawned `ClaudeAgent` with all prior messages for that conversation, loaded from the `messages` table in Lakebase, before the agent is returned from `AgentPool.get_or_create`. Hydration SHALL only occur on a cache miss (new agent) and SHALL be skipped on a cache hit (existing agent already has in-process history).

#### Scenario: Fresh agent receives full conversation history
- **WHEN** `AgentPool.get_or_create` is called for a `conversation_id` that is NOT in the pool (cache miss)
- **AND** the `messages` table contains prior rows for that `conversation_id` ordered by `created_at` ascending
- **THEN** the newly spawned agent's `_history` is populated as `[{"role": m.role, "content": m.content}, ...]` for each message row, in ascending `created_at` order, before the agent is returned

#### Scenario: Existing agent is not re-hydrated
- **WHEN** `AgentPool.get_or_create` is called for a `conversation_id` that IS already in the pool (cache hit)
- **THEN** the existing agent is returned immediately; no database query is issued for message history; the agent's `_history` is unchanged

#### Scenario: Cache miss on conversation with no prior messages
- **WHEN** `AgentPool.get_or_create` is called for a brand-new `conversation_id` (cache miss)
- **AND** no `messages` rows exist for that `conversation_id`
- **THEN** the agent is returned with an empty `_history` (same behavior as before this change)

#### Scenario: History hydration occurs before first `stream()` call
- **WHEN** `get_or_create` returns the agent
- **THEN** `agent._history` is already populated; the caller does not need to perform any additional setup before calling `agent.stream(message)`

## Test Requirements

Tests MUST be written in `tests/unit/test_agent_pool.py` BEFORE hydration is implemented in `core/agent_pool.py` (RED phase). The `get_or_create` call signature must accept a `db` parameter (SQLAlchemy `Session`) so hydration can query the `messages` table.

Required test scenarios (RED-before-GREEN):
- Cache miss on conversation with no DB messages → spawned agent has empty `_history`; DB queried once for messages
- Cache miss on conversation with 3 prior messages → spawned agent's `_history` has 3 entries in correct role/content order
- Cache hit → `_history` untouched; DB NOT queried for messages (assert `db.query` not called or mock shows zero calls on pool hit)
- History injected in ascending `created_at` order (not insertion order)
- Messages with `role="user"` and `role="assistant"` both mapped correctly to `{"role": ..., "content": ...}` dicts
- DB query failure during hydration → `RuntimeError` propagated (agent not stored in pool)

Fixture additions required (in `tests/conftest.py`):
- `populated_messages_db`: a `db_session` fixture variant pre-populated with a `Conversation` row and 4 `Message` rows (alternating user/assistant) for a known `conversation_id`
