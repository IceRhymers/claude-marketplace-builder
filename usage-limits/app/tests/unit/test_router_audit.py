"""Tests for routers/audit.py — Audit log endpoints."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from main import app
from deps import get_db, get_current_user


@pytest.fixture
def test_client(mock_session, admin_identity):
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: admin_identity
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestListAuditLog:
    def test_returns_audit_entries(self, test_client, mock_session):
        mock_row = MagicMock()
        mock_row.id = 1
        mock_row.action = "save_budget"
        mock_row.user_id = "u@e.com"
        mock_row.details = {"daily": 50.0}
        mock_row.created_at = None
        mock_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_row]

        response = test_client.get("/api/audit/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["action"] == "save_budget"

    def test_returns_empty_list(self, test_client, mock_session):
        mock_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        response = test_client.get("/api/audit/")
        assert response.status_code == 200
        assert response.json() == []

    def test_respects_limit_parameter(self, test_client, mock_session):
        mock_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        response = test_client.get("/api/audit/?limit=10")
        assert response.status_code == 200


@pytest.mark.unit
class TestAuditAdminGating:
    def test_returns_403_for_non_admin(self, mock_session, non_admin_identity):
        app.dependency_overrides[get_db] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: non_admin_identity
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/audit/")
        assert response.status_code == 403

        app.dependency_overrides.clear()
