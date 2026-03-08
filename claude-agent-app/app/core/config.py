"""App configuration loaded from environment variables."""

from __future__ import annotations

import dataclasses
import os


@dataclasses.dataclass(frozen=True)
class AppConfig:
    """Immutable configuration for the claude-agent-app."""

    pg_host: str
    pg_database: str
    lakebase_instance: str
    skills_volume_path: str
    agent_ttl_minutes: int
    skills_reload_interval_seconds: int

    @classmethod
    def from_env(cls) -> AppConfig:
        """Load configuration from environment variables.

        Raises ValueError if a required variable is missing.
        """
        required = ["PGHOST", "PGDATABASE", "LAKEBASE_INSTANCE"]
        for var in required:
            if not os.environ.get(var):
                raise ValueError(f"Required environment variable {var} is not set")

        return cls(
            pg_host=os.environ["PGHOST"],
            pg_database=os.environ["PGDATABASE"],
            lakebase_instance=os.environ["LAKEBASE_INSTANCE"],
            skills_volume_path=os.environ.get("SKILLS_VOLUME_PATH", ""),
            agent_ttl_minutes=int(os.environ.get("AGENT_TTL_MINUTES", "30")),
            skills_reload_interval_seconds=int(
                os.environ.get("SKILLS_RELOAD_INTERVAL_SECONDS", "60")
            ),
        )

    @property
    def conninfo(self) -> str:
        """Return a psycopg DSN connection string."""
        return (
            f"dbname={self.pg_database} "
            f"host={self.pg_host} "
            f"port=5432 "
            f"sslmode=require"
        )
