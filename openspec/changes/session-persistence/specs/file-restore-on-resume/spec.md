## MODIFIED Requirements

### Capability: `agent-pool` — file restore from Volume on cache miss

#### Requirement: Restore session sandbox from Volume before returning fresh agent
The system SHALL check whether a Volume path exists at `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/` when `AgentPool.get_or_create` results in a cache miss. If the path exists and contains files, they SHALL be downloaded to the new local session sandbox at `/tmp/claude-agent-sessions/{conversation_id}/` before the agent is returned.

#### Scenario: Cache miss with existing Volume files — sandbox restored
- **WHEN** `AgentPool.get_or_create` results in a cache miss for `conversation_id`
- **AND** `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/` exists on the Volume and contains files
- **THEN** all files from that Volume path are downloaded to the local session sandbox at `/tmp/claude-agent-sessions/{conversation_id}/`
- **AND** the agent is spawned with the restored files already present in its session directory
- **AND** file restore completes BEFORE history hydration begins

#### Scenario: Cache miss for new conversation — no Volume path exists
- **WHEN** `AgentPool.get_or_create` results in a cache miss for a brand-new `conversation_id`
- **AND** no path exists at `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/` on the Volume
- **THEN** no download calls are made (no-op)
- **AND** the agent is spawned with an empty session sandbox (same behavior as before this change)

#### Scenario: Restore occurs before history hydration
- **WHEN** `AgentPool.get_or_create` handles a cache miss with both Volume files and Lakebase messages
- **THEN** files are downloaded to the local sandbox FIRST
- **AND** `_history` is populated from Lakebase SECOND
- **AND** the agent is returned with both files and history intact

#### Requirement: Volume restore failure is non-fatal
The system SHALL NOT raise an exception if Volume download fails during a cache miss in `get_or_create`. Instead, the failure SHALL be logged as a WARNING, the agent SHALL be spawned with whatever files were successfully downloaded (or an empty sandbox if none), and execution SHALL continue to history hydration.

#### Scenario: Volume download failure during restore
- **WHEN** `AgentPool.get_or_create` results in a cache miss
- **AND** `WorkspaceClient.files.download()` raises an exception for one or more files
- **THEN** the exception is caught and logged as a WARNING
- **AND** agent spawning continues with a partially restored or empty session sandbox
- **AND** no exception propagates from `get_or_create` due to the restore failure

#### Requirement: Graceful degradation when `AGENT_SESSIONS_VOLUME_PATH` not set
- **WHEN** `AgentPool.get_or_create` handles a cache miss
- **AND** `AGENT_SESSIONS_VOLUME_PATH` is not set or empty
- **THEN** Volume restore is skipped with a WARNING log; agent is spawned with an empty session sandbox

## Test Requirements

Tests MUST be written in `tests/unit/test_agent_pool.py` BEFORE restore logic is implemented in `core/agent_pool.py` (RED phase).

Required test scenarios (RED-before-GREEN):
- Cache miss with Volume files present → `WorkspaceClient.files.download` called for each file; files land in local session sandbox before agent is returned
- Cache miss with no Volume path / empty Volume path → no `download` calls; agent spawned with empty sandbox
- Cache miss with Volume download failure → WARNING logged; agent spawned (possibly with partial sandbox); no exception raised from `get_or_create`
- Cache miss with `AGENT_SESSIONS_VOLUME_PATH` unset → WARNING logged; no Volume calls; agent spawned normally
- File restore happens before history hydration: assert restore mock called before DB messages query (use `unittest.mock.call_args_list` or `MagicMock.assert_called_before`)
- Cache hit → no `download` calls (restore only on cache miss)

Fixture additions required (in `tests/conftest.py`):
- `mock_volume_with_files`: mock of `WorkspaceClient.files.list()` that returns a list of 2 file metadata objects, and `download()` that returns stub file bytes
- `mock_volume_empty`: mock of `WorkspaceClient.files.list()` that returns an empty list (path exists but no files)
