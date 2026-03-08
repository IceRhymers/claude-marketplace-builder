## MODIFIED Requirements

### Capability: `agent-chat` — extend DELETE to clean up Volume path

#### Requirement: `DELETE /api/conversations/{id}` removes Volume path in addition to DB rows
The system SHALL delete the Databricks Volume path `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/` as part of the `DELETE /api/conversations/{conversation_id}` request, after evicting the agent from the pool with `purge=True`.

The deletion order SHALL be:
1. Evict the agent from `AgentPool` with `purge=True` (skips Volume sync — no point syncing files about to be deleted)
2. Delete the Volume path `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/` recursively via `WorkspaceClient.files.delete()`
3. Delete the `Conversation` row from Lakebase (FK cascade removes `Message` rows)
4. Return `204 No Content`

#### Scenario: DELETE conversation removes Volume path
- **WHEN** a user sends `DELETE /api/conversations/{id}` and owns the conversation
- **THEN** `AgentPool.evict(conversation_id, purge=True)` is called (skipping file sync)
- **AND** `WorkspaceClient.files.delete(volume_path, recursive=True)` is called for `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/`
- **AND** the conversation and all its messages are deleted from Lakebase
- **AND** the response is `204 No Content`

#### Scenario: Volume delete failure does not block conversation deletion
- **WHEN** `DELETE /api/conversations/{id}` is called
- **AND** `WorkspaceClient.files.delete()` raises an exception (e.g., path does not exist, network error)
- **THEN** the exception is caught and logged as a WARNING
- **AND** the Lakebase rows are still deleted
- **AND** the response is still `204 No Content`

#### Scenario: DELETE non-owned conversation returns 404 without cleanup
- **WHEN** a user sends `DELETE /api/conversations/{id}` for a conversation they do not own
- **THEN** `404 Not Found` is returned
- **AND** no eviction, no Volume delete, and no DB delete is performed

#### Scenario: DELETE conversation not in pool still cleans up Volume
- **WHEN** `DELETE /api/conversations/{id}` is called for a conversation whose agent has already been evicted from the pool
- **THEN** `AgentPool.evict(conversation_id, purge=True)` is a no-op (conversation not in pool)
- **AND** the Volume delete is still attempted
- **AND** the Lakebase rows are still deleted
- **AND** `204 No Content` is returned

#### Requirement: Graceful degradation when `AGENT_SESSIONS_VOLUME_PATH` not set
- **WHEN** `DELETE /api/conversations/{id}` is called
- **AND** `AGENT_SESSIONS_VOLUME_PATH` is not set
- **THEN** Volume delete is skipped with a WARNING log
- **AND** Lakebase rows are still deleted and `204 No Content` returned

## Test Requirements

Tests MUST be written in `tests/unit/test_router_conversations.py` BEFORE the `DELETE` endpoint is extended (RED phase). Use `mock_agent_pool` and `mock_workspace_client` fixtures from `conftest.py`.

Required test scenarios (RED-before-GREEN):
- `DELETE /api/conversations/{id}` owned conversation → `evict(purge=True)` called; `files.delete` called with correct Volume path; `204` returned; DB row gone
- `DELETE /api/conversations/{id}` with `files.delete` raising → WARNING logged; `204` still returned; DB row still gone
- `DELETE /api/conversations/{id}` non-owned → `404`; evict not called; `files.delete` not called; DB row unchanged
- `DELETE /api/conversations/{id}` conversation not in pool → `evict` is no-op; `files.delete` still called; `204` returned
- `DELETE /api/conversations/{id}` with `AGENT_SESSIONS_VOLUME_PATH` unset → no `files.delete` call; `204` returned; DB row gone
- `evict` called with `purge=True` (not `purge=False`) on conversation delete
