"""Tests for deps.py — FastAPI dependency injection."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException


@pytest.mark.unit
class TestGetConfig:
    def test_returns_config_from_app_state(self):
        from deps import get_config

        mock_request = MagicMock()
        mock_request.app.state.config = MagicMock(sql_warehouse_id="test-wh")

        result = get_config(mock_request)
        assert result.sql_warehouse_id == "test-wh"


@pytest.mark.unit
class TestGetClient:
    def test_returns_client_from_app_state(self):
        from deps import get_client

        mock_request = MagicMock()
        mock_request.app.state.client = MagicMock()

        result = get_client(mock_request)
        assert result is mock_request.app.state.client


@pytest.mark.unit
class TestGetDb:
    def test_yields_session_and_closes(self):
        from deps import get_db

        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_request.app.state.session_factory.return_value = mock_session

        gen = get_db(mock_request)
        session = next(gen)
        assert session is mock_session

        # Exhaust the generator
        try:
            next(gen)
        except StopIteration:
            pass

        mock_session.close.assert_called_once()

    def test_closes_session_on_exception(self):
        from deps import get_db

        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_request.app.state.session_factory.return_value = mock_session

        gen = get_db(mock_request)
        next(gen)

        # Simulate an exception
        try:
            gen.throw(ValueError("test error"))
        except ValueError:
            pass

        mock_session.close.assert_called_once()


@pytest.mark.unit
class TestGetCurrentUser:
    @patch("deps.resolve_user_identity")
    def test_returns_identity_with_valid_token(self, mock_resolve):
        from deps import get_current_user
        from core.auth import UserIdentity

        identity = UserIdentity(
            email="user@example.com",
            display_name="Test User",
            groups=["users"],
            is_admin=False,
        )
        mock_resolve.return_value = identity

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "valid-token"
        mock_request.app.state.config.admin_groups = []

        result = get_current_user(mock_request)
        assert result.email == "user@example.com"
        mock_resolve.assert_called_once_with("valid-token", [])

    def test_missing_token_raises_401(self):
        from deps import get_current_user

        mock_request = MagicMock()
        mock_request.headers.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(mock_request)
        assert exc_info.value.status_code == 401

    @patch("deps.resolve_user_identity")
    def test_invalid_token_raises_401(self, mock_resolve):
        from deps import get_current_user

        mock_resolve.side_effect = Exception("Bad token")

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "bad-token"
        mock_request.app.state.config.admin_groups = []

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(mock_request)
        assert exc_info.value.status_code == 401


@pytest.mark.unit
class TestRequireAdmin:
    def test_admin_user_passes_through(self):
        from deps import require_admin
        from core.auth import UserIdentity

        admin = UserIdentity(
            email="admin@example.com",
            display_name="Admin",
            groups=["admins"],
            is_admin=True,
        )
        result = require_admin(admin)
        assert result is admin

    def test_non_admin_raises_403(self):
        from deps import require_admin
        from core.auth import UserIdentity

        user = UserIdentity(
            email="user@example.com",
            display_name="User",
            groups=["users"],
            is_admin=False,
        )
        with pytest.raises(HTTPException) as exc_info:
            require_admin(user)
        assert exc_info.value.status_code == 403
