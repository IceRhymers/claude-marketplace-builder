"""In-process AgentPool — keyed by conversation_id with TTL eviction."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from core.skills import SkillsConfig, substitute_token

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class AgentEntry:
    """A pool entry holding an agent and its last-access metadata."""
    agent: Any
    last_accessed: datetime
    user_id: str


def build_agent(system_prompt: str, mcp_config: dict) -> Any:
    """Construct a Claude agent with the given system prompt and MCP config.

    This is a module-level function so tests can easily patch it.
    In production, this would use the Claude Agent SDK.
    """
    # Import here to avoid import errors when SDK is unavailable in tests
    try:
        import anthropic
        client = anthropic.Anthropic()

        class SimpleAgent:
            """Minimal agent wrapper for streaming responses."""
            def __init__(self, client, system_prompt, mcp_config):
                self._client = client
                self._system_prompt = system_prompt
                self._mcp_config = mcp_config
                self._history: list[dict] = []

            async def stream(self, message: str):
                """Stream a response, yielding event dicts."""
                self._history.append({"role": "user", "content": message})
                # Use the Messages API for streaming
                try:
                    with self._client.messages.stream(
                        model="claude-sonnet-4-5",
                        max_tokens=4096,
                        system=self._system_prompt,
                        messages=self._history,
                    ) as stream:
                        full_text = ""
                        for text in stream.text_stream:
                            full_text += text
                            yield {"type": "text_delta", "text": text}
                        self._history.append({"role": "assistant", "content": full_text})
                except Exception as exc:
                    logger.error("Agent stream error: %s", exc)
                    raise
                yield {"type": "done"}

            def close(self):
                pass

        return SimpleAgent(client, system_prompt, mcp_config)
    except ImportError:
        logger.warning("anthropic SDK not available — returning stub agent")

        class StubAgent:
            async def stream(self, message: str):
                yield {"type": "text_delta", "text": "Agent SDK not configured."}
                yield {"type": "done"}

            def close(self):
                pass

        return StubAgent()


class AgentPool:
    """In-memory pool of agents, keyed by conversation_id."""

    def __init__(self):
        self._pool: dict[str, AgentEntry] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        conversation_id: str,
        user_id: str,
        access_token: str,
        skills_config: SkillsConfig,
    ) -> Any:
        """Return an existing agent or spawn a new one.

        Args:
            conversation_id: Key for pool lookup.
            user_id: Owner of this conversation.
            access_token: User's OAuth token for MCP connections.
            skills_config: Current loaded skills/MCP configuration.

        Returns:
            Agent instance.

        Raises:
            RuntimeError: If agent initialization fails (MCP connection error, etc.).
        """
        async with self._lock:
            if conversation_id in self._pool:
                entry = self._pool[conversation_id]
                entry.last_accessed = datetime.now(timezone.utc)
                logger.debug("AgentPool: reusing agent for %s", conversation_id)
                return entry.agent

            # Build system prompt from skills
            system_prompt = "\n\n".join(skills_config.skill_contents) or "You are a helpful assistant."

            # Substitute user token into MCP config
            mcp_config = substitute_token(skills_config.mcp_config, access_token)

            try:
                agent = build_agent(system_prompt=system_prompt, mcp_config=mcp_config)
            except Exception as exc:
                logger.error("AgentPool: failed to build agent for %s: %s", conversation_id, exc)
                raise RuntimeError(f"Agent initialization failed: {exc}") from exc

            self._pool[conversation_id] = AgentEntry(
                agent=agent,
                last_accessed=datetime.now(timezone.utc),
                user_id=user_id,
            )
            logger.info("AgentPool: spawned new agent for conversation %s (user=%s)", conversation_id, user_id)
            return agent

    def evict(self, conversation_id: str) -> None:
        """Remove a single conversation from the pool."""
        entry = self._pool.pop(conversation_id, None)
        if entry is not None:
            try:
                entry.agent.close()
            except Exception as exc:
                logger.warning("AgentPool: close() error during evict: %s", exc)
            logger.info("AgentPool: evicted %s", conversation_id)

    def evict_stale(self, ttl_minutes: int) -> None:
        """Remove all entries that have been idle longer than ttl_minutes."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
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
        async with self._lock:
            for conversation_id, entry in list(self._pool.items()):
                try:
                    entry.agent.close()
                except Exception as exc:
                    logger.warning("AgentPool: close() error on shutdown for %s: %s", conversation_id, exc)
            self._pool.clear()
            logger.info("AgentPool: shutdown complete")


# Singleton pool instance
_pool_instance: AgentPool | None = None


def get_pool() -> AgentPool:
    """Return the singleton AgentPool, creating it if needed."""
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = AgentPool()
    return _pool_instance
