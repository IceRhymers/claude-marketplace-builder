"""Create a Lakebase project for the usage-limits app via Databricks SDK."""

from __future__ import annotations

import argparse
import sys

from databricks.sdk import WorkspaceClient


def create_lakebase_project(
    project_name: str = "usage-limits",
    branch: str = "main",
) -> None:
    """Create a Lakebase project and endpoint."""
    w = WorkspaceClient()

    print(f"Creating Lakebase project: {project_name}")

    try:
        project = w.postgres.create_project(name=project_name)
        print(f"  Project created: {project.name}")

        endpoint = w.postgres.create_endpoint(
            project_name=project.name,
            branch_name=branch,
        )
        print(f"  Endpoint created: {endpoint.name}")
        print(f"  Endpoint path: {endpoint.endpoint}")
        print("")
        print("Set these environment variables in app.yaml:")
        print(f"  PGHOST: {endpoint.host}")
        print(f"  PGDATABASE: {endpoint.database}")
        print(f"  LAKEBASE_ENDPOINT: {endpoint.endpoint}")
        print(f"  PGUSER: <your-service-principal-client-id>")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Create a Lakebase project for usage-limits")
    parser.add_argument("--name", default="usage-limits", help="Project name")
    parser.add_argument("--branch", default="main", help="Branch name")
    args = parser.parse_args()

    create_lakebase_project(project_name=args.name, branch=args.branch)


if __name__ == "__main__":
    main()
