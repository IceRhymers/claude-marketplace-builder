"""Conversation TTL cleanup — daily purge of stale conversations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


def purge_stale_conversations(
    session_factory: Callable,
    pool: Any,
    workspace_client: Any,
    ttl_days: int,
    volume_base: str,
) -> None:
    """Find and purge conversations older than ttl_days.

    Per-conversation failure isolation: one failure does not stop others.

    Args:
        session_factory: Callable that returns a new SQLAlchemy Session.
        pool: AgentPool instance.
        workspace_client: Databricks WorkspaceClient for Volume operations.
        ttl_days: Number of days of inactivity before a conversation is stale.
        volume_base: Base Volume path (AGENT_SESSIONS_VOLUME_PATH). Empty = skip.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    session = session_factory()
    purged_count = 0

    try:
        from core.models import Conversation
        stale = session.query(Conversation).filter(Conversation.updated_at < cutoff).all()

        for conv in stale:
            try:
                # Evict from pool (purge=True skips Volume sync)
                pool.evict(conv.id, purge=True)

                # Delete Volume path (non-fatal)
                if volume_base:
                    volume_path = f"{volume_base}/{conv.user_id}/{conv.id}"
                    try:
                        workspace_client.files.delete(volume_path)
                    except Exception as exc:
                        logger.warning(
                            "TTL cleanup Volume delete failed for %s: %s", conv.id, exc
                        )

                # Delete DB row (cascade removes messages)
                session.delete(conv)
                session.commit()
                purged_count += 1
                logger.info(
                    "TTL cleanup: purged conversation %s (user=%s)", conv.id, conv.user_id
                )

            except Exception as exc:
                logger.error(
                    "TTL cleanup failed for conversation %s: %s", conv.id, exc
                )
                session.rollback()

        logger.info("TTL cleanup: purged %d stale conversation(s)", purged_count)

    finally:
        session.close()
