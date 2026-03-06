"""SQLAlchemy ORM models for the usage-limits app."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    BigInteger,
    CheckConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BudgetConfig(Base):
    __tablename__ = "budget_configs"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id"),
        CheckConstraint("entity_type IN ('user', 'group')", name="ck_entity_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    daily_dollar_limit: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    weekly_dollar_limit: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    monthly_dollar_limit: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class DefaultBudget(Base):
    __tablename__ = "default_budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_dollar_limit: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    weekly_dollar_limit: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    monthly_dollar_limit: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Warning(Base):
    __tablename__ = "warnings"
    __table_args__ = (UniqueConstraint("user_id", "reason"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    dollar_usage: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    dollar_limit: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    enforced_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class UsageSnapshot(Base):
    __tablename__ = "usage_snapshots"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    dollar_cost_1d: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    dollar_cost_7d: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    dollar_cost_30d: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_tokens_1d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_tokens_7d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_tokens_30d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    request_count_1d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_count_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_count_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    def to_dict(self) -> dict:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class AppConfigEntry(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
