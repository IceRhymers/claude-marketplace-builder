## ADDED Requirements

### Requirement: Test coverage for user identity dependency
The system SHALL have `tests/unit/test_auth.py` covering all `get_current_user` scenarios before `core/auth.py` is implemented.

## Test Requirements

The following test scenarios MUST be implemented in `tests/unit/test_auth.py` before `core/auth.py` is written. All tests patch `core.auth.WorkspaceClient` with a mock.

#### Scenario: Valid token resolves user_id and access_token
- **WHEN** `get_current_user` is called with `x_forwarded_access_token="valid-token"` and the mock `WorkspaceClient.current_user.me()` returns `MagicMock(user_name="alice@example.com")`
- **THEN** the function returns a `CurrentUser` with `user_id="alice@example.com"` and `access_token="valid-token"`

#### Scenario: Missing token raises HTTPException 401
- **WHEN** `get_current_user` is called with `x_forwarded_access_token=None` or an empty string
- **THEN** an `HTTPException` with `status_code=401` and `detail` containing `"Missing X-Forwarded-Access-Token"` is raised

#### Scenario: Invalid token raises HTTPException 401
- **WHEN** `get_current_user` is called with `x_forwarded_access_token="bad-token"` and the mock `WorkspaceClient.current_user.me()` raises `PermissionDenied`
- **THEN** an `HTTPException` with `status_code=401` and `detail` containing `"Invalid token"` is raised

#### Scenario: Dependency injection wires correctly in FastAPI route
- **WHEN** a test endpoint decorated with `Depends(get_current_user)` is called via `httpx.AsyncClient` with the `X-Forwarded-Access-Token` header set to `"test-token"`
- **THEN** the route handler receives a `CurrentUser` object with the resolved `user_id` without calling the SDK directly in the handler body

#### Scenario: Dependency failure short-circuits before handler executes
- **WHEN** the `X-Forwarded-Access-Token` header is missing and the endpoint uses `Depends(get_current_user)`
- **THEN** the HTTP response is `401` and the route handler body is never executed (verified by asserting a side-effect mock inside the handler is not called)

#### Scenario: access_token forwarded to AgentPool
- **WHEN** the streaming endpoint resolves `CurrentUser(user_id="alice@example.com", access_token="token-a")` and calls `AgentPool.get_or_create`
- **THEN** the test asserts `mock_agent_pool.get_or_create` was called with `access_token="token-a"` as the third positional argument
