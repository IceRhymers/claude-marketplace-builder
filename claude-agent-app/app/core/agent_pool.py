"""In-process AgentPool — keyed by conversation_id with TTL eviction."""

from __future__ import annotations

import dataclasses
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from core.skills import SkillsConfig, substitute_token

logger = logging.getLogger(__name__)

SESSION_BASE = Path(tempfile.gettempdir()) / "claude-agent-sessions"


@dataclasses.dataclass
class AgentEntry:
    """A pool entry holding an agent and its last-access metadata."""
    agent: Any
    last_accessed: datetime
    user_id: str
    session_dir: Path
    conversation_id: str = ""


def build_agent(
    session_dir: Path,
    mcp_config: dict,
    enabled_skill_names: set[str],
    skills_config: SkillsConfig,
) -> Any:
    """Construct a Claude agent, mounting enabled skills into session sandbox.

    Steps:
    1. Create session_dir/.claude/skills/ directory
    2. Copy each enabled skill directory from skills_config into the mount point
    3. Initialise Claude Agent SDK (with fallback to StubAgent)

    Args:
        session_dir: The sandbox directory for this conversation.
        mcp_config: MCP server configuration (already token-substituted).
        enabled_skill_names: Set of skill names the user has enabled.
        skills_config: Full SkillsConfig with SkillDefinition paths.

    Returns:
        An agent instance with an async `stream(message)` generator method.

    Raises:
        RuntimeError: If skill directory copy fails.
    """
    # Step 1: Create .claude/skills/ directory
    skills_mount = session_dir / ".claude" / "skills"
    skills_mount.mkdir(parents=True, exist_ok=True)

    # Step 2: Copy enabled skill directories
    for name in enabled_skill_names:
        if name in skills_config.skills:
            skill_def = skills_config.skills[name]
            dest = skills_mount / name
            if not dest.exists():
                shutil.copytree(str(skill_def.path), str(dest))

    # Step 3: Initialise Claude Agent SDK (with fallback)
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions

        options = ClaudeAgentOptions(
            cwd=str(session_dir),
            setting_sources=["project"],
            allowed_tools=["Skill", "Bash", "Read", "Write"],
        )

        class SDKAgent:
            def __init__(self, options, mcp_config, session_dir):
                self._options = options
                self._mcp_config = mcp_config
                self._session_dir = session_dir
                self._history: list[dict] = []

            async def stream(self, message: str):
                """Stream a response using claude_agent_sdk.query()."""
                self._history.append({"role": "user", "content": message})
                full_text = ""
                try:
                    async for sdk_message in query(prompt=message, options=self._options):
                        if hasattr(sdk_message, "type"):
                            if sdk_message.type == "text":
                                full_text += sdk_message.text
                                yield {"type": "text_delta", "text": sdk_message.text}
                            elif sdk_message.type == "tool_use":
                                yield {
                                    "type": "tool_use",
                                    "tool": sdk_message.name,
                                    "input": sdk_message.input,
                                }
                            elif sdk_message.type == "tool_result":
                                yield {
                                    "type": "tool_result",
                                    "tool": sdk_message.tool_use_id,
                                    "result": sdk_message.content,
                                }
                except Exception as exc:
                    logger.error("SDK stream error: %s", exc)
                    raise
                self._history.append({"role": "assistant", "content": full_text})
                yield {"type": "done"}

            def close(self):
                pass

        return SDKAgent(options, mcp_config, session_dir)

    except ImportError:
        logger.warning("claude_agent_sdk not available — falling back to stub agent")

        class StubAgent:
            def __init__(self, session_dir: Path):
                self._session_dir = session_dir
                self._history: list[dict] = []

            async def stream(self, message: str):
                yield {"type": "text_delta", "text": "Agent SDK not configured."}
                yield {"type": "done"}

            def close(self):
                pass

        return StubAgent(session_dir)


