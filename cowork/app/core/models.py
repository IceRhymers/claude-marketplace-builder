"""SQLAlchemy models for conversations and messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now_utc():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    """A conversation session owned by a single user."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, onupdate=_now_utc
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class Message(Base):
    """A single message in a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_message_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )


class UserSkillPref(Base):
    """Per-user skill enable/disable preference."""

    __tablename__ = "user_skill_prefs"

    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    skill_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, onupdate=_now_utc
    )


class UserMcpPref(Base):
    """Per-user MCP server enable/disable preference."""

    __tablename__ = "user_mcp_prefs"

    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    mcp_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, onupdate=_now_utc
    )
