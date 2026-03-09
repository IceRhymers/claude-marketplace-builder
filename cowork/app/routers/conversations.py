"""Conversation CRUD endpoints."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.auth import CurrentUser, get_current_user, WorkspaceClient
from core.models import Conversation, Message
from core.agent_pool import AgentPool
from deps import get_db, get_agent_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/conversations", status_code=201)
def create_conversation(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new conversation for the authenticated user."""
    conv = Conversation(
        id=str(uuid.uuid4()),
        user_id=current_user.user_id,
        title=None,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {
        "conversation_id": conv.id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


@router.get("/conversations")
def list_conversations(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all conversations for the authenticated user, newest first."""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [
        {
            "conversation_id": c.id,
            "user_id": c.user_id,
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convs
    ]


@router.get("/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return message history for a conversation (owner-only)."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.user_id,
    ).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    pool: AgentPool = Depends(get_agent_pool),
):
    """Delete a conversation and all messages (owner-only).

    Deletion order:
    1. Evict agent from pool with purge=True (skips Volume sync)
    2. Delete Volume path (non-fatal on failure)
    3. Delete DB row (cascade removes messages)
    4. Return 204 No Content
    """
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.user_id,
    ).first()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Step 1: Evict from pool (purge=True skips Volume sync — no point syncing files about to be deleted)
    pool.evict(conversation_id, purge=True)

    # Step 2: Delete Volume files (non-fatal)
    volume_base = os.environ.get("AGENT_SESSIONS_VOLUME_PATH", "")
    if volume_base:
        try:
            ws = WorkspaceClient()
            volume_path = f"{volume_base}/{current_user.user_id}/{conversation_id}"
            ws.files.delete(volume_path)
        except Exception as exc:
            logger.warning("Volume delete failed for conversation %s (non-fatal): %s", conversation_id, exc)

    # Step 3: Delete DB row (cascade removes messages)
    db.delete(conv)
    db.commit()

    return Response(status_code=204)
