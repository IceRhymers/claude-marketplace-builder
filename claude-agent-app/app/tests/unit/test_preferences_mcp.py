"""Tests for MCP preferences API endpoints — written BEFORE implementation (RED phase).

Covers:
  3.1 GET /api/preferences/mcp — list all servers with enabled state
  3.2 PATCH /api/preferences/mcp/{mcp_name} — upsert server pref, 404 for unknown
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


def make_mcp_skills_config(mcp_config):
    """Create a SkillsConfig with given mcp_config."""
    from core.skills import SkillsConfig
    return SkillsConfig(version="v1.0.0", skills={}, mcp_config=mcp_config)


def make_real_db():
    """Create a real in-memory SQLite DB with all tables."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def make_mock_user(user_id="alice@example.com"):
    with patch.dict("sys.modules", {"databricks": MagicMock(), "databricks.sdk": MagicMock()}):
        from core.auth import CurrentUser
    return CurrentUser(user_id=user_id, access_token="tok")


def make_app(skills_config, db_session, mock_user):
    """Create a TestClient with mocked dependencies."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers.preferences import router
    from deps import get_db, get_skills_config
    from core.auth import get_current_user

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_skills_config] = lambda: skills_config
    test_app.dependency_overrides[get_db] = lambda: db_session
    test_app.dependency_overrides[get_current_user] = lambda: mock_user
    return TestClient(test_app)


class TestGetMcpPrefs:
    def test_returns_all_servers_with_enabled_state(self):
        """GET /api/preferences/mcp returns [{name, enabled}] for all servers."""
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": ["-y", "@slack/mcp"]},
                "github": {"command": "npx", "args": ["-y", "@github/mcp"]},
            }
        }
        sc = make_mcp_skills_config(mcp_config)
        db = make_real_db()
        mock_user = make_mock_user()

        client = make_app(sc, db, mock_user)
        response = client.get("/api/preferences/mcp")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        names = {item["name"] for item in data}
        assert names == {"slack", "github"}
        for item in data:
            assert "name" in item
            assert "enabled" in item

    def test_no_pref_rows_all_enabled(self):
        """GET /api/preferences/mcp with no rows → all enabled=true."""
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": []},
                "github": {"command": "npx", "args": []},
            }
        }
        sc = make_mcp_skills_config(mcp_config)
        db = make_real_db()
        mock_user = make_mock_user()

        client = make_app(sc, db, mock_user)
        response = client.get("/api/preferences/mcp")

        assert response.status_code == 200
        for item in response.json():
            assert item["enabled"] is True

    def test_disabled_server_reflected(self):
        """GET /api/preferences/mcp reflects enabled=false for disabled row."""
        from core.models import UserMcpPref
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": []},
                "github": {"command": "npx", "args": []},
            }
        }
        sc = make_mcp_skills_config(mcp_config)
        db = make_real_db()
        mock_user = make_mock_user()

        # Pre-insert disabled row for slack
        row = UserMcpPref(user_id="alice@example.com", mcp_name="slack", enabled=False)
        db.add(row)
        db.commit()

        client = make_app(sc, db, mock_user)
        response = client.get("/api/preferences/mcp")

        assert response.status_code == 200
        items_by_name = {item["name"]: item for item in response.json()}
        assert items_by_name["slack"]["enabled"] is False
        assert items_by_name["github"]["enabled"] is True

    def test_empty_mcp_servers_returns_empty_list(self):
        """GET /api/preferences/mcp with no servers → []."""
        sc = make_mcp_skills_config({"mcpServers": {}})
        db = make_real_db()
        mock_user = make_mock_user()

        client = make_app(sc, db, mock_user)
        response = client.get("/api/preferences/mcp")

        assert response.status_code == 200
        assert response.json() == []


class TestPatchMcpPref:
    def test_disable_new_row_creates_row(self):
        """PATCH /api/preferences/mcp/slack with enabled=false creates a row."""
        from core.models import UserMcpPref
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": []},
                "github": {"command": "npx", "args": []},
            }
        }
        sc = make_mcp_skills_config(mcp_config)
        db = make_real_db()
        mock_user = make_mock_user()

        client = make_app(sc, db, mock_user)
        response = client.patch("/api/preferences/mcp/slack", json={"enabled": False})

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "slack"
        assert data["enabled"] is False

        # Verify row in DB
        row = db.query(UserMcpPref).filter_by(
            user_id="alice@example.com", mcp_name="slack"
        ).first()
        assert row is not None
        assert row.enabled is False

    def test_re_enable_existing_row(self):
        """PATCH /api/preferences/mcp/slack with enabled=true updates existing row."""
        from core.models import UserMcpPref
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": []},
            }
        }
        sc = make_mcp_skills_config(mcp_config)
        db = make_real_db()
        mock_user = make_mock_user()

        # Pre-insert disabled row
        existing = UserMcpPref(user_id="alice@example.com", mcp_name="slack", enabled=False)
        db.add(existing)
        db.commit()

        client = make_app(sc, db, mock_user)
        response = client.patch("/api/preferences/mcp/slack", json={"enabled": True})

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "slack"
        assert data["enabled"] is True

        # Verify DB row updated
        row = db.query(UserMcpPref).filter_by(
            user_id="alice@example.com", mcp_name="slack"
        ).first()
        assert row.enabled is True

    def test_unknown_server_returns_404(self):
        """PATCH /api/preferences/mcp/unknown-server returns 404."""
        sc = make_mcp_skills_config({"mcpServers": {"slack": {}}})
        db = make_real_db()
        mock_user = make_mock_user()

        client = make_app(sc, db, mock_user)
        response = client.patch("/api/preferences/mcp/unknown-server", json={"enabled": False})

        assert response.status_code == 404
        assert "unknown-server" in response.json()["detail"]

    def test_unknown_server_no_db_write(self):
        """PATCH /api/preferences/mcp/unknown-server does not write to DB."""
        from core.models import UserMcpPref
        sc = make_mcp_skills_config({"mcpServers": {"slack": {}}})
        db = make_real_db()
        mock_user = make_mock_user()

        client = make_app(sc, db, mock_user)
        client.patch("/api/preferences/mcp/unknown-server", json={"enabled": False})

        rows = db.query(UserMcpPref).all()
        assert len(rows) == 0
