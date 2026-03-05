"""FastAPI budget check endpoint for Claude Code hook integration."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException
from databricks.sdk import WorkspaceClient
from sqlalchemy.orm import sessionmaker, Session

from core.warnings import get_active_warnings_for_user

logger = logging.getLogger(__name__)

app = FastAPI(title="Usage Limits Budget API")

_session_factory: sessionmaker[Session] | None = None


def set_session_factory(factory: sessionmaker[Session]) -> None:
    """Set the SQLAlchemy session factory for the API."""
    global _session_factory
    _session_factory = factory


def get_session() -> Session:
    """Create a new database session."""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized")
    return _session_factory()


@app.get("/api/check-budget")
def check_budget(authorization: str = Header(default=None)):
    """Check if a user is within their budget.

    Resolves user identity from the Databricks token in the Authorization header.
    Returns {"allowed": true} or {"allowed": false, "reason": "..."}.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        client = WorkspaceClient(token=token, host="")
        user = client.current_user.me()
        user_email = user.user_name
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    logger.info("Budget check request for user=%s", user_email)

    session = get_session()
    try:
        warnings = get_active_warnings_for_user(session, user_email)
    finally:
        session.close()

    if warnings:
        first = warnings[0]
        reason = first["reason"]
        logger.info("Budget check denied for user=%s: %s", user_email, reason)
        return {
            "allowed": False,
            "reason": reason,
            "usage": float(first.get("dollar_usage") or 0),
            "limit": float(first.get("dollar_limit") or 0),
        }

    logger.info("Budget check allowed for user=%s", user_email)
    return {"allowed": True}
