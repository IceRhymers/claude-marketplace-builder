"""Pydantic schemas for authentication."""

from __future__ import annotations

from pydantic import BaseModel


class MeResponse(BaseModel):
    email: str
    display_name: str
    is_admin: bool
