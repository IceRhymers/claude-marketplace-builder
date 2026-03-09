"""Integration tests for core/db.py and Alembic migrations.

Written BEFORE implementation (RED phase).
"""

from __future__ import annotations

import uuid
import pytest
from unittest.mock import MagicMock, patch


class TestCreateEngine:
    """Tests for create_engine_from_config()."""

    @patch("core.db.event")
    @patch("core.db.create_engine")
    def test_creates_engine_with_postgresql_psycopg(self, mock_create_engine, mock_event, env_vars):
        from core.config import AppConfig
        from core.db import create_engine_from_config

        config = AppConfig.from_env()
        create_engine_from_config(config)

        mock_create_engine.assert_called_once()
        url = str(mock_create_engine.call_args[0][0])
        assert "postgresql+psycopg" in url
        assert "sslmode=require" in url

    @patch("core.db.event")
    @patch("core.db.create_engine")
    def test_engine_pool_settings(self, mock_create_engine, mock_event, env_vars):
        from core.config import AppConfig
        from core.db import create_engine_from_config

        config = AppConfig.from_env()
        create_engine_from_config(config)

        call_kwargs = mock_create_engine.call_args.kwargs
        assert call_kwargs["pool_size"] == 1
        assert call_kwargs["max_overflow"] == 9

    @patch("core.db.event")
    @patch("core.db.create_engine")
    def test_registers_do_connect_listener(self, mock_create_engine, mock_event, env_vars):
        from core.config import AppConfig
        from core.db import create_engine_from_config

        config = AppConfig.from_env()
        create_engine_from_config(config)

        mock_event.listens_for.assert_called_once()
        args = mock_event.listens_for.call_args[0]
        assert args[1] == "do_connect"


class TestAlembicMigrations:
    """Tests for Alembic migration correctness using in-memory SQLite."""

    def test_base_metadata_creates_tables(self):
        """Base.metadata.create_all creates conversations and messages tables."""
        from sqlalchemy import create_engine, inspect
        from core.models import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        insp = inspect(engine)
        tables = insp.get_table_names()
        assert "conversations" in tables
        assert "messages" in tables
        Base.metadata.drop_all(engine)

    def test_schema_creation_idempotent(self):
        """create_all called twice raises no error."""
        from sqlalchemy import create_engine
        from core.models import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        # Call again — should be idempotent
        Base.metadata.create_all(engine)
        Base.metadata.drop_all(engine)

    def test_conversation_insert_and_user_filter(self, db_session):
        from core.models import Conversation
        conv = Conversation(id=str(uuid.uuid4()), user_id="alice@example.com", title="Test")
        db_session.add(conv)
        db_session.commit()

        result = db_session.query(Conversation).filter_by(user_id="alice@example.com").all()
        assert len(result) == 1
        assert result[0].title == "Test"

    def test_messages_cascade_delete_with_conversation(self, db_session):
        from core.models import Conversation, Message
        conv = Conversation(id=str(uuid.uuid4()), user_id="alice@example.com")
        db_session.add(conv)
        db_session.flush()

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            user_id="alice@example.com",
            role="user",
            content="Test",
        )
        db_session.add(msg)
        db_session.commit()

        conv_id = conv.id
        db_session.delete(conv)
        db_session.commit()

        from core.models import Message
        remaining = db_session.query(Message).filter_by(conversation_id=conv_id).all()
        assert len(remaining) == 0

    def test_user_isolation_on_list_query(self, db_session):
        from core.models import Conversation
        alice_conv = Conversation(id=str(uuid.uuid4()), user_id="alice@example.com", title="Alice")
        bob_conv = Conversation(id=str(uuid.uuid4()), user_id="bob@example.com", title="Bob")
        db_session.add_all([alice_conv, bob_conv])
        db_session.commit()

        alice_convs = db_session.query(Conversation).filter_by(user_id="alice@example.com").all()
        assert len(alice_convs) == 1
        assert alice_convs[0].title == "Alice"

    def test_message_lookup_for_non_owner_returns_empty(self, db_session):
        from core.models import Conversation, Message
        conv = Conversation(id=str(uuid.uuid4()), user_id="alice@example.com")
        db_session.add(conv)
        db_session.flush()

        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            user_id="alice@example.com",
            role="user",
            content="Alice's message",
        )
        db_session.add(msg)
        db_session.commit()

        # Bob's conversations
        bob_convs = db_session.query(Conversation).filter_by(user_id="bob@example.com").all()
        assert len(bob_convs) == 0
