"""Tests for core/auth.py — User identity resolution via X-Forwarded-Access-Token.

These tests are written BEFORE the implementation (RED phase).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
import httpx


# ---------------------------------------------------------------------------
# Tests for CurrentUser dataclass
# ---------------------------------------------------------------------------

class TestCurrentUser:
    def test_current_user_has_user_id_and_access_token(self):
        from core.auth import CurrentUser
        user = CurrentUser(user_id="alice@example.com", access_token="valid-token")
        assert user.user_id == "alice@example.com"
        assert user.access_token == "valid-token"

    def test_current_user_is_dataclass(self):
        from core.auth import CurrentUser
        import dataclasses
        assert dataclasses.is_dataclass(CurrentUser)


# ---------------------------------------------------------------------------
# Tests for get_current_user dependency
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    @patch("core.auth.WorkspaceClient")
    def test_valid_token_resolves_user(self, mock_wsc_class):
        """Valid X-Forwarded-Access-Token resolves to CurrentUser with user_id."""
        from core.auth import get_current_user, CurrentUser

        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        from fastapi import Request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"x-forwarded-access-token": "valid-token"}

        result = get_current_user(x_forwarded_access_token="valid-token")

        assert isinstance(result, CurrentUser)
        assert result.user_id == "alice@example.com"
        assert result.access_token == "valid-token"

    def test_missing_token_raises_401(self):
        """Missing X-Forwarded-Access-Token header raises HTTPException 401."""
        from core.auth import get_current_user
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(x_forwarded_access_token=None)

        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail

    @patch("core.auth.WorkspaceClient")
    def test_invalid_token_raises_401(self, mock_wsc_class):
        """Invalid/expired token causes SDK exception, returns 401."""
        from core.auth import get_current_user
        from fastapi import HTTPException

        mock_client = MagicMock()
        mock_client.current_user.me.side_effect = Exception("PermissionDenied")
        mock_wsc_class.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(x_forwarded_access_token="bad-token")

        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail

    @patch("core.auth.WorkspaceClient")
    def test_dependency_injects_into_route(self, mock_wsc_class):
        """Route with Depends(get_current_user) receives populated CurrentUser."""
        from core.auth import get_current_user, CurrentUser

        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        app = FastAPI()
        received = {}

        @app.get("/test")
        def test_route(current_user: CurrentUser = Depends(get_current_user)):
            received["user"] = current_user
            return {"user_id": current_user.user_id}

        with TestClient(app) as client:
            resp = client.get("/test", headers={"X-Forwarded-Access-Token": "valid-token"})
            assert resp.status_code == 200
            assert resp.json()["user_id"] == "alice@example.com"

    def test_dependency_without_token_returns_401(self):
        """Route called without token returns 401 and handler body not executed."""
        from core.auth import get_current_user, CurrentUser

        app = FastAPI()
        executed = []

        @app.get("/test")
        def test_route(current_user: CurrentUser = Depends(get_current_user)):
            executed.append(True)
            return {"user_id": current_user.user_id}

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/test")
            assert resp.status_code == 401
            assert len(executed) == 0

    @patch("core.auth.WorkspaceClient")
    def test_access_token_available_on_current_user(self, mock_wsc_class):
        """The raw access_token is preserved on CurrentUser for MCP forwarding."""
        from core.auth import get_current_user, CurrentUser

        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        result = get_current_user(x_forwarded_access_token="my-raw-token")

        assert result.access_token == "my-raw-token"
