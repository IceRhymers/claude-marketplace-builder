## Context

The `claude-agent-app/` follows the pattern established in `usage-limits/`: FastAPI + APScheduler + SQLAlchemy against Lakebase, with the `AgentPool` as an in-process singleton keyed by `conversation_id`. The pool already assigns each conversation a local sandbox directory at `/tmp/claude-agent-sessions/{conversation_id}/` and already stores `user_id` in every `AgentEntry`. The `messages` table in Lakebase is the authoritative store for conversation history; the `AgentPool._history` in-process list is a derived, ephemeral copy.

Session persistence wires these existing pieces together: Lakebase messages become the source of truth for history hydration; the Databricks Files API (`WorkspaceClient.files`) becomes the durable store for file sandboxes; and the existing `evict()` / `get_or_create()` call sites become the hooks for sync/restore. The TTL cleanup job slots into the same APScheduler instance that already runs agent eviction and skills reload.

## Goals / Non-Goals

**Goals:**
- Hydrate a freshly spawned agent's `_history` from Lakebase `messages` rows on every cache miss in `get_or_create`
- Sync local session sandbox to `{AGENT_SESSIONS_VOLUME_PATH}/{user_id}/{conversation_id}/` on every non-purge `evict()` call
- Restore session sandbox from Volume to local tmp on cache miss when Volume path exists
- Clean up Volume path + pool entry on manual conversation delete (with `purge=True` — skip Volume sync)
- Purge stale conversations (Volume + Lakebase + pool) via a daily APScheduler job
- Degrade gracefully if `AGENT_SESSIONS_VOLUME_PATH` is not configured (log warning, skip sync/restore)

**Non-Goals:**
- Real-time file sync on every agent message turn (only sync on eviction)
- Distributed file locking across multiple app instances (app is single-instance by design)
- Versioning or rollback of previous session file states
- Streaming large files in chunks (standard Databricks Files API upload/download is sufficient for agent session artifacts)
- Recovering in-progress work if the process crashes mid-turn (messages are in DB; files at risk are only those written since last eviction, which is acceptable per D2)

## Decisions

### D1: `purge=True` on `evict()` instead of a separate `delete()` method

**Decision:** Add a `purge: bool = False` keyword argument to `AgentPool.evict()`. When `purge=True`, the method skips the Volume sync step and proceeds directly to local tmp cleanup. When `purge=False` (default), it syncs files to Volume first.

**Rationale:** A single eviction path avoids duplicating the MCP connection teardown, local tmp cleanup, and pool dictionary removal logic. All callers (TTL sweep, manual delete, shutdown) converge on the same code path with a single flag controlling whether files are preserved or discarded. A separate `delete()` method would copy the teardown logic and risk drift.

**Alternative considered:** A separate `purge(conversation_id)` method distinct from `evict()`. Rejected — it duplicates connection teardown and cleanup code that should not diverge.

### D2: Sync on eviction, not on every message turn

**Decision:** File sync to the Databricks Volume happens only in `evict()`, not after every agent turn.

**Rationale:** The Databricks Files API incurs network I/O on each call. Syncing after every turn adds latency to the hot streaming path, which would degrade perceived responsiveness for multi-turn conversations. The risk of data loss (files written since last eviction lost if process crashes) is acceptable: the most valuable artifacts of a session are the conversation messages, which are already persisted to Lakebase atomically on every turn. File artifacts are secondary outputs. This mirrors common session storage patterns where state is checkpointed at session end rather than on every operation.

**Alternative considered:** Sync after every `stream()` completion. Rejected — adds Volume write latency to every turn; Volume IOPS are not designed for per-message frequency.

### D3: Databricks Volume over Lakebase BLOB columns for file storage

**Decision:** Store session file sandboxes in a Databricks Unity Catalog Volume accessed via `WorkspaceClient.files` API (or `dbutils.fs` equivalent).

**Rationale:** Agent session files can include large artifacts — CSVs loaded for analysis, generated code files, downloaded data. Lakebase (PostgreSQL) `BYTEA` columns are technically capable but poorly suited for large binary blobs: they inflate row size, complicate backup/restore, and lack native file semantics. Databricks Volumes are purpose-built for file storage at scale, integrate with Unity Catalog governance, and expose a simple HTTP-based Files API with upload/download/list/delete operations matching exactly what session persistence needs.

**Alternative considered:** Store files as `BYTEA` in a new `session_files` Lakebase table. Rejected — blob-in-DB is an antipattern for files larger than a few KB; agent sessions can easily produce MB-scale files.

### D4: Daily TTL cleanup job, not on-demand per-request

**Decision:** A daily APScheduler job (configurable via `CONVERSATION_TTL_CHECK_HOURS`, default 24) sweeps for conversations where `updated_at < now() - CONVERSATION_TTL_DAYS days` and purges them.

**Rationale:** Conversation accumulation is a slow, background process — users create at most a handful of conversations per day. Checking on every request for stale conversations adds unnecessary query overhead to the hot path. A daily job is sufficient to keep storage bounded and aligns with how the existing `agent_eviction` job is structured. APScheduler is already running in the app; adding one more job is minimal overhead.

**Alternative considered:** Evict stale conversations lazily on each `get_or_create` call (check age of conversation on access). Rejected — does not handle conversations that are never accessed again (the common case for TTL targets); orphaned Volume paths and Lakebase rows would never be cleaned.

