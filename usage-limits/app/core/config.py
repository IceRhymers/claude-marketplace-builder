"""App configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.auth import parse_admin_groups


@dataclass(frozen=True)
class AppConfig:
    """Immutable configuration for the usage-limits app."""

    pg_host: str
    pg_database: str
    lakebase_instance: str
    sql_warehouse_id: str
    evaluation_interval_minutes: int
    user_sync_interval_minutes: int
    budget_api_port: int
    admin_groups: list[str]

    @classmethod
    def from_env(cls) -> AppConfig:
        """Load configuration from environment variables.

        Raises ValueError if a required variable is missing.
        """
        required = [
            "PGHOST",
            "PGDATABASE",
            "LAKEBASE_INSTANCE",
            "SQL_WAREHOUSE_ID",
        ]
        for var in required:
            if not os.environ.get(var):
                raise ValueError(f"Required environment variable {var} is not set")

        return cls(
            pg_host=os.environ["PGHOST"],
            pg_database=os.environ["PGDATABASE"],
            lakebase_instance=os.environ["LAKEBASE_INSTANCE"],
            sql_warehouse_id=os.environ["SQL_WAREHOUSE_ID"],
            evaluation_interval_minutes=int(
                os.environ.get("EVALUATION_INTERVAL_MINUTES", "5")
            ),
            user_sync_interval_minutes=int(
                os.environ.get("USER_SYNC_INTERVAL_MINUTES", "5")
            ),
            budget_api_port=int(
                os.environ.get("BUDGET_API_PORT", "8502")
            ),
            admin_groups=parse_admin_groups(
                os.environ.get("ADMIN_GROUPS", "")
            ),
        )

    @property
    def conninfo(self) -> str:
        """Return a psycopg DSN connection string (without user — injected at connect time)."""
        return (
            f"dbname={self.pg_database} "
            f"host={self.pg_host} "
            f"port=5432 "
            f"sslmode=require"
        )
