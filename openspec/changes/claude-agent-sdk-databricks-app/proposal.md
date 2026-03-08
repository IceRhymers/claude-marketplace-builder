## Why

Databricks users need a team-hosted, skills-aware Claude chat application that acts on behalf of each individual user — using their own identity for tool calls like Slack — rather than a shared service principal, enabling accountability, personalization, and auditability across the organization. Building this as a Databricks App in the existing repo provides a repeatable pattern for deploying Claude Agent SDK applications alongside the usage-limits app.

## What Changes

- New top-level `claude-agent-app/` directory following the same FastAPI + React structure as `usage-limits/`
- FastAPI backend with SSE streaming chat endpoints, AgentPool lifecycle management, and Lakebase-backed conversation state
- React 19 frontend with a chat UI, conversation history sidebar, and real-time streaming message rendering
- Claude Agent SDK integration using skills and MCP tool connections loaded from a Databricks Volume at runtime
- User-scoped MCP connections via `uc-mcp-proxy` — each agent instance receives the user's `X-Forwarded-Access-Token` so tools like Slack operate as that user
- `AgentPool` keyed by `conversation_id` with TTL-based eviction via APScheduler
- `conversations` and `messages` Lakebase tables, user-isolated via token-resolved `user_id`
- Hot-reloadable skills and MCP config from a Databricks Volume (`latest.json` pointer pattern)
- `scripts/build-artifact.sh` + GitHub Actions workflow to bundle SKILL.md files and `.mcp.json` configs into versioned artifacts uploaded to the Volume
- `databricks.yml` asset bundle config and `app.yml` for Databricks App deployment

## Capabilities

### New Capabilities

- `agent-chat`: Streaming chat via SSE — create/continue conversations, stream agent responses with tool-call events, cancel in-flight streams
- `agent-pool`: Session-scoped agent lifecycle — spawn, retrieve, and evict `ClaudeAgent` instances keyed by `conversation_id` with configurable TTL
- `conversation-state`: Persistent conversation and message storage in Lakebase — CRUD for conversations and messages, user-isolated via resolved `user_id`
- `user-identity`: Token-to-user resolution from `X-Forwarded-Access-Token` header using the Databricks SDK, shared across all endpoints
- `mcp-config`: Volume-backed MCP and skill configuration — reads `latest.json` pointer, hot-reloads on new artifact publish without restart
- `artifact-pipeline`: GitHub Actions + shell script pipeline that bundles SKILL.md files and `.mcp.json` configs into versioned tarballs, uploads to Databricks Volume, and updates the `latest.json` pointer

### Modified Capabilities

<!-- No existing specs to modify -->

## Impact

- New directory `claude-agent-app/` added at repo root — no changes to `usage-limits/` or any existing plugin
- New Python dependencies: `anthropic[agent-sdk]`, `sse-starlette`, `apscheduler`
- New frontend packages: `@tanstack/react-query` (streaming), EventSource handling for SSE
- Requires a Databricks Volume path configured via env var for skill/MCP artifact storage
- Lakebase instance provisioned for `conversations` and `messages` tables
- GitHub Actions secrets: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `VOLUME_PATH`
