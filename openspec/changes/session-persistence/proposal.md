## Why

Today, when the AgentPool evicts an agent after 30 minutes of inactivity, two things are lost permanently: the conversation history (requiring a fresh context-free agent on resume) and any files the agent created in its local session sandbox. The conversation history is already durable in Lakebase, but it is not re-injected into a freshly spawned agent — the new agent starts with an empty `_history`, giving Claude no awareness of what was discussed. The file sandbox is simply deleted, meaning any CSVs, code files, or artifacts produced during the session are gone. When a user resumes after a break, they face a broken experience: Claude does not remember the prior conversation and cannot reference files it previously created.

Tying the file sandbox and conversation history together through a unified persistence lifecycle fixes both problems: history is hydrated from Lakebase into fresh agents, and files are synced to a Databricks Volume on eviction and restored on resume. A conversation delete (manual or TTL-based) cleanly removes both the Volume path and Lakebase rows, preventing orphaned storage accumulation.

## What Changes

- `AgentPool.get_or_create`: on a cache miss, hydrate the new agent's `_history` from `messages` table rows before returning (history hydration)
- `AgentPool.evict()`: before deleting the local `session_dir`, sync its contents to `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/` on the Databricks Volume; add `purge=True` parameter to skip sync when files should be discarded
- `AgentPool.get_or_create`: on a cache miss, check Volume for existing files and download them to the new local session sandbox before history hydration (file restore on resume)
- `DELETE /api/conversations/{id}`: evict from pool with `purge=True` (skip sync), delete the Volume path, and let FK cascade handle Lakebase rows
- New APScheduler daily job: find conversations where `updated_at < now() - CONVERSATION_TTL_DAYS days`, evict each with `purge=True`, delete their Volume paths, and delete Lakebase rows
- New env vars: `AGENT_SESSIONS_VOLUME_PATH`, `CONVERSATION_TTL_DAYS` (default 30), `CONVERSATION_TTL_CHECK_HOURS` (default 24)

## Capabilities

### Modified Capabilities

- `agent-pool`: add `purge=True` to `evict()`, add Volume sync on eviction, add Volume restore on resume, add history hydration on cache miss — all wired in `AgentPool.get_or_create` and `AgentPool.evict()`
- `agent-chat`: `DELETE /api/conversations/{id}` extended to also delete the Volume path for the conversation

### New Capabilities

- `history-hydration`: hydrate agent `_history` from `messages` table on cache miss in `get_or_create`
- `file-sync-on-eviction`: sync local session sandbox to Databricks Volume when `evict()` is called without `purge=True`
- `file-restore-on-resume`: restore files from Volume to new local session sandbox on cache miss in `get_or_create`
- `conversation-delete-cleanup`: clean up Volume path and evict from pool on manual conversation delete
- `conversation-ttl-cleanup`: daily APScheduler job purging conversations older than `CONVERSATION_TTL_DAYS`

## Impact

- No changes to the React frontend — persistence is entirely backend-side
- New Python dependency: `databricks-sdk` is already declared; no new packages required
- New env var `AGENT_SESSIONS_VOLUME_PATH` required for Volume operations; app degrades gracefully if unset (skips file sync/restore with a warning)
- New env vars `CONVERSATION_TTL_DAYS` and `CONVERSATION_TTL_CHECK_HOURS` with safe defaults (30 days, 24 hours)
- Eviction path now does I/O to a Databricks Volume — adds latency to TTL eviction sweep, which is acceptable because eviction runs in a background APScheduler job, not on the hot request path
- Volume storage grows proportional to number of active conversations; TTL cleanup bounds it
- Existing `agent-chat` and `agent-pool` spec contracts are preserved; changes are additive or backward-compatible extensions
