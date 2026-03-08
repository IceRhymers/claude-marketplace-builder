"""Unit tests for get_user_skill_prefs dependency and preferences router.

Written before implementation (RED -> GREEN).
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


def make_skills_config(skill_names, tmp_path=None):
    """Helper to create a SkillsConfig with given skill names."""
    from core.skills import SkillsConfig, SkillDefinition
    skills = {}
    for name in skill_names:
        path = (tmp_path / name) if tmp_path else Path(f"/fake/skills/{name}")
        if tmp_path:
            path.mkdir(parents=True, exist_ok=True)
        skills[name] = SkillDefinition(
            name=name,
            path=path,
            has_scripts=False,
            has_references=False,
        )
    return SkillsConfig(version="v1.0.0", skills=skills, mcp_config={})


def make_db_with_prefs(prefs: dict):
    """Create a mock DB session that returns UserSkillPref rows for given dict.

    prefs: {skill_name: enabled_bool}
    """
    from core.models import UserSkillPref
    rows = []
    for skill_name, enabled in prefs.items():
        row = MagicMock(spec=UserSkillPref)
        row.skill_name = skill_name
        row.enabled = enabled
        rows.append(row)

    db = MagicMock()
    query_mock = MagicMock()
    filter_mock = MagicMock()
    filter_mock.all.return_value = rows
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock
    return db


class TestGetUserSkillPrefs:
    def test_all_skills_enabled_when_no_prefs(self):
        """No pref rows → all skills in config returned as enabled."""
        from deps import get_user_skill_prefs

        skills_config = make_skills_config(["skill-a", "skill-b", "skill-c"])
        db = make_db_with_prefs({})

        result = get_user_skill_prefs("alice", db, skills_config)
        assert result == {"skill-a", "skill-b", "skill-c"}

    def test_disabled_skill_excluded(self):
        """Skill with enabled=False pref row is excluded from result."""
        from deps import get_user_skill_prefs

        skills_config = make_skills_config(["skill-a", "skill-b", "skill-c"])
        db = make_db_with_prefs({"skill-a": False, "skill-c": True})

        result = get_user_skill_prefs("alice", db, skills_config)
        # skill-a disabled, skill-b default-enabled, skill-c explicitly enabled
        assert result == {"skill-b", "skill-c"}

    def test_mix_of_explicit_prefs_and_defaults(self):
        """Mix of explicit prefs and missing → correct set."""
        from deps import get_user_skill_prefs

        skills_config = make_skills_config(["skill-a", "skill-b", "skill-c"])
        # Only skill-a explicitly disabled; skill-c explicitly enabled; skill-b has no row
        db = make_db_with_prefs({"skill-a": False, "skill-c": True})

        result = get_user_skill_prefs("alice", db, skills_config)
        assert "skill-a" not in result
        assert "skill-b" in result
        assert "skill-c" in result

    def test_orphaned_pref_for_removed_skill_not_in_result(self):
        """Pref row for skill no longer in config is not included."""
        from deps import get_user_skill_prefs

        skills_config = make_skills_config(["skill-b"])  # old-skill removed
        db = make_db_with_prefs({"old-skill": True})  # orphaned row

        result = get_user_skill_prefs("alice", db, skills_config)
        assert "old-skill" not in result
        assert "skill-b" in result

    def test_two_users_independent(self):
        """Different users get independent pref sets."""
        from deps import get_user_skill_prefs

        skills_config = make_skills_config(["skill-a", "skill-b"])
        db_alice = make_db_with_prefs({"skill-a": False})
        db_bob = make_db_with_prefs({})

        result_alice = get_user_skill_prefs("alice", db_alice, skills_config)
        result_bob = get_user_skill_prefs("bob", db_bob, skills_config)

        assert "skill-a" not in result_alice
        assert "skill-b" in result_alice
        assert result_bob == {"skill-a", "skill-b"}

    def test_empty_skills_config_returns_empty_set(self):
        """Empty SkillsConfig.skills → always returns empty set."""
        from deps import get_user_skill_prefs

        skills_config = make_skills_config([])
        db = make_db_with_prefs({"skill-a": True})

        result = get_user_skill_prefs("alice", db, skills_config)
        assert result == set()


class TestPreferencesRouter:
    def _make_app(self, skills_config, db_session, mock_user):
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

    def _make_real_db(self, tmp_path=None):
        """Create a real in-memory SQLite DB with UserSkillPref table."""
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

    def _make_mock_user(self, user_id="alice@example.com"):
        with patch.dict("sys.modules", {"databricks": MagicMock(), "databricks.sdk": MagicMock()}):
            from core.auth import CurrentUser
        return CurrentUser(user_id=user_id, access_token="tok")

    def test_get_skill_prefs_all_default_enabled(self, tmp_path):
        """GET /api/preferences/skills returns all skills with enabled=true when no rows."""
        from core.skills import SkillsConfig, SkillDefinition

        skill_path = tmp_path / "skill-a"
        skill_path.mkdir()
        sc = SkillsConfig(
            version="v1.0.0",
            skills={
                "skill-a": SkillDefinition("skill-a", skill_path, False, False),
            },
            mcp_config={},
        )
        db = self._make_real_db()
        mock_user = self._make_mock_user()

        client = self._make_app(sc, db, mock_user)
        response = client.get("/api/preferences/skills")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "skill-a"
        assert data[0]["enabled"] is True

    def test_get_skill_prefs_reflects_disabled_row(self, tmp_path):
        """GET /api/preferences/skills shows enabled=false for row with enabled=False."""
        from core.skills import SkillsConfig, SkillDefinition
        from core.models import UserSkillPref

        skill_path = tmp_path / "skill-a"
        skill_path.mkdir()
        sc = SkillsConfig(
            version="v1.0.0",
            skills={
                "skill-a": SkillDefinition("skill-a", skill_path, False, False),
            },
            mcp_config={},
        )
        db = self._make_real_db()
        mock_user = self._make_mock_user()

        # Insert a disabled row
        row = UserSkillPref(user_id="alice@example.com", skill_name="skill-a", enabled=False)
        db.add(row)
        db.commit()

        client = self._make_app(sc, db, mock_user)
        response = client.get("/api/preferences/skills")

        assert response.status_code == 200
        data = response.json()
        assert data[0]["name"] == "skill-a"
        assert data[0]["enabled"] is False

    def test_get_skill_prefs_empty_config(self):
        """GET /api/preferences/skills with empty skills config returns []."""
        from core.skills import SkillsConfig
        sc = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})
        db = self._make_real_db()
        mock_user = self._make_mock_user()

        client = self._make_app(sc, db, mock_user)
        response = client.get("/api/preferences/skills")

        assert response.status_code == 200
        assert response.json() == []

    def test_patch_creates_new_row(self, tmp_path):
        """PATCH /api/preferences/skills/<name> creates new row and returns 200."""
        from core.skills import SkillsConfig, SkillDefinition
        from core.models import UserSkillPref

        skill_path = tmp_path / "skill-a"
        skill_path.mkdir()
        sc = SkillsConfig(
            version="v1.0.0",
            skills={
                "skill-a": SkillDefinition("skill-a", skill_path, True, False),
            },
            mcp_config={},
        )
        db = self._make_real_db()
        mock_user = self._make_mock_user()

        client = self._make_app(sc, db, mock_user)
        response = client.patch(
            "/api/preferences/skills/skill-a",
            json={"enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "skill-a"
        assert data["enabled"] is False
        assert data["has_scripts"] is True

        # Verify row in DB
        row = db.query(UserSkillPref).filter_by(
            user_id="alice@example.com", skill_name="skill-a"
        ).first()
        assert row is not None
        assert row.enabled is False

    def test_patch_updates_existing_row(self, tmp_path):
        """PATCH on existing row updates enabled value."""
        from core.skills import SkillsConfig, SkillDefinition
        from core.models import UserSkillPref

        skill_path = tmp_path / "skill-a"
        skill_path.mkdir()
        sc = SkillsConfig(
            version="v1.0.0",
            skills={
                "skill-a": SkillDefinition("skill-a", skill_path, False, False),
            },
            mcp_config={},
        )
        db = self._make_real_db()
        mock_user = self._make_mock_user()

        # Pre-insert row with enabled=False
        existing = UserSkillPref(user_id="alice@example.com", skill_name="skill-a", enabled=False)
        db.add(existing)
        db.commit()

        client = self._make_app(sc, db, mock_user)
        response = client.patch(
            "/api/preferences/skills/skill-a",
            json={"enabled": True},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is True

        row = db.query(UserSkillPref).filter_by(
            user_id="alice@example.com", skill_name="skill-a"
        ).first()
        assert row.enabled is True

    def test_patch_unknown_skill_returns_404(self, tmp_path):
        """PATCH unknown skill name returns 404 and no DB write."""
        from core.skills import SkillsConfig
        from core.models import UserSkillPref

        sc = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})
        db = self._make_real_db()
        mock_user = self._make_mock_user()

        client = self._make_app(sc, db, mock_user)
        response = client.patch(
            "/api/preferences/skills/nonexistent-skill",
            json={"enabled": False},
        )

        assert response.status_code == 404
        assert "nonexistent-skill" in response.json()["detail"]

        # No rows written
        rows = db.query(UserSkillPref).all()
        assert len(rows) == 0

    def test_two_users_independent_preferences(self, tmp_path):
        """Alice disabling a skill does not affect Bob's preferences."""
        from core.skills import SkillsConfig, SkillDefinition
        from core.models import UserSkillPref

        skill_path = tmp_path / "skill-a"
        skill_path.mkdir()
        sc = SkillsConfig(
            version="v1.0.0",
            skills={
                "skill-a": SkillDefinition("skill-a", skill_path, False, False),
            },
            mcp_config={},
        )
        db = self._make_real_db()

        with patch.dict("sys.modules", {"databricks": MagicMock(), "databricks.sdk": MagicMock()}):
            from core.auth import CurrentUser
        alice = CurrentUser(user_id="alice@example.com", access_token="tok-alice")
        bob = CurrentUser(user_id="bob@example.com", access_token="tok-bob")

        # Alice disables skill-a
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routers.preferences import router
        from deps import get_db, get_skills_config
        from core.auth import get_current_user

        # Client for Alice
        app_alice = FastAPI()
        app_alice.include_router(router)
        app_alice.dependency_overrides[get_skills_config] = lambda: sc
        app_alice.dependency_overrides[get_db] = lambda: db
        app_alice.dependency_overrides[get_current_user] = lambda: alice
        client_alice = TestClient(app_alice)

        client_alice.patch("/api/preferences/skills/skill-a", json={"enabled": False})

        # Client for Bob (same DB)
        app_bob = FastAPI()
        app_bob.include_router(router)
        app_bob.dependency_overrides[get_skills_config] = lambda: sc
        app_bob.dependency_overrides[get_db] = lambda: db
        app_bob.dependency_overrides[get_current_user] = lambda: bob
        client_bob = TestClient(app_bob)

        response_bob = client_bob.get("/api/preferences/skills")
        assert response_bob.status_code == 200
        data = response_bob.json()
        # Bob's skill-a should still be default enabled
        assert data[0]["enabled"] is True
