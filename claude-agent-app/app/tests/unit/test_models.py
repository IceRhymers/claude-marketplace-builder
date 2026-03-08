"""Tests for core/models.py — SQLAlchemy model validation.

Written BEFORE implementation (RED phase).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def memory_engine():
    """Create a fresh in-memory SQLite engine for each test."""
    from core.models import Base
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(memory_engine):
    """Yield a session bound to the in-memory engine."""
    Session = sessionmaker(bind=memory_engine)
    s = Session()
    yield s
    s.close()


class TestConversationModel:
    def test_conversation_table_exists(self, memory_engine):
        insp = inspect(memory_engine)
        assert "conversations" in insp.get_table_names()

    def test_conversation_columns(self, memory_engine):
        insp = inspect(memory_engine)
        cols = {c["name"] for c in insp.get_columns("conversations")}
        assert "id" in cols
        assert "user_id" in cols
        assert "title" in cols
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_insert_conversation(self, session):
        from core.models import Conversation
        conv = Conversation(
            id=str(uuid.uuid4()),
            user_id="alice@example.com",
            title="Test Conv",
        )
        session.add(conv)
        session.commit()

        result = session.query(Conversation).filter_by(user_id="alice@example.com").first()
        assert result is not None
        assert result.user_id == "alice@example.com"
        assert result.title == "Test Conv"

    def test_conversation_title_nullable(self, session):
        from core.models import Conversation
        conv = Conversation(
            id=str(uuid.uuid4()),
            user_id="alice@example.com",
            title=None,
        )
        session.add(conv)
        session.commit()
        result = session.query(Conversation).first()
        assert result.title is None

    def test_user_id_filter_isolates_users(self, session):
        from core.models import Conversation
        alice_conv = Conversation(id=str(uuid.uuid4()), user_id="alice@example.com", title="Alice's")
        bob_conv = Conversation(id=str(uuid.uuid4()), user_id="bob@example.com", title="Bob's")
        session.add_all([alice_conv, bob_conv])
        session.commit()

        alice_results = session.query(Conversation).filter_by(user_id="alice@example.com").all()
        assert len(alice_results) == 1
        assert alice_results[0].title == "Alice's"


class TestMessageModel:
    def test_messages_table_exists(self, memory_engine):
        insp = inspect(memory_engine)
        assert "messages" in insp.get_table_names()

    def test_messages_columns(self, memory_engine):
        insp = inspect(memory_engine)
        cols = {c["name"] for c in insp.get_columns("messages")}
        assert "id" in cols
        assert "conversation_id" in cols
        assert "user_id" in cols
        assert "role" in cols
        assert "content" in cols
        assert "created_at" in cols

    def test_insert_message(self, session):
        from core.models import Conversation, Message
        conv = Conversation(id=str(uuid.uuid4()), user_id="alice@example.com")
        session.add(conv)
        session.flush()

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            user_id="alice@example.com",
            role="user",
            content="Hello!",
        )
        session.add(msg)
        session.commit()

        result = session.query(Message).filter_by(conversation_id=conv.id).first()
        assert result is not None
        assert result.role == "user"
        assert result.content == "Hello!"

    def test_messages_cascade_delete(self, session):
        from core.models import Conversation, Message
        conv = Conversation(id=str(uuid.uuid4()), user_id="alice@example.com")
        session.add(conv)
        session.flush()

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            user_id="alice@example.com",
            role="assistant",
            content="Hi there",
        )
        session.add(msg)
        session.commit()

        session.delete(conv)
        session.commit()

        msgs = session.query(Message).filter_by(conversation_id=conv.id).all()
        assert len(msgs) == 0

    def test_message_lookup_for_non_owner_returns_empty(self, session):
        from core.models import Conversation, Message
        conv = Conversation(id=str(uuid.uuid4()), user_id="alice@example.com")
        session.add(conv)
        session.flush()

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            user_id="alice@example.com",
            role="user",
            content="Alice's message",
        )
        session.add(msg)
        session.commit()

        # Bob tries to get Alice's messages by filtering on bob's user_id
        bob_convs = session.query(Conversation).filter_by(user_id="bob@example.com").all()
        bob_conv_ids = [c.id for c in bob_convs]
        bob_msgs = session.query(Message).filter(
            Message.conversation_id.in_(bob_conv_ids)
        ).all()
        assert len(bob_msgs) == 0
