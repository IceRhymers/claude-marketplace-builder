## ADDED Requirements

### Requirement: Resolve user identity from X-Forwarded-Access-Token
The system SHALL resolve the calling user's identity by exchanging the `X-Forwarded-Access-Token` header value with the Databricks SDK `WorkspaceClient.current_user.me()` call, returning the authenticated user's `user_name` (email) as the canonical `user_id` for all downstream operations.

#### Scenario: Valid token resolves user
- **WHEN** a request arrives with a valid `X-Forwarded-Access-Token` header
- **THEN** the system calls `current_user.me()` and extracts `user_name` as the `user_id`

#### Scenario: Missing token rejected
- **WHEN** a request arrives without `X-Forwarded-Access-Token`
- **THEN** all protected endpoints return `401 Unauthorized` with `{"detail": "Missing X-Forwarded-Access-Token header"}`

#### Scenario: Invalid or expired token rejected
- **WHEN** a request arrives with a malformed or expired `X-Forwarded-Access-Token`
- **THEN** the Databricks SDK raises an exception, and the system returns `401 Unauthorized` with `{"detail": "Invalid token"}`

### Requirement: User identity provided as FastAPI dependency
The system SHALL expose user resolution as a FastAPI `Depends`-injectable function `get_current_user(x_forwarded_access_token: str = Header(...))` returning a `CurrentUser` dataclass with fields `user_id: str` and `access_token: str`, so all route handlers can declare it once without duplicating resolution logic.

#### Scenario: Dependency injected into route
- **WHEN** a route handler declares `current_user: CurrentUser = Depends(get_current_user)`
- **THEN** FastAPI resolves the user identity before invoking the handler, and the handler receives a populated `CurrentUser` without calling the SDK directly

#### Scenario: Dependency failure short-circuits request
- **WHEN** the `get_current_user` dependency fails (missing or invalid token)
- **THEN** FastAPI returns the error response before the route handler body executes

### Requirement: Access token forwarded to MCP layer
The system SHALL make the raw `access_token` from `CurrentUser` available to the AgentPool spawn function so it can be injected into MCP connection headers for user-scoped tool calls.

#### Scenario: Token passed to agent spawn
- **WHEN** a streaming request triggers a new agent spawn
- **THEN** the `access_token` from `CurrentUser` is passed to `AgentPool.get_or_create(conversation_id, user_id, access_token)` and used in MCP transport configuration

## Test Requirements

Tests MUST be written in `tests/unit/test_auth.py` BEFORE `core/auth.py` is implemented (RED phase). All tests patch `core.auth.WorkspaceClient` with `unittest.mock.patch`.

Required test scenarios:
- Valid token → `CurrentUser(user_id="alice@example.com", access_token="valid-token")` returned
- `None` / empty `x_forwarded_access_token` → `HTTPException(status_code=401, detail=...Missing...)`
- `WorkspaceClient.current_user.me()` raises `PermissionDenied` → `HTTPException(status_code=401, detail=...Invalid token...)`
- Route with `Depends(get_current_user)` called via `httpx.AsyncClient` with header → handler receives populated `CurrentUser`
- Route with `Depends(get_current_user)` called without header → `401` response and handler body not executed
- Streaming endpoint: `mock_agent_pool.get_or_create` called with `access_token` matching the request header value