class AgentPool:
    """In-memory pool of agents, keyed by conversation_id."""

    def __init__(self):
        self._pool: dict[str, AgentEntry] = {}
        self._lock = threading.Lock()
        self._ws_client: Any = None

    def set_workspace_client(self, client: Any) -> None:
        """Set the Databricks WorkspaceClient used for Volume operations."""
        self._ws_client = client

    def _session_dir(self, conversation_id: str) -> Path:
        """Return the session sandbox directory for a given conversation."""
        return SESSION_BASE / conversation_id

    def _sync_to_volume(self, entry: AgentEntry, volume_base: str) -> None:
        """Upload all files from session_dir to Volume. Non-fatal on error."""
        if not entry.session_dir.exists() or not any(entry.session_dir.iterdir()):
            return  # empty dir, skip
        volume_path = f"{volume_base}/{entry.user_id}/{entry.conversation_id}"
        try:
            for file in entry.session_dir.rglob("*"):
                if file.is_file():
                    relative = file.relative_to(entry.session_dir)
                    with open(file, "rb") as f:
                        self._ws_client.files.upload(f"{volume_path}/{relative}", f, overwrite=True)
        except Exception as exc:
            logger.warning("File sync to Volume failed (non-fatal): %s", exc)

    def _restore_from_volume(self, entry: AgentEntry, volume_base: str) -> None:
        """Download files from Volume to session_dir. Non-fatal on error."""
        volume_path = f"{volume_base}/{entry.user_id}/{entry.conversation_id}"
        try:
            items = list(self._ws_client.files.list_directory_contents(volume_path))
        except Exception:
            return  # Volume path doesn't exist or isn't accessible — new conversation
        try:
            for item in items:
                if item.is_directory:
                    continue
                relative = item.path.removeprefix(volume_path).lstrip("/")
                dest = entry.session_dir / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                content = self._ws_client.files.download(item.path).contents
                dest.write_bytes(content.read())
        except Exception as exc:
            logger.warning("File restore from Volume failed (non-fatal): %s", exc)

    async def get_or_create(
        self,
        conversation_id: str,
        user_id: str,
        access_token: str,
        skills_config: SkillsConfig,
        db: Any = None,
    ) -> Any:
        """Return an existing agent or spawn a new one.

        Args:
            conversation_id: Key for pool lookup.
            user_id: Owner of this conversation.
            access_token: User's OAuth token for MCP connections.
            skills_config: Current loaded skills/MCP configuration.
            db: SQLAlchemy Session for history hydration and pref lookup (optional).

        Returns:
            Agent instance.

        Raises:
            RuntimeError: If agent initialization fails.
        """
        with self._lock:
            if conversation_id in self._pool:
                entry = self._pool[conversation_id]
                entry.last_accessed = datetime.now(timezone.utc)
                logger.debug("AgentPool: reusing agent for %s", conversation_id)
                return entry.agent

            # Substitute user token into MCP config
            mcp_config = substitute_token(skills_config.mcp_config, access_token)

            # Create isolated session directory
            session_dir = self._session_dir(conversation_id)
            session_dir.mkdir(parents=True, exist_ok=True)

            # Create an entry (needed for _restore_from_volume and _sync_to_volume)
            entry = AgentEntry(
                agent=None,  # placeholder until agent is built
                last_accessed=datetime.now(timezone.utc),
                user_id=user_id,
                session_dir=session_dir,
                conversation_id=conversation_id,
            )

            # Step 1: Restore files from Volume (before history hydration)
            volume_base = os.environ.get("AGENT_SESSIONS_VOLUME_PATH", "")
            if volume_base and self._ws_client:
                self._restore_from_volume(entry, volume_base)
            elif not volume_base:
                logger.warning("AGENT_SESSIONS_VOLUME_PATH not set — skipping file restore")

            # Step 2: Resolve enabled skills for this user
            if db is not None:
                try:
                    from deps import get_user_skill_prefs
                    enabled_skills = get_user_skill_prefs(user_id, db, skills_config)
                except Exception as exc:
                    logger.error("AgentPool: skill prefs lookup failed for %s: %s", conversation_id, exc)
                    raise RuntimeError(f"Skill prefs lookup failed: {exc}") from exc
            else:
                # No DB available — default all skills to enabled
                enabled_skills = set(skills_config.skills.keys())

            # Step 3: Resolve enabled MCP servers for this user
            if db is not None:
                try:
                    from deps import get_user_mcp_prefs
                    enabled_mcp_names = get_user_mcp_prefs(user_id, db, mcp_config)
                    # Filter mcp_config to only enabled servers
                    filtered_mcp_config = {
                        "mcpServers": {
                            name: cfg
                            for name, cfg in mcp_config.get("mcpServers", {}).items()
                            if name in enabled_mcp_names
                        }
                    }
                except Exception as exc:
                    logger.error("AgentPool: mcp prefs lookup failed for %s: %s", conversation_id, exc)
                    raise RuntimeError(f"MCP prefs lookup failed: {exc}") from exc
            else:
                filtered_mcp_config = mcp_config

            # Step 4: Hydrate history from DB
            history: list[dict] = []
            if db is not None:
                try:
                    from core.models import Message
                    messages = (
                        db.query(Message)
                        .filter(Message.conversation_id == conversation_id)
                        .order_by(Message.created_at.asc())
                        .all()
                    )
                    history = [{"role": m.role, "content": m.content} for m in messages]
                except Exception as exc:
                    logger.error("AgentPool: history hydration failed for %s: %s", conversation_id, exc)
                    raise RuntimeError(f"History hydration failed: {exc}") from exc

            # Step 5: Build the agent (copies skills, initialises SDK)
            try:
                agent = build_agent(
                    session_dir=session_dir,
                    mcp_config=filtered_mcp_config,
                    enabled_skill_names=enabled_skills,
                    skills_config=skills_config,
                )
            except Exception as exc:
                logger.error("AgentPool: failed to build agent for %s: %s", conversation_id, exc)
                raise RuntimeError(f"Agent initialization failed: {exc}") from exc

            # Step 6: Inject history into agent
            agent._history = history

            # Step 7: Store in pool
            entry.agent = agent
            self._pool[conversation_id] = entry
            logger.info("AgentPool: spawned new agent for conversation %s (user=%s)", conversation_id, user_id)
            return agent

    def evict(self, conversation_id: str, purge: bool = False) -> None:
        """Remove a single conversation from the pool.

        Args:
            conversation_id: The conversation to evict.
            purge: If True, skip Volume sync (for manual delete / TTL purge).
                   If False (default), sync session files to Volume before cleanup.
        """
        with self._lock:
            entry = self._pool.pop(conversation_id, None)
        if entry is None:
            return

        try:
            entry.agent.close()
        except Exception as exc:
            logger.warning("AgentPool: close() error during evict: %s", exc)

        # Sync to Volume unless purge=True
        if not purge and self._ws_client:
            volume_base = os.environ.get("AGENT_SESSIONS_VOLUME_PATH", "")
            if volume_base:
                self._sync_to_volume(entry, volume_base)
            else:
                logger.warning("AGENT_SESSIONS_VOLUME_PATH not set — skipping file sync on eviction")
        elif not purge and not self._ws_client:
            logger.warning("No WorkspaceClient set — skipping file sync on eviction")

        # Always delete local session dir
        try:
            shutil.rmtree(entry.session_dir, ignore_errors=True)
        except Exception as exc:
            logger.warning("Failed to clean session dir %s: %s", entry.session_dir, exc)
        logger.info("AgentPool: evicted %s", conversation_id)

    def evict_stale(self, ttl_minutes: int) -> None:
        """Remove all entries that have been idle longer than ttl_minutes."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
        with self._lock:
            stale_keys = [
                k for k, entry in self._pool.items()
                if entry.last_accessed < cutoff
            ]
        for key in stale_keys:
            self.evict(key)
        if stale_keys:
            logger.info("AgentPool: evicted %d stale entries", len(stale_keys))

    async def shutdown(self) -> None:
        """Close all agents and clear the pool (called on app shutdown)."""
        with self._lock:
            entries = list(self._pool.items())
            self._pool.clear()
        for conversation_id, entry in entries:
            try:
                entry.agent.close()
            except Exception as exc:
                logger.warning("AgentPool: close() error on shutdown for %s: %s", conversation_id, exc)
            try:
                shutil.rmtree(entry.session_dir, ignore_errors=True)
            except Exception as exc:
                logger.warning("Failed to clean session dir %s: %s", entry.session_dir, exc)
        logger.info("AgentPool: shutdown complete")


# Singleton pool instance
_pool_instance: AgentPool | None = None


def get_pool() -> AgentPool:
    """Return the singleton AgentPool, creating it if needed."""
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = AgentPool()
    return _pool_instance