### D5: Restore before hydration ordering

**Decision:** In `get_or_create` on a cache miss, restore files from Volume first, then hydrate `_history` from Lakebase messages.

**Rationale:** The agent's system prompt references the session sandbox path. If history hydration runs first and any injected history references specific file paths (e.g., "I saved results to `/tmp/claude-agent-sessions/{id}/analysis.csv`"), those paths must exist in the local sandbox for the agent to act on them in the next turn. Restoring files first ensures the sandbox is populated before the agent processes historical context, preventing stale path references from triggering errors on the next tool call.

**Alternative considered:** Hydrate history first, then restore files. Rejected — creates a window where historical messages reference file paths that do not yet exist locally; risk of subtle tool-call failures on first turn after resume.

### D6: `WorkspaceClient.files` API for Volume I/O

**Decision:** Use `databricks.sdk.WorkspaceClient` with the `workspace.files` service (Files API) for all Volume upload, download, list, and delete operations.

**Rationale:** The `databricks-sdk` package is already a declared dependency. The Files API (`client.files.upload()`, `client.files.download()`, `client.files.list()`, `client.files.delete()`) provides a clean Python interface to Databricks Volumes without requiring `dbutils` (which is only available in notebook/cluster contexts, not in Databricks App processes). The SDK handles authentication automatically from the app's service principal credentials.

**Alternative considered:** Use `dbutils.fs.cp` for file operations. Rejected — `dbutils` is not available outside Databricks notebook/cluster runtimes; Databricks Apps run as standard Python processes where the SDK is the correct integration point.

### D7: Graceful degradation when `AGENT_SESSIONS_VOLUME_PATH` is unset

**Decision:** If `AGENT_SESSIONS_VOLUME_PATH` is not configured, all Volume-related operations (sync on eviction, restore on resume, TTL Volume cleanup) are skipped with a `WARNING` log. The app continues to function, simply without file persistence.

**Rationale:** This allows the app to run in development or testing environments without a Volume configured, matching the existing pattern where missing `SKILLS_VOLUME_PATH` is non-fatal. Tests can omit the env var and mock Volume calls without needing to configure real infrastructure.

## Risks / Trade-offs

**[Risk] Volume sync adds latency to eviction sweep**
→ Mitigation: Eviction runs in a background APScheduler job on a 15-minute interval (half of the 30-minute TTL), not on the request path. File upload latency (typically sub-second for small session dirs) does not affect user-facing request latency.

**[Risk] Volume sync failure blocks local tmp cleanup**
→ Mitigation: Per spec D1 / `file-sync-on-eviction`, if Volume sync fails, the error is logged as a WARNING and local tmp cleanup proceeds anyway. The pool entry is still removed. Files may be lost on that eviction cycle, but the app is not blocked.

**[Risk] Large session directories slow down eviction**
→ Mitigation: Agent sessions are sandboxed at `/tmp/claude-agent-sessions/{id}/` and scoped to artifacts created during the session. The system prompt already constrains agents to that directory. For very large files, the Volume upload will take longer but remains non-blocking for user traffic.

**[Risk] Volume paths orphaned if app process is killed before eviction**
→ Mitigation: The TTL cleanup job handles any orphaned Volume paths by purging stale conversations — paths whose conversations are deleted or TTL-expired are cleaned up within 24 hours (one TTL check cycle).

**[Risk] Concurrent `get_or_create` for same conversation_id during restore**
→ Mitigation: `get_or_create` holds `_lock` (threading.Lock) during the cache-miss path including the restore step. A second concurrent request for the same conversation will block on the lock and then find the agent already in the pool, taking the cache-hit path. No double-restore can occur.

## Migration Plan

1. Add `AGENT_SESSIONS_VOLUME_PATH` to `claude-agent-app/app.yml` env var list (optional, with empty default)
2. Add `CONVERSATION_TTL_DAYS` and `CONVERSATION_TTL_CHECK_HOURS` to `app.yml`
3. Implement specs in order: `history-hydration` → `file-sync-on-eviction` → `file-restore-on-resume` → `conversation-delete-cleanup` → `conversation-ttl-cleanup`
4. Each spec follows RED-before-GREEN TDD: write failing tests first, then implement
5. Deploy to `dev` target; verify eviction + restore round-trip with a test conversation containing files
6. Promote to `prod` after smoke-test validation in `dev`

**Rollback:** Remove `AGENT_SESSIONS_VOLUME_PATH` from env — all Volume operations are skipped. The code paths degrade to the pre-change behavior (agents start fresh, local tmp deleted on eviction).

## Open Questions

- **Volume path for Databricks Files API:** The `WorkspaceClient.files` API uses a `/Volumes/<catalog>/<schema>/<volume>/<path>` format. Confirm with infrastructure that the Unity Catalog path matches the format expected by `client.files.upload()` (not the `dbfs:/Volumes/` prefix used by `dbutils`).
- **Files API pagination:** `client.files.list()` may return paginated results for large session directories. Confirm pagination handling is needed or if a flat listing suffices for typical session sizes.
- **TTL job DB session lifecycle:** The daily TTL cleanup job runs in an APScheduler thread and needs a dedicated SQLAlchemy session. Confirm whether the session should use the same `session_factory` from `app.state` or create a dedicated engine for background threads.
