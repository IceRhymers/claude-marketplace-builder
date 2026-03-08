## ADDED Requirements

### Requirement: Create conversation
The system SHALL allow an authenticated user to create a new conversation, returning a `conversation_id` that identifies the session for all subsequent requests.

#### Scenario: Successful conversation creation
- **WHEN** a user sends `POST /api/conversations` with a valid `X-Forwarded-Access-Token` header
- **THEN** the system creates a conversation record owned by the resolved `user_id`, returns `201` with `{"conversation_id": "<uuid>", "created_at": "<iso8601>"}`, and persists the record to Lakebase

#### Scenario: Missing token on conversation creation
- **WHEN** a user sends `POST /api/conversations` without `X-Forwarded-Access-Token`
- **THEN** the system returns `401 Unauthorized` with `{"detail": "Missing X-Forwarded-Access-Token header"}`

### Requirement: Stream chat response via SSE
The system SHALL stream Claude agent responses as Server-Sent Events on `GET /api/conversations/{conversation_id}/stream` after the user supplies a message, so the UI can render tokens progressively.

#### Scenario: Successful streaming response
- **WHEN** a user sends `GET /api/conversations/{conversation_id}/stream?message=<text>` with a valid token and the conversation belongs to that user
- **THEN** the system retrieves or creates an agent from the AgentPool, sends the message, and streams SSE events with `data:` lines containing JSON objects of the form `{"type": "text_delta", "text": "..."}` until the response is complete, followed by a final `{"type": "done"}` event

#### Scenario: Tool call events included in stream
- **WHEN** the agent invokes an MCP tool during a response
- **THEN** the stream includes SSE events with `{"type": "tool_use", "tool": "<name>", "input": {...}}` before the result and `{"type": "tool_result", "tool": "<name>", "output": "..."}` after

#### Scenario: Conversation not found or not owned
- **WHEN** a user requests streaming for a `conversation_id` that does not exist or belongs to a different `user_id`
- **THEN** the system returns `404 Not Found` before opening the SSE stream

#### Scenario: Stream cancelled by client disconnect
- **WHEN** the client closes the SSE connection before the agent finishes responding
- **THEN** the system detects the disconnect and cancels the in-flight agent run without corrupting stored messages

### Requirement: Persist messages after stream completes
The system SHALL persist both the user message and the full assistant response to the `messages` table in Lakebase after each successful streaming turn.

#### Scenario: Messages stored after turn
- **WHEN** a streaming turn completes (agent sends `done` event)
- **THEN** a `user` role message and an `assistant` role message are written to the `messages` table with the correct `conversation_id`, `user_id`, `content`, and `created_at`

#### Scenario: Partial message on cancelled stream
- **WHEN** the stream is cancelled by client disconnect before completion
- **THEN** no messages are persisted for that turn (atomic: either full turn is stored or nothing)

### Requirement: List conversations
The system SHALL allow a user to retrieve a paginated list of their conversations via `GET /api/conversations`.

#### Scenario: Successful list
- **WHEN** a user sends `GET /api/conversations` with a valid token
- **THEN** the system returns `200` with a JSON array of conversations owned by that `user_id`, ordered by `updated_at` descending, with fields `conversation_id`, `title`, `created_at`, `updated_at`

#### Scenario: Empty list
- **WHEN** a user has no conversations
- **THEN** the system returns `200` with an empty array `[]`

### Requirement: Retrieve conversation messages
The system SHALL allow a user to retrieve the message history for a conversation via `GET /api/conversations/{conversation_id}/messages`.

#### Scenario: Successful message retrieval
- **WHEN** a user sends `GET /api/conversations/{conversation_id}/messages` with a valid token and the conversation belongs to them
- **THEN** the system returns `200` with an ordered array of message objects including `role`, `content`, and `created_at`

#### Scenario: Access denied to another user's conversation
- **WHEN** a user requests messages for a `conversation_id` owned by a different `user_id`
- **THEN** the system returns `404 Not Found`

### Requirement: Delete conversation
The system SHALL allow a user to delete one of their conversations and all associated messages via `DELETE /api/conversations/{conversation_id}`.

#### Scenario: Successful deletion
- **WHEN** a user sends `DELETE /api/conversations/{conversation_id}` and owns the conversation
- **THEN** the system deletes the conversation and all its messages from Lakebase, evicts the agent from the AgentPool if present, and returns `204 No Content`

#### Scenario: Delete non-owned conversation
- **WHEN** a user sends `DELETE /api/conversations/{conversation_id}` for a conversation they do not own
- **THEN** the system returns `404 Not Found` without modifying any data
