## ADDED Requirements

### Capability: `conversation-ttl-cleanup` — daily stale conversation purge

#### Requirement: Daily APScheduler job purges stale conversations
The system SHALL run a background APScheduler job that periodically finds and purges conversations where `updated_at < now() - CONVERSATION_TTL_DAYS days`. The job SHALL:
1. Query the `conversations` table for rows older than the TTL threshold
2. For each stale conversation: call `AgentPool.evict(conversation_id, purge=True)`, delete the Volume path `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/`, and delete the Lakebase row (cascade removes messages)
3. Log the count of purged conversations

The job SHALL be registered in the APScheduler instance at app startup with an interval of `CONVERSATION_TTL_CHECK_HOURS` hours (default 24). The job SHALL also run once at startup to handle any stale conversations from before the app was last running.

#### Scenario: Stale conversations purged on job run
- **WHEN** the TTL cleanup job runs
- **AND** the `conversations` table contains rows where `updated_at < now() - CONVERSATION_TTL_DAYS days`
- **THEN** each stale conversation is evicted from the pool with `purge=True`
- **AND** its Volume path is deleted via `WorkspaceClient.files.delete()`
- **AND** its Lakebase row (and cascaded messages) are deleted
- **AND** a log line records the count of purged conversations

#### Scenario: Active conversations not purged
- **WHEN** the TTL cleanup job runs
- **AND** a conversation's `updated_at` is within the TTL window (`now() - CONVERSATION_TTL_DAYS days`)
- **THEN** that conversation is NOT evicted, NOT deleted from Volume, and NOT deleted from Lakebase

#### Scenario: Job runs at startup
- **WHEN** the FastAPI app starts
- **THEN** the TTL cleanup job executes once immediately at startup in addition to its scheduled interval
- **AND** any stale conversations present before the app restarted are purged on first run

#### Requirement: TTL configurable via environment variables
The TTL threshold and check interval SHALL be configurable:
- `CONVERSATION_TTL_DAYS` (int, default 30): number of days of inactivity before a conversation is considered stale
- `CONVERSATION_TTL_CHECK_HOURS` (int, default 24): how frequently the cleanup job runs, in hours

#### Scenario: Custom TTL applied
- **WHEN** `CONVERSATION_TTL_DAYS=7` is set
- **THEN** conversations where `updated_at < now() - 7 days` are purged on the next job run

#### Requirement: Per-conversation failures are isolated
The system SHALL NOT abort the entire TTL cleanup job if a single conversation's cleanup fails (e.g., Volume delete fails for one conversation). The failure SHALL be logged as a WARNING and the job SHALL continue to the next stale conversation.

#### Scenario: Single conversation cleanup failure is isolated
- **WHEN** the TTL job processes a batch of 3 stale conversations
- **AND** `WorkspaceClient.files.delete()` raises for the second conversation
- **THEN** the second conversation's Volume cleanup failure is logged as a WARNING
- **AND** the first and third conversations are still fully purged
- **AND** all three Lakebase rows are deleted (or attempted)

#### Requirement: Graceful degradation when `AGENT_SESSIONS_VOLUME_PATH` not set
- **WHEN** the TTL cleanup job runs
- **AND** `AGENT_SESSIONS_VOLUME_PATH` is not set
- **THEN** Volume delete is skipped for all conversations with a WARNING log
- **AND** Lakebase rows are still deleted (pool eviction and DB cleanup proceed normally)

## Test Requirements

Tests MUST be written in `tests/unit/test_ttl_cleanup.py` (new test file) BEFORE the TTL job is implemented in `main.py` or a dedicated `core/cleanup.py` module (RED phase).

Required test scenarios (RED-before-GREEN):
- Job with 2 stale conversations → both evicted with `purge=True`; both Volume paths deleted; both DB rows deleted
- Job with 0 stale conversations → no evictions, no Volume deletes, no DB deletes; log shows "0 purged"
- Job with mixed stale/active conversations → only stale ones purged; active conversation untouched
- `CONVERSATION_TTL_DAYS=7` → threshold computed correctly (conversations with `updated_at < 7 days ago` selected)
- Volume delete fails for one of two stale conversations → WARNING logged for that conversation; other conversation fully purged; both DB rows deleted
- `AGENT_SESSIONS_VOLUME_PATH` unset → no Volume deletes; DB rows still deleted; no exception raised
- Job is registered in scheduler at startup with `hours=CONVERSATION_TTL_CHECK_HOURS` interval (verify via mock scheduler)
- Job runs immediately at startup (`run_date` trigger or `misfire_grace_time=0` / explicit immediate call)

Fixture additions required (in `tests/conftest.py`):
- `stale_conversations_db`: `db_session` fixture variant pre-populated with 2 `Conversation` rows having `updated_at` 35 days ago and 1 `Conversation` row with `updated_at` 5 days ago (within 30-day TTL)
- `mock_scheduler`: mock `BackgroundScheduler` with `add_job` and `start` mocked to capture registered jobs
