"""CLI wrapper for schema initialization."""

from __future__ import annotations

import sys


def main():
    """Initialize the Lakebase schema from the command line."""
    from core.config import AppConfig
    from core.db import create_pool, init_schema

    try:
        config = AppConfig.from_env()
        pool = create_pool(config)
        init_schema(pool)
        print("Schema initialized successfully.")
        pool.close()
    except Exception as e:
        print(f"Schema initialization failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
