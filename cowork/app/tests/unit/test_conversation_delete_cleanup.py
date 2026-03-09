"""Tests for DELETE /api/conversations/{id} cleanup behavior.

Written BEFORE implementation (RED phase) per TDD requirement.
"""

from __future__ import annotations

import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


VOLUME_BASE = "/Volumes/catalog/schema/agent-sessions"


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


def make_app_with_overrides(SessionLocal, mock_pool, mock_ws_client=None):
    """Helper to build a FastAPI test app with dependency overrides."""
    from routers.conversations import router as conv_router
    from deps import get_db, get_agent_pool

    app = FastAPI()
    app.include_router(conv_router)

    def override_get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_agent_pool] = lambda: mock_pool

    return app


class TestDeleteConversationEvictsWithPurge:
    @patch("core.auth.WorkspaceClient")
    def test_delete_evicts_from_pool_with_purge_true(self, mock_wsc_class, monkeypatch):
        """DELETE owned conversation → pool.evict(conv_id, purge=True) called."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_client.files.delete = MagicMock()
        mock_wsc_class.return_value = mock_client

        from core.models import Conversation

        engine, SessionLocal = make_sqlite_setup()

        # Pre-seed conversation
        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com", title="Test")
        session.add(conv)
        session.commit()
        session.close()

        mock_pool = MagicMock()
        app = make_app_with_overrides(SessionLocal, mock_pool, mock_client)

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "alice-token"}
            )

        assert resp.status_code == 204
        mock_pool.evict.assert_called_once_with(conv_id, purge=True)

    @patch("core.auth.WorkspaceClient")
    def test_delete_not_purge_false(self, mock_wsc_class, monkeypatch):
        """DELETE must call evict with purge=True, not purge=False."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_client.files.delete = MagicMock()
        mock_wsc_class.return_value = mock_client

        from core.models import Conversation

        engine, SessionLocal = make_sqlite_setup()

        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        mock_pool = MagicMock()
        app = make_app_with_overrides(SessionLocal, mock_pool, mock_client)

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "alice-token"}
            )

        assert resp.status_code == 204
        # Confirm it was called with purge=True explicitly
        call_args = mock_pool.evict.call_args
        assert call_args.kwargs.get("purge", call_args.args[1] if len(call_args.args) > 1 else None) is True


class TestDeleteConversationVolumePath:
    @patch("routers.conversations.WorkspaceClient")
    @patch("core.auth.WorkspaceClient")
    def test_delete_removes_volume_path(self, mock_auth_wsc, mock_conv_wsc, monkeypatch):
        """DELETE → ws.files.delete called with correct Volume path."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        # Auth mock
        mock_auth_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_auth_client.current_user.me.return_value = mock_user
        mock_auth_wsc.return_value = mock_auth_client

        # Volume operations mock
        mock_vol_client = MagicMock()
        mock_vol_client.files.delete = MagicMock()
        mock_conv_wsc.return_value = mock_vol_client

        from core.models import Conversation

        engine, SessionLocal = make_sqlite_setup()

        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        mock_pool = MagicMock()
        app = make_app_with_overrides(SessionLocal, mock_pool)

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "alice-token"}
            )

        assert resp.status_code == 204
        expected_path = f"{VOLUME_BASE}/alice@example.com/{conv_id}"
        mock_vol_client.files.delete.assert_called_once()
        actual_path = mock_vol_client.files.delete.call_args[0][0]
        assert actual_path == expected_path

    @patch("routers.conversations.WorkspaceClient")
    @patch("core.auth.WorkspaceClient")
    def test_delete_volume_failure_is_nonfatal(self, mock_auth_wsc, mock_conv_wsc, monkeypatch):
        """files.delete raises → WARNING logged; 204 still returned; DB row deleted."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        mock_auth_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_auth_client.current_user.me.return_value = mock_user
        mock_auth_wsc.return_value = mock_auth_client

        mock_vol_client = MagicMock()
        mock_vol_client.files.delete = MagicMock(side_effect=Exception("Volume error"))
        mock_conv_wsc.return_value = mock_vol_client

        from core.models import Conversation

        engine, SessionLocal = make_sqlite_setup()

        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        mock_pool = MagicMock()
        app = make_app_with_overrides(SessionLocal, mock_pool)

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "alice-token"}
            )

        assert resp.status_code == 204

        # DB row should be gone
        check_session = SessionLocal()
        result = check_session.query(Conversation).filter(Conversation.id == conv_id).first()
        check_session.close()
        assert result is None

    @patch("routers.conversations.WorkspaceClient")
    @patch("core.auth.WorkspaceClient")
    def test_delete_skips_volume_delete_when_path_not_set(self, mock_auth_wsc, mock_conv_wsc, monkeypatch):
        """AGENT_SESSIONS_VOLUME_PATH unset → no files.delete; 204 returned; DB row gone."""
        monkeypatch.delenv("AGENT_SESSIONS_VOLUME_PATH", raising=False)

        mock_auth_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_auth_client.current_user.me.return_value = mock_user
        mock_auth_wsc.return_value = mock_auth_client

        mock_vol_client = MagicMock()
        mock_vol_client.files.delete = MagicMock()
        mock_conv_wsc.return_value = mock_vol_client

        from core.models import Conversation

        engine, SessionLocal = make_sqlite_setup()

        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        mock_pool = MagicMock()
        app = make_app_with_overrides(SessionLocal, mock_pool)

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "alice-token"}
            )

        assert resp.status_code == 204
        mock_vol_client.files.delete.assert_not_called()


