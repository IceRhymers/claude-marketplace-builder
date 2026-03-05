"""Pydantic schemas for OTEL metrics."""

from __future__ import annotations

from pydantic import BaseModel


class OtelUserSummaryOut(BaseModel):
    user_id: str | None = None
    total_value: int
    metric_count: int


class OtelMetricOut(BaseModel):
    metric_name: str | None = None
    user_id: str | None = None
    token_count: int | None = None
    event_time: str | None = None


class OtelStatusOut(BaseModel):
    enabled: bool
    otel_table: str | None = None
