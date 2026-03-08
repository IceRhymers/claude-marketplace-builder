## MODIFIED Requirements

### Capability: `agent-pool` — file sync to Volume on eviction

#### Requirement: Sync session sandbox to Databricks Volume before local cleanup
The system SHALL upload all files from the local session sandbox (`/tmp/claude-agent-sessions/{conversation_id}/`) to the Databricks Volume path `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/` when `AgentPool.evict()` is called without the `purge` flag. Sync SHALL complete before the local tmp directory is deleted.

#### Scenario: Non-empty session sandbox synced to Volume on eviction
- **WHEN** `AgentPool.evict(conversation_id)` is called (default `purge=False`)
- **AND** the local session sandbox contains one or more files
- **THEN** each file is uploaded to `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/{relative_path}` via `WorkspaceClient.files.upload()`
- **AND** the local tmp directory is deleted after upload completes

#### Scenario: Empty session sandbox skips Volume sync (no-op)
- **WHEN** `AgentPool.evict(conversation_id)` is called with `purge=False`
- **AND** the local session sandbox is empty (no files present)
- **THEN** no Volume upload calls are made
- **AND** the local tmp directory is still deleted

#### Scenario: Volume sync failure does not block eviction
- **WHEN** `AgentPool.evict(conversation_id)` is called with `purge=False`
- **AND** the `WorkspaceClient.files.upload()` call raises an exception
- **THEN** the exception is caught and logged as a WARNING
- **AND** the pool entry is still removed and the local tmp directory is still deleted
- **AND** no exception propagates to the caller

#### Requirement: `purge=True` skips Volume sync
The system SHALL accept a `purge: bool = False` keyword argument on `AgentPool.evict()`. When `purge=True`, the Volume sync step SHALL be skipped entirely and the pool entry and local tmp directory SHALL be cleaned up immediately.

#### Scenario: `evict(conversation_id, purge=True)` skips Volume sync
- **WHEN** `AgentPool.evict(conversation_id, purge=True)` is called
- **THEN** no `WorkspaceClient.files.upload()` calls are made
- **AND** the pool entry is removed and local tmp directory deleted as normal

#### Requirement: Volume path derived from `user_id` stored in `AgentEntry`
The Volume path for file sync SHALL be `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/` where `user_id` is read from the `AgentEntry.user_id` field (already stored at agent spawn time) and `AGENT_SESSIONS_VOLUME_PATH` is read from the `AGENT_SESSIONS_VOLUME_PATH` environment variable.

#### Scenario: Graceful degradation when `AGENT_SESSIONS_VOLUME_PATH` not set
- **WHEN** `AgentPool.evict(conversation_id)` is called with `purge=False`
- **AND** `AGENT_SESSIONS_VOLUME_PATH` environment variable is not set or is empty
- **THEN** Volume sync is skipped with a WARNING log
- **AND** local tmp directory is still deleted

## Test Requirements

Tests MUST be written in `tests/unit/test_agent_pool.py` BEFORE sync logic is implemented in `core/agent_pool.py` (RED phase).

Required test scenarios (RED-before-GREEN):
- `evict(purge=False)` with non-empty session dir → `WorkspaceClient.files.upload` called once per file; local dir deleted after upload
- `evict(purge=False)` with empty session dir → no `upload` calls; local dir deleted
- `evict(purge=False)` when `upload` raises → WARNING logged; pool entry removed; local dir deleted; no exception raised to caller
- `evict(purge=True)` → no `upload` calls; pool entry removed; local dir deleted
- `evict(purge=False)` with `AGENT_SESSIONS_VOLUME_PATH` unset → WARNING logged; no `upload` calls; local dir deleted
- Volume path is `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/filename` for each uploaded file
- `evict_stale()` calls `evict()` with `purge=False` (default) for each stale entry

Fixture additions required (in `tests/conftest.py`):
- `mock_workspace_files`: a mock for `WorkspaceClient.files` with `upload`, `download`, `list`, `delete` methods; add to existing `mock_workspace_client` fixture
- `session_dir_with_files`: a tmp directory fixture with 2 test files pre-created (e.g., `output.csv` and `results.txt`)
