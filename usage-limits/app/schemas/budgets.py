"""Pydantic schemas for budget management."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BudgetConfigIn(BaseModel):
    entity_id: str
    daily_dollar_limit: float | None = None
    weekly_dollar_limit: float | None = None
    monthly_dollar_limit: float | None = None


class BudgetConfigOut(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    daily_dollar_limit: float | None = None
    weekly_dollar_limit: float | None = None
    monthly_dollar_limit: float | None = None
    is_custom: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None


class DefaultBudgetIn(BaseModel):
    daily_dollar_limit: float | None = None
    weekly_dollar_limit: float | None = None
    monthly_dollar_limit: float | None = None


class DefaultBudgetOut(BaseModel):
    id: int
    daily_dollar_limit: float | None = None
    weekly_dollar_limit: float | None = None
    monthly_dollar_limit: float | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None
