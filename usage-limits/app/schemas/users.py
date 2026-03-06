"""Pydantic schemas for user usage data."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserUsageDayOut(BaseModel):
    usage_date: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


class UserUsageHistoryOut(BaseModel):
    user_email: str
    days: list[UserUsageDayOut]
    total_tokens_30d: int
    daily_average: int


class UserSnapshotOut(BaseModel):
    user_id: str
    dollar_cost_1d: float | None = None
    dollar_cost_7d: float | None = None
    dollar_cost_30d: float | None = None
    total_tokens_1d: int | None = None
    total_tokens_7d: int | None = None
    total_tokens_30d: int | None = None
    request_count_1d: int | None = None
    request_count_7d: int | None = None
    request_count_30d: int | None = None
    updated_at: datetime | None = None
