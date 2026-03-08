"""SSE streaming endpoint for claude agent chat."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from core.auth import CurrentUser, get_current_user
from core.models import Conversation, Message
from core.agent_pool import AgentPool
from core.skills import SkillsConfig
from deps import get_db, get_agent_pool, get_skills_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/conversations/{conversation_id}/stream")
async def stream_conversation(
    conversation_id: str,
    message: str = Query(..., description="User message to send to the agent"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    pool: AgentPool = Depends(get_agent_pool),
    skills_config: SkillsConfig = Depends(get_skills_config),
):
    """Stream an agent response as Server-Sent Events.

    Validates conversation ownership, retrieves or creates an agent,
    streams response events, and persists messages on completion.
    """
    # Verify ownership
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.user_id,
    ).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def event_generator():
        full_text = ""
        completed = False
        try:
            agent = await pool.get_or_create(
                conversation_id=conversation_id,
                user_id=current_user.user_id,
                access_token=current_user.access_token,
                skills_config=skills_config,
            )

            # Stream events from agent
            async for event in agent.stream(message):
                event_type = event.get("type", "")
                if event_type == "text_delta":
                    full_text += event.get("text", "")
                    yield {"data": json.dumps(event)}
                elif event_type in ("tool_use", "tool_result"):
                    yield {"data": json.dumps(event)}
                elif event_type == "done":
                    # Persist messages atomically
                    try:
                        user_msg = Message(
                            id=str(uuid.uuid4()),
                            conversation_id=conversation_id,
                            user_id=current_user.user_id,
                            role="user",
                            content=message,
                        )
                        assistant_msg = Message(
                            id=str(uuid.uuid4()),
                            conversation_id=conversation_id,
                            user_id=current_user.user_id,
                            role="assistant",
                            content=full_text,
                        )
                        # Update conversation title from first message if not set
                        if conv.title is None and message:
                            conv.title = message[:80] + ("..." if len(message) > 80 else "")
                        db.add(user_msg)
                        db.add(assistant_msg)
                        db.commit()
                        completed = True
                    except Exception as exc:
                        logger.error("Failed to persist messages: %s", exc)
                        db.rollback()

                    done_event = {"type": "done", "message_id": assistant_msg.id if completed else None}
                    yield {"data": json.dumps(done_event)}
                    return

        except Exception as exc:
            logger.error("Stream error for conversation %s: %s", conversation_id, exc)
            yield {"data": json.dumps({"type": "error", "detail": str(exc)})}

    return EventSourceResponse(event_generator())


@router.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}
