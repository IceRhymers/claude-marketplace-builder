"""Pydantic schemas for personal usage data."""

from __future__ import annotations

from pydantic import BaseModel


class MyBudgetStatus(BaseModel):
    daily_dollar_limit: float | None = None
    weekly_dollar_limit: float | None = None
    monthly_dollar_limit: float | None = None
    dollar_cost_1d: float | None = None
    dollar_cost_7d: float | None = None
    dollar_cost_30d: float | None = None
