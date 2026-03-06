"""Pydantic schemas for audit log."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    action: str
    user_id: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime | None = None
