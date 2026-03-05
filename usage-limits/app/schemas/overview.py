"""Pydantic schemas for the overview dashboard."""

from __future__ import annotations

from pydantic import BaseModel


class OverviewMetricsOut(BaseModel):
    cost_today: float
    requests_today: int
    active_users: int


class TopUserOut(BaseModel):
    requester: str
    total_tokens: int
    request_count: int
