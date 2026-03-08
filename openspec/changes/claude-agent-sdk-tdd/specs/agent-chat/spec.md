## ADDED Requirements

### Requirement: Test coverage for agent-chat endpoints
The system SHALL have a `tests/unit/test_router_conversations.py` and `tests/integration/test_stream.py` covering the scenarios defined in this capability's spec before any router code is written.

## Test Requirements

The following test scenarios MUST be implemented as pytest tests before the corresponding implementation tasks are started. Unit tests use `mock_workspace_client` and `mock_agent_pool` fixtures from `conftest.py`; integration tests use `httpx.AsyncClient` with `ASGITransport`.

#### Scenario: POST /api/conversations returns 201 with conversation_id
- **WHEN** `POST /api/conversations` is called with a valid mocked `X-Forwarded-Access-Token`
- **THEN** the test asserts `response.status_code == 201` and `"conversation_id"` and `"created_at"` are in `response.json()`

#### Scenario: POST /api/conversations returns 401 with missing token
- **WHEN** `POST /api/conversations` is called without the `X-Forwarded-Access-Token` header
- **THEN** the test asserts `response.status_code == 401`

#### Scenario: GET /api/conversations/id/stream emits text_delta and done events
- **WHEN** `GET /api/conversations/{id}/stream?message=Hello` is called with a valid token and the `mock_agent_pool` fixture
- **THEN** the test collects all SSE event lines and asserts at least one `{"type": "text_delta"}` event and one `{"type": "done"}` event are present

#### Scenario: GET /api/conversations/id/stream returns 404 for non-owned conversation
- **WHEN** `GET /api/conversations/{id}/stream` is called for a conversation owned by a different `user_id`
- **THEN** the test asserts `response.status_code == 404` before any SSE data is sent

#### Scenario: Stream persists user and assistant messages on completion
- **WHEN** a streaming turn completes (done event received)
- **THEN** the test queries the `messages` table and asserts two rows exist: one with `role="user"` and one with `role="assistant"` for the conversation

#### Scenario: DELETE /api/conversations/id returns 204 and evicts agent
- **WHEN** `DELETE /api/conversations/{id}` is called by the owning user
- **THEN** `response.status_code == 204` and `mock_agent_pool.evict.assert_called_once_with(id)` passes

#### Scenario: GET /api/conversations/id/messages returns 404 for non-owner
- **WHEN** a different user requests messages for a conversation they do not own
- **THEN** `response.status_code == 404`

#### Scenario: Tool call events included in SSE stream
- **WHEN** the mock agent yields `{"type": "tool_use", "tool": "slack", "input": {}}` then `{"type": "tool_result", "tool": "slack", "output": "ok"}` then `{"type": "done"}`
- **THEN** the integration test asserts all three event types appear in the collected SSE output in order
