"""Pydantic schemas for budget warnings."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WarningOut(BaseModel):
    id: int
    user_id: str
    reason: str
    dollar_usage: float | None = None
    dollar_limit: float | None = None
    enforced_at: datetime | None = None
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
    is_active: bool


class ResolveWarningIn(BaseModel):
    warning_id: int
