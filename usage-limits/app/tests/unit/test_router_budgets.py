"""Tests for routers/budgets.py — Budget management endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from deps import get_db


@pytest.fixture
def test_client(mock_session):
    app.dependency_overrides[get_db] = lambda: mock_session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestListBudgets:
    def test_returns_all_budgets(self, test_client, mock_session):
        mock_row = MagicMock()
        mock_row.to_dict.return_value = {
            "id": 1,
            "entity_type": "user",
            "entity_id": "u@e.com",
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
            "is_admin": False,
            "created_at": None,
            "updated_at": None,
            "created_by": None,
        }
        mock_session.query.return_value.all.return_value = [mock_row]

        response = test_client.get("/api/budgets/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["entity_id"] == "u@e.com"

    def test_returns_empty_list(self, test_client, mock_session):
        mock_session.query.return_value.all.return_value = []

        response = test_client.get("/api/budgets/")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.unit
class TestSaveBudget:
    @patch("routers.budgets.save_budget_config")
    @patch("routers.budgets.log_audit_entry")
    def test_creates_budget(self, mock_audit, mock_save, test_client, mock_session):
        mock_row = MagicMock()
        mock_row.to_dict.return_value = {
            "id": 1,
            "entity_type": "user",
            "entity_id": "u@e.com",
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": None,
            "monthly_dollar_limit": None,
            "is_admin": False,
            "created_at": None,
            "updated_at": None,
            "created_by": None,
        }
        mock_session.query.return_value.filter.return_value.first.return_value = mock_row

        response = test_client.post("/api/budgets/", json={
            "entity_id": "u@e.com",
            "daily_dollar_limit": 50.0,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["entity_id"] == "u@e.com"
        mock_save.assert_called_once()
        mock_audit.assert_called_once()


@pytest.mark.unit
class TestDeleteBudget:
    def test_deletes_existing_budget(self, test_client, mock_session):
        mock_row = MagicMock()
        mock_row.entity_id = "u@e.com"
        mock_session.get.return_value = mock_row

        response = test_client.delete("/api/budgets/1")
        assert response.status_code == 200
        assert response.json()["deleted"] is True
        mock_session.delete.assert_called_once_with(mock_row)

    def test_returns_404_for_missing_budget(self, test_client, mock_session):
        mock_session.get.return_value = None

        response = test_client.delete("/api/budgets/999")
        assert response.status_code == 404


@pytest.mark.unit
class TestGetDefaultBudget:
    def test_returns_null_when_none(self, test_client, mock_session):
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        response = test_client.get("/api/budgets/default")
        assert response.status_code == 200
        assert response.json() is None

    def test_returns_default(self, test_client, mock_session):
        mock_row = MagicMock()
        mock_row.to_dict.return_value = {
            "id": 1,
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
            "updated_at": None,
            "updated_by": None,
        }
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_row

        response = test_client.get("/api/budgets/default")
        assert response.status_code == 200
        data = response.json()
        assert data["daily_dollar_limit"] == 50.0


@pytest.mark.unit
class TestSaveDefaultBudget:
    @patch("routers.budgets.save_default_budget")
    @patch("routers.budgets.log_audit_entry")
    def test_saves_default(self, mock_audit, mock_save, test_client, mock_session):
        mock_row = MagicMock()
        mock_row.to_dict.return_value = {
            "id": 1,
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
            "updated_at": None,
            "updated_by": None,
        }
        mock_session.query.return_value.order_by.return_value.first.return_value = mock_row

        response = test_client.post("/api/budgets/default", json={
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
        })
        assert response.status_code == 200
        mock_save.assert_called_once()
