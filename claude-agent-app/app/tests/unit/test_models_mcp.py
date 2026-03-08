"""Tests for UserMcpPref model — written BEFORE implementation (RED phase).

Covers:
  1.1 Table name
  1.2 Composite PK
  1.3 Default enabled=True
  1.3 Migration creates table
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def memory_engine():
    """Create a fresh in-memory SQLite engine with all models."""
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


class TestUserMcpPrefModel:
    def test_tablename_is_user_mcp_prefs(self):
        """UserMcpPref.__tablename__ must be 'user_mcp_prefs'."""
        from core.models import UserMcpPref
        assert UserMcpPref.__tablename__ == "user_mcp_prefs"

    def test_table_exists_in_schema(self, memory_engine):
        """user_mcp_prefs table must exist after Base.metadata.create_all."""
        insp = inspect(memory_engine)
        assert "user_mcp_prefs" in insp.get_table_names()

    def test_columns_exist(self, memory_engine):
        """user_mcp_prefs must have user_id, mcp_name, enabled, updated_at."""
        insp = inspect(memory_engine)
        cols = {c["name"] for c in insp.get_columns("user_mcp_prefs")}
        assert "user_id" in cols
        assert "mcp_name" in cols
        assert "enabled" in cols
        assert "updated_at" in cols

    def test_default_enabled_is_true(self, session):
        """UserMcpPref created without enabled defaults to True."""
        from core.models import UserMcpPref
        row = UserMcpPref(user_id="alice", mcp_name="slack")
        session.add(row)
        session.commit()
        result = session.query(UserMcpPref).filter_by(user_id="alice").first()
        assert result.enabled is True

    def test_composite_pk_rejects_duplicate(self, session):
        """Inserting duplicate (user_id, mcp_name) raises IntegrityError."""
        from core.models import UserMcpPref
        row1 = UserMcpPref(user_id="alice", mcp_name="slack", enabled=True)
        row2 = UserMcpPref(user_id="alice", mcp_name="slack", enabled=False)
        session.add(row1)
        session.commit()
        session.add(row2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_different_user_same_mcp_allowed(self, session):
        """Different users can have rows for the same mcp_name."""
        from core.models import UserMcpPref
        row1 = UserMcpPref(user_id="alice", mcp_name="slack", enabled=True)
        row2 = UserMcpPref(user_id="bob", mcp_name="slack", enabled=False)
        session.add_all([row1, row2])
        session.commit()
        count = session.query(UserMcpPref).filter_by(mcp_name="slack").count()
        assert count == 2

    def test_same_user_different_mcp_allowed(self, session):
        """Same user can have rows for different mcp_name values."""
        from core.models import UserMcpPref
        row1 = UserMcpPref(user_id="alice", mcp_name="slack", enabled=True)
        row2 = UserMcpPref(user_id="alice", mcp_name="github", enabled=False)
        session.add_all([row1, row2])
        session.commit()
        count = session.query(UserMcpPref).filter_by(user_id="alice").count()
        assert count == 2


class TestMigrationMcp:
    def test_migration_file_exists(self):
        """Alembic migration 002_add_user_mcp_prefs.py must exist."""
        import os
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "alembic", "versions", "002_add_user_mcp_prefs.py"
        )
        assert os.path.exists(migration_path), f"Migration file not found: {migration_path}"

    def test_migration_has_correct_revision(self):
        """Migration 002 must declare revision = '002_add_user_mcp_prefs'."""
        import os
        import importlib.util
        migration_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            "..", "..", "alembic", "versions", "002_add_user_mcp_prefs.py"
        ))
        spec = importlib.util.spec_from_file_location("migration_002", migration_path)
        module = importlib.util.module_from_spec(spec)
        # Don't exec — just read the source to avoid alembic import issues
        source = open(migration_path).read()
        assert 'revision = "002_add_user_mcp_prefs"' in source or "revision = '002_add_user_mcp_prefs'" in source

    def test_migration_creates_user_mcp_prefs_table(self):
        """Migration 002 upgrade() SQL must reference user_mcp_prefs table."""
        import os
        migration_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            "..", "..", "alembic", "versions", "002_add_user_mcp_prefs.py"
        ))
        source = open(migration_path).read()
        assert "user_mcp_prefs" in source
        assert "user_id" in source
        assert "mcp_name" in source
        assert "enabled" in source
