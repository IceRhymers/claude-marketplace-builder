"""Tests for routers/conversations.py and routers/me.py.

Written BEFORE implementation (RED phase).
"""

from __future__ import annotations

import uuid
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def make_sqlite_setup():
    """Create a StaticPool SQLite in-memory engine + session factory."""
    from core.models import Base
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


class TestPostConversations:
    @patch("core.auth.WorkspaceClient")
    def test_post_conversations_returns_201(self, mock_wsc_class):
        """POST /api/conversations with valid token → 201 with conversation_id."""
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "test@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        from fastapi import FastAPI
        from routers.conversations import router as conv_router
        from deps import get_db

        engine, SessionLocal = make_sqlite_setup()

        app = FastAPI()
        app.include_router(conv_router)

        def override_get_db():
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.post(
                "/api/conversations",
                headers={"X-Forwarded-Access-Token": "valid-token"}
            )
            assert resp.status_code == 201
            data = resp.json()
            assert "conversation_id" in data
            assert "created_at" in data

    def test_post_conversations_without_token_returns_401(self):
        """POST /api/conversations without token → 401."""
        from fastapi import FastAPI
        from routers.conversations import router as conv_router
        from deps import get_db

        engine, SessionLocal = make_sqlite_setup()

        app = FastAPI()
        app.include_router(conv_router)

        def override_get_db():
            session = SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/api/conversations")
            assert resp.status_code == 401


class TestGetConversations:
    @patch("core.auth.WorkspaceClient")
    def test_get_conversations_returns_only_callers(self, mock_wsc_class):
        """GET /api/conversations returns only authenticated user's conversations."""
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        from fastapi import FastAPI
        from core.models import Conversation
        from routers.conversations import router as conv_router
        from deps import get_db

        engine, SessionLocal = make_sqlite_setup()

        # Pre-seed data
        session = SessionLocal()
        alice_conv = Conversation(id=str(uuid.uuid4()), user_id="alice@example.com", title="Alice's")
        bob_conv = Conversation(id=str(uuid.uuid4()), user_id="bob@example.com", title="Bob's")
        session.add_all([alice_conv, bob_conv])
        session.commit()
        session.close()

        app = FastAPI()
        app.include_router(conv_router)

        def override_get_db():
            s = SessionLocal()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get(
                "/api/conversations",
                headers={"X-Forwarded-Access-Token": "alice-token"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert all(c["user_id"] == "alice@example.com" for c in data)
            assert len(data) == 1


class TestGetMessages:
    @patch("core.auth.WorkspaceClient")
    def test_get_messages_non_owner_returns_404(self, mock_wsc_class):
        """GET /api/conversations/{id}/messages with non-owner → 404."""
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "bob@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        from fastapi import FastAPI
        from core.models import Conversation
        from routers.conversations import router as conv_router
        from deps import get_db

        engine, SessionLocal = make_sqlite_setup()

        # Alice owns the conv
        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        app = FastAPI()
        app.include_router(conv_router)

        def override_get_db():
            s = SessionLocal()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                f"/api/conversations/{conv_id}/messages",
                headers={"X-Forwarded-Access-Token": "bob-token"}
            )
            assert resp.status_code == 404


class TestDeleteConversation:
    @patch("core.auth.WorkspaceClient")
    def test_delete_owned_conversation_returns_204(self, mock_wsc_class):
        """DELETE /api/conversations/{id} owned → 204 and agent evicted."""
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        from fastapi import FastAPI
        from core.models import Conversation
        from routers.conversations import router as conv_router
        from deps import get_db, get_agent_pool

        engine, SessionLocal = make_sqlite_setup()

        # Pre-seed
        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com", title="Alice's")
        session.add(conv)
        session.commit()
        session.close()

        app = FastAPI()
        app.include_router(conv_router)

        mock_pool = MagicMock()

        def override_get_db():
            s = SessionLocal()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_agent_pool] = lambda: mock_pool

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "alice-token"}
            )
            assert resp.status_code == 204
            mock_pool.evict.assert_called_once_with(conv_id, purge=True)

    @patch("core.auth.WorkspaceClient")
    def test_delete_non_owned_returns_404(self, mock_wsc_class):
        """DELETE /api/conversations/{id} non-owned → 404."""
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "bob@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        from fastapi import FastAPI
        from core.models import Conversation
        from routers.conversations import router as conv_router
        from deps import get_db, get_agent_pool

        engine, SessionLocal = make_sqlite_setup()

        # Alice owns the conversation
        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        app = FastAPI()
        app.include_router(conv_router)

        def override_get_db():
            s = SessionLocal()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_agent_pool] = lambda: MagicMock()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "bob-token"}
            )
            assert resp.status_code == 404