class TestDeleteConversationDBRows:
    @patch("core.auth.WorkspaceClient")
    def test_delete_removes_db_row(self, mock_wsc_class, monkeypatch):
        """DELETE → conversation row gone from DB after delete."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_client.files.delete = MagicMock()
        mock_wsc_class.return_value = mock_client

        from core.models import Conversation

        engine, SessionLocal = make_sqlite_setup()

        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        mock_pool = MagicMock()
        app = make_app_with_overrides(SessionLocal, mock_pool, mock_client)

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "alice-token"}
            )

        assert resp.status_code == 204

        check_session = SessionLocal()
        result = check_session.query(Conversation).filter(Conversation.id == conv_id).first()
        check_session.close()
        assert result is None


class TestDeleteConversationOwnership:
    @patch("core.auth.WorkspaceClient")
    def test_delete_returns_404_for_other_user_conversation(self, mock_wsc_class, monkeypatch):
        """DELETE non-owned conversation → 404; no evict, no files.delete, no DB delete."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "bob@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_client.files.delete = MagicMock()
        mock_wsc_class.return_value = mock_client

        from core.models import Conversation

        engine, SessionLocal = make_sqlite_setup()

        # Alice owns the conversation
        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        mock_pool = MagicMock()
        app = make_app_with_overrides(SessionLocal, mock_pool, mock_client)

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "bob-token"}
            )

        assert resp.status_code == 404
        mock_pool.evict.assert_not_called()
        mock_client.files.delete.assert_not_called()

        # DB row must still exist
        check_session = SessionLocal()
        result = check_session.query(Conversation).filter(Conversation.id == conv_id).first()
        check_session.close()
        assert result is not None

    @patch("routers.conversations.WorkspaceClient")
    @patch("core.auth.WorkspaceClient")
    def test_delete_conversation_not_in_pool_still_cleans_volume(self, mock_auth_wsc, mock_conv_wsc, monkeypatch):
        """Conversation not in pool → evict is no-op; Volume delete still attempted; 204."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        mock_auth_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_auth_client.current_user.me.return_value = mock_user
        mock_auth_wsc.return_value = mock_auth_client

        mock_vol_client = MagicMock()
        mock_vol_client.files.delete = MagicMock()
        mock_conv_wsc.return_value = mock_vol_client

        from core.models import Conversation

        engine, SessionLocal = make_sqlite_setup()

        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        # Pool where evict is a no-op (conv not in pool)
        mock_pool = MagicMock()

        app = make_app_with_overrides(SessionLocal, mock_pool)

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.delete(
                f"/api/conversations/{conv_id}",
                headers={"X-Forwarded-Access-Token": "alice-token"}
            )

        assert resp.status_code == 204
        # evict is called (even if it's a no-op inside)
        mock_pool.evict.assert_called_once()
        # Volume delete is still attempted
        mock_vol_client.files.delete.assert_called_once()
