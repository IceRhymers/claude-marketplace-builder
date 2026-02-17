#!/usr/bin/env python3
"""
Search for tables and explore lineage relationships in Databricks Unity Catalog.

Usage:
    python search_lineage.py <pattern> [--catalog CATALOG] [--depth N]
"""

import argparse
import json
import subprocess
import sys
from collections import deque


def run_api(endpoint: str) -> dict | None:
    try:
        result = subprocess.run(
            ["databricks", "api", "get", endpoint],
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout) if result.stdout.strip() else None
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def run_sql(query: str) -> list[dict] | None:
    try:
        result = subprocess.run(
            ["databricks", "sql", "query", query],
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout) if result.stdout.strip() else None
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def search_tables(pattern: str, catalog: str | None = None) -> list[str]:
    source = f"{catalog}.information_schema.tables" if catalog else "system.information_schema.tables"
    rows = run_sql(f"SELECT table_catalog, table_schema, table_name FROM {source} WHERE LOWER(table_name) LIKE '%{pattern.lower()}%' LIMIT 50")
    if not rows:
        return []
    return [f"{r.get('table_catalog','')}.{r.get('table_schema','')}.{r.get('table_name','')}" for r in rows]


def get_lineage(table: str) -> tuple[list[str], list[str]]:
    data = run_api(f"/api/2.0/lineage-tracking/table-lineage?table_name={table}&include_entity_lineage=true")
    if not data:
        return [], []
    def extract(items):
        return [f"{i['tableInfo'].get('catalog_name','')}.{i['tableInfo'].get('schema_name','')}.{i['tableInfo'].get('name','')}"
                for i in items if "tableInfo" in i]
    return extract(data.get("upstreams", [])), extract(data.get("downstreams", []))


def main():
    parser = argparse.ArgumentParser(description="Search tables and explore lineage")
    parser.add_argument("pattern", help="Search pattern for table names")
    parser.add_argument("--catalog", "-c", help="Limit to a specific catalog")
    parser.add_argument("--depth", "-d", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    print(f"Searching for tables matching '{args.pattern}'...")
    tables = search_tables(args.pattern, args.catalog)
    if not tables:
        print("No tables found. Try specifying a known table with get_table_lineage.py")
        sys.exit(0)

    print(f"Found {len(tables)} table(s):\n")
    for t in tables:
        print(f"  - {t}")
        if args.depth > 0:
            ups, downs = get_lineage(t)
            for u in ups:
                print(f"    <- {u}")
            for d in downs:
                print(f"    -> {d}")


if __name__ == "__main__":
    main()
