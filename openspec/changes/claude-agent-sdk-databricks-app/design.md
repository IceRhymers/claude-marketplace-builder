## Context

The `usage-limits/` app establishes the canonical pattern for Databricks Apps in this repo: FastAPI backend serving a compiled React SPA via `SPAStaticFiles`, Lakebase/PostgreSQL via SQLAlchemy with OAuth token injection, background jobs via APScheduler, and deployment via `databricks.yml` asset bundles. The `claude-agent-app/` will follow this exact pattern while adding the Claude Agent SDK, SSE streaming, an in-memory AgentPool, and a Volume-backed skill/MCP configuration system.

The Databricks Apps reverse proxy injects `X-Forwarded-Access-Token` with each user's personal OAuth token, eliminating the need for a separate auth service. This token is the only identity primitive — it resolves the user's email address via `WorkspaceClient.current_user.me()` and is forwarded as-is to per-user MCP connections so tools like Slack act as the individual, not the app service principal.

## Goals / Non-Goals

**Goals:**
- Full FastAPI + React parity with `usage-limits/` (same toolchain, same deployment pattern)
- Streaming SSE chat with the Claude Agent SDK, persisting turns to Lakebase
- Per-user, per-conversation agent isolation via AgentPool with TTL eviction
- User-scoped MCP connections using the user's personal Databricks OAuth token
- Hot-reloadable skills and MCP config from a Databricks Volume (no code deployments for config changes)
- A publishable artifact pipeline (GitHub Actions + shell script) that bundles SKILL.md files and `.mcp.json` into versioned tarballs on the Volume
- Alembic-managed schema for `conversations` and `messages` tables

**Non-Goals:**
- Multi-tenant isolation beyond what the `user_id` filter provides (no row-level security policies)
- WebSocket-based streaming (SSE is sufficient and simpler with FastAPI)
- Real-time collaboration (multiple users in one conversation)
- Horizontal scaling / distributed AgentPool (single-instance Databricks App)
- Built-in eval framework (evals are handled separately by the `evals/` package)

## Decisions

### D1: SSE over WebSocket for streaming

**Decision:** Use Server-Sent Events (`GET /api/conversations/{id}/stream?message=...`) rather than WebSockets.

**Rationale:** FastAPI's `sse-starlette` library provides first-class SSE support with generator-based streaming that composes naturally with the Claude Agent SDK's async iterator interface. SSE is unidirectional (server → client), which matches the chat response pattern exactly. The frontend `EventSource` API handles reconnection and is universally supported. WebSockets add bidirectional complexity not needed here.

**Alternative considered:** WebSocket via `fastapi.WebSocket`. Rejected because it requires a more complex connection lifecycle (handshake, ping/pong, close frames) and does not compose as cleanly with `sse-starlette`.

### D2: AgentPool in-process dictionary, not Redis/external cache

**Decision:** The AgentPool is an in-process Python dictionary keyed by `conversation_id`, running in the single FastAPI worker process. TTL eviction runs via APScheduler on a configurable interval.

**Rationale:** Databricks Apps run as a single-instance process (no horizontal scaling). An in-process dict is zero-latency, requires no external infrastructure, and keeps the deployment footprint minimal — matching `usage-limits/`'s approach of using APScheduler for background work. Agent instances hold live MCP TCP connections that cannot be serialized across process boundaries anyway.

**Alternative considered:** Redis-backed session cache. Rejected — would require a Redis sidecar, adds operational overhead, and is architecturally mismatched (MCP connections are process-local).

### D3: Alembic for schema migrations instead of raw `create_all`

**Decision:** Use Alembic with a checked-in `alembic/` directory and an initial migration for `conversations` + `messages`. The lifespan startup event calls `alembic upgrade head` programmatically.

**Rationale:** `usage-limits/` uses inline `create_all` with manual column-add migrations, which becomes brittle at scale. Since this is a new app, adopting Alembic from day one gives a cleaner upgrade path. The startup-time upgrade is idempotent and takes <100ms against an already-current schema.

**Alternative considered:** `Base.metadata.create_all(engine)` as in `usage-limits/`. Rejected for new code — Alembic is the right foundation even if the first migration is simple.

### D4: Volume-backed config with `latest.json` pointer

**Decision:** Skills and MCP config are stored in a Databricks Volume. A `latest.json` file points to the current versioned artifact directory. An APScheduler job re-reads `latest.json` every 60 seconds to detect and load new versions.

**Rationale:** This decouples skill authoring from app deployment — skills team can publish new SKILL.md files or update `.mcp.json` without a Databricks App redeploy. The pointer pattern (`latest.json`) is atomic from the reader's perspective: old config stays active until `latest.json` is overwritten.

**Alternative considered:** Git-based config loaded at startup only. Rejected — requires credentials at runtime and forces a redeploy for every skill change.

### D5: User token injected into MCP connections at agent spawn, not stored

**Decision:** The user's `X-Forwarded-Access-Token` is used at agent spawn time to configure MCP transport headers. It is never written to the database or logged.

**Rationale:** Tokens are ephemeral OAuth tokens from the Databricks reverse proxy. They should not be persisted — they will expire. Passing them through the in-memory spawn path only (request → dependency → AgentPool.get_or_create → MCP transport) keeps the security boundary tight.

