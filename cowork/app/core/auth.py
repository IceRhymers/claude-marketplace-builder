"""User identity resolution from X-Forwarded-Access-Token header."""

from __future__ import annotations

import dataclasses
import logging
from typing import Optional

from databricks.sdk import WorkspaceClient
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CurrentUser:
    """Resolved user identity from the Databricks OAuth token."""
    user_id: str
    access_token: str


def get_current_user(
    x_forwarded_access_token: Optional[str] = Header(default=None),
) -> CurrentUser:
    """FastAPI dependency: resolve user from X-Forwarded-Access-Token header.

    Raises:
        HTTPException(401): if token is missing or invalid.
    """
    if not x_forwarded_access_token:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Forwarded-Access-Token header",
        )

    try:
        client = WorkspaceClient(token=x_forwarded_access_token, auth_type="pat")
        user = client.current_user.me()
        user_id = user.user_name
        return CurrentUser(user_id=user_id, access_token=x_forwarded_access_token)
    except Exception as exc:
        logger.warning("Token validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")
