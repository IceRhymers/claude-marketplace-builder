"""Integration tests for the SSE streaming endpoint.

Written BEFORE implementation (RED phase).
"""

from __future__ import annotations

import uuid
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
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


class TestStreamEndpoint:
    @patch("core.auth.WorkspaceClient")
    async def test_stream_emits_text_delta_and_done(self, mock_wsc_class):
        """GET /api/conversations/{id}/stream emits text_delta and done events."""
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        import httpx
        from httpx import AsyncClient
        from fastapi import FastAPI
        from core.models import Conversation
        from routers.stream import router as stream_router
        from deps import get_db, get_agent_pool, get_skills_config

        engine, SessionLocal = make_sqlite_setup()

        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com", title="Test")
        session.add(conv)
        session.commit()
        session.close()

        app = FastAPI()
        app.include_router(stream_router)

        # Scripted mock agent as an async generator function
        class ScriptedAgent:
            async def stream(self, message: str):
                yield {"type": "text_delta", "text": "Hello"}
                yield {"type": "done"}

            def close(self):
                pass

        scripted_agent = ScriptedAgent()
        mock_pool = MagicMock()
        mock_pool.get_or_create = AsyncMock(return_value=scripted_agent)

        mock_skills = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

        def override_get_db():
            s = SessionLocal()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_agent_pool] = lambda: mock_pool
        app.dependency_overrides[get_skills_config] = lambda: mock_skills

        async with AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            async with client.stream(
                "GET",
                f"/api/conversations/{conv_id}/stream",
                params={"message": "Hello"},
                headers={"X-Forwarded-Access-Token": "alice-token"},
            ) as resp:
                assert resp.status_code == 200
                chunks = []
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            chunks.append(json.loads(line[6:]))
                        except json.JSONDecodeError:
                            pass

        event_types = [c["type"] for c in chunks]
        assert "text_delta" in event_types
        assert "done" in event_types

    @patch("core.auth.WorkspaceClient")
    async def test_stream_returns_404_for_non_owned_conversation(self, mock_wsc_class):
        """Stream endpoint returns 404 for non-owned conversation."""
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "bob@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        import httpx
        from httpx import AsyncClient
        from fastapi import FastAPI
        from core.models import Conversation
        from routers.stream import router as stream_router
        from deps import get_db, get_agent_pool, get_skills_config

        engine, SessionLocal = make_sqlite_setup()

        # Alice owns the conv
        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com")
        session.add(conv)
        session.commit()
        session.close()

        app = FastAPI()
        app.include_router(stream_router)

        def override_get_db():
            s = SessionLocal()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_agent_pool] = lambda: MagicMock()
        app.dependency_overrides[get_skills_config] = lambda: MagicMock()

        async with AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/conversations/{conv_id}/stream",
                params={"message": "Hello"},
                headers={"X-Forwarded-Access-Token": "bob-token"},
            )
            assert resp.status_code == 404

    @patch("core.auth.WorkspaceClient")
    async def test_messages_persisted_after_stream_completes(self, mock_wsc_class):
        """After stream completes, user and assistant messages are in DB."""
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.user_name = "alice@example.com"
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        import httpx
        from httpx import AsyncClient
        from fastapi import FastAPI
        from core.models import Conversation, Message
        from routers.stream import router as stream_router
        from deps import get_db, get_agent_pool, get_skills_config

        engine, SessionLocal = make_sqlite_setup()

        session = SessionLocal()
        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id="alice@example.com", title="Test")
        session.add(conv)
        session.commit()
        session.close()

        app = FastAPI()
        app.include_router(stream_router)

        class ScriptedAgent:
            async def stream(self, message: str):
                yield {"type": "text_delta", "text": "Response text"}
                yield {"type": "done"}

            def close(self):
                pass

        scripted_agent = ScriptedAgent()
        mock_pool = MagicMock()
        mock_pool.get_or_create = AsyncMock(return_value=scripted_agent)

        mock_skills = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

        def override_get_db():
            s = SessionLocal()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_agent_pool] = lambda: mock_pool
        app.dependency_overrides[get_skills_config] = lambda: mock_skills

        async with AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            async with client.stream(
                "GET",
                f"/api/conversations/{conv_id}/stream",
                params={"message": "Hello there"},
                headers={"X-Forwarded-Access-Token": "alice-token"},
            ) as resp:
                # Consume the full stream
                async for _ in resp.aiter_lines():
                    pass

        # Check messages were persisted
        check_session = SessionLocal()
        msgs = check_session.query(Message).filter_by(conversation_id=conv_id).all()
        check_session.close()

        assert len(msgs) == 2
        roles = {m.role for m in msgs}
        assert "user" in roles
        assert "assistant" in roles