**Alternative considered:** Storing tokens in Lakebase keyed by `user_id` for agent re-use across requests. Rejected — stale/expired tokens would break MCP calls silently; re-resolving from the request header is always current.

### D6: React frontend follows usage-limits pattern exactly

**Decision:** Same stack: Vite, React 19, TanStack Router + Query, Radix UI, Tailwind CSS v4, TypeScript. Chat UI built with Radix primitives; SSE consumed via the native `EventSource` API wrapped in a custom TanStack Query mutation.

**Rationale:** Consistency with `usage-limits/` reduces cognitive overhead and allows sharing of auth patterns (`useAuth`, `AuthProvider`), UI primitives (Button, Card, etc.), and build tooling. The `EventSource` API is the standard browser SSE client and does not require additional dependencies.

### D7: Conversation title derived from first message

**Decision:** When a conversation is created, `title` is `null`. After the first turn completes, the backend sets `title` to the first 80 characters of the user's first message (truncated with ellipsis). No separate LLM call for title generation.

**Rationale:** Calling Claude again just for a title adds latency and cost. Truncated first-message title is "good enough" for conversation list UX and keeps the implementation simple. Can be upgraded later.

### D8: Test-Driven Development enforced — tests written before implementation

**Decision:** For every implementation task in `tasks.md`, a corresponding test-writing task appears immediately before it using the red-green-refactor cycle: write a failing test (RED), implement just enough to make it pass (GREEN), then refactor. No implementation task may be considered complete unless its preceding test task is also complete and the tests are green.

**Rationale:** Testing deferred to the end of a project (as in the original group-10 approach) allows design flaws and regressions to accumulate unchecked. Writing tests first forces implementers to think about the public contract of each module before writing any code, catches integration issues at the earliest possible moment, and produces a living regression suite that protects future changes. The `usage-limits/` app's `tests/` directory demonstrates the canonical test pattern for this repo — `claude-agent-app/` mirrors it exactly.

**Alternative considered:** Keeping tests in a final group and relying on developer discipline to write them. Rejected — historical evidence in this codebase shows testing is deprioritized when it is the last item. Structural enforcement (task ordering) is more reliable than convention.

**Implementation:** See `claude-agent-sdk-tdd` change for the testing framework spec, updated task ordering, and fixture contracts.

## Risks / Trade-offs

**[Risk] Single-instance AgentPool is lost on redeploy**
→ Mitigation: On restart, agents are lazily recreated from the first streaming request; conversation history is reloaded from Lakebase. Users experience at most one "cold start" turn per conversation after a deploy.

**[Risk] Long-lived MCP connections to uc-mcp-proxy may time out**
→ Mitigation: The MCP transport should be configured with `keepalive` / `reconnect` options. The `AgentPool` eviction sweep double-acts as a connection health check — evicted agents close their connections cleanly; new agents open fresh ones.

**[Risk] Token-per-user MCP connections scale O(concurrent users)**
→ Mitigation: TTL eviction bounds the pool size. Default TTL of 30 minutes is deliberately conservative — most chat sessions are short. `AGENT_TTL_MINUTES` is tunable if memory pressure is observed.

**[Risk] Volume read latency on hot-reload check**
→ Mitigation: The reload job checks `latest.json` (a tiny JSON file) not the full artifact. The tarball is only downloaded when the version string changes. DBFS reads are sub-second for small files.

**[Risk] Alembic upgrade at startup adds startup latency**
→ Mitigation: `alembic upgrade head` on an already-current schema is a no-op check taking <100ms. Only new migrations add time.

## Migration Plan

1. Create `claude-agent-app/` directory structure mirroring `usage-limits/`
2. Provision a new Lakebase instance (`claude-agent-app-db`) via `resources/lakebase.yml`
3. Configure a Databricks Volume for skills/MCP artifacts (manual one-time setup)
4. Run `alembic upgrade head` via the startup lifespan on first deploy
5. Deploy via `databricks bundle deploy` targeting the `dev` environment
6. Publish the initial skill artifact via `scripts/build-artifact.sh` + manual upload or GitHub Actions
7. Promote to `prod` target after smoke-testing in `dev`

**Rollback:** Delete the Databricks App resource and drop the Lakebase instance. No shared state with `usage-limits/`.

## Open Questions

- **MCP proxy endpoint:** What is the production `uc-mcp-proxy` URL for the Slack MCP server? Needs to be documented in `.mcp.json.template` and referenced in the deployment guide.
- **Volume path convention:** Should `SKILLS_VOLUME_PATH` follow `dbfs:/Volumes/<catalog>/<schema>/<volume>/skills` or a different Unity Catalog Volume path format? To be confirmed with the infrastructure team.
- **Concurrent request safety:** If two SSE requests arrive simultaneously for the same `conversation_id`, both will try to `get_or_create` from the pool. The pool needs a per-key lock or atomic `setdefault` to avoid double-initialization. Needs explicit implementation decision during coding.
- **Conversation title update timing:** Should the title be updated synchronously at end of first streaming turn, or asynchronously via a background task? Synchronous is simpler; async avoids adding to the hot path.
