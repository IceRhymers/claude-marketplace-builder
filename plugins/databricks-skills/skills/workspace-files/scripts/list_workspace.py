#!/usr/bin/env python3
"""
List Databricks workspace contents with optional recursion.

Usage:
    python list_workspace.py /path [--recursive] [--max-depth N]
"""

import argparse
import json
import subprocess
import sys


def run_databricks_command(args: list[str]) -> dict | list | None:
    """Run a databricks CLI command and return parsed JSON output."""
    try:
        result = subprocess.run(
            ["databricks"] + args + ["--output", "json"],
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout) if result.stdout.strip() else None
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def list_workspace(path: str) -> list[dict]:
    result = run_databricks_command(["workspace", "list", path])
    if isinstance(result, dict) and "objects" in result:
        return result["objects"]
    return result if isinstance(result, list) else []


def format_object(obj: dict, indent: int = 0) -> str:
    prefix = "  " * indent
    name = obj.get("path", "").split("/")[-1]
    indicator = {"DIRECTORY": "[DIR]", "NOTEBOOK": "[NB] ", "FILE": "[FILE]"}.get(
        obj.get("object_type", ""), "[???]"
    )
    lang = obj.get("language", "")
    return f"{prefix}{indicator} {name}{f' ({lang.lower()})' if lang else ''}"


def list_recursive(path: str, max_depth: int, depth: int = 0) -> None:
    for obj in list_workspace(path):
        print(format_object(obj, depth))
        if obj.get("object_type") == "DIRECTORY" and depth < max_depth:
            list_recursive(obj["path"], max_depth, depth + 1)


def main():
    parser = argparse.ArgumentParser(description="List Databricks workspace contents")
    parser.add_argument("path", help="Workspace path to list")
    parser.add_argument("--recursive", "-r", action="store_true")
    parser.add_argument("--max-depth", "-d", type=int, default=3)
    args = parser.parse_args()

    if args.recursive:
        print(f"Listing {args.path} (recursive, max depth: {args.max_depth})")
        print("-" * 50)
        list_recursive(args.path, args.max_depth)
    else:
        objects = list_workspace(args.path)
        if not objects:
            print(f"No objects found at {args.path}")
            return
        print(f"Contents of {args.path}:")
        print("-" * 50)
        for obj in objects:
            print(format_object(obj))


if __name__ == "__main__":
    main()
