"""FastAPI budget check endpoint for Claude Code hook integration."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException
from databricks.sdk import WorkspaceClient

from core.warnings import get_active_warnings_for_user

logger = logging.getLogger(__name__)

app = FastAPI(title="Usage Limits Budget API")

_pool = None


def set_pool(pool):
    """Set the database pool for the API."""
    global _pool
    _pool = pool


def get_pool():
    """Get the database pool."""
    if _pool is None:
        raise RuntimeError("Pool not initialized")
    return _pool


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

    pool = get_pool()
    warnings = get_active_warnings_for_user(pool, user_email)

    if warnings:
        reasons = [w["reason"] for w in warnings]
        return {"allowed": False, "reason": "; ".join(reasons)}

    return {"allowed": True}
