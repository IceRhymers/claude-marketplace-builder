"""UC MCP Server CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys


def main() -> None:
    """CLI entry point with subcommands."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("uc-mcp")

    parser = argparse.ArgumentParser(
        prog="uc-mcp",
        description="UC MCP Server — proxy HTTP APIs through Databricks UC connections",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── serve ────────────────────────────────────────────────────
    serve_parser = subparsers.add_parser("serve", help="Start MCP server on stdio")
    serve_parser.add_argument("definition", help="Path to YAML definition file")
    serve_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    # ── validate ─────────────────────────────────────────────────
    validate_parser = subparsers.add_parser("validate", help="Validate a YAML definition")
    validate_parser.add_argument("definition", help="Path to YAML definition file")

    # ── introspect ───────────────────────────────────────────────
    introspect_parser = subparsers.add_parser("introspect", help="Introspect an MCP server")
    introspect_parser.add_argument("command", help="Command to run the MCP server")
    introspect_parser.add_argument("--connection", required=True, help="UC connection name")
    introspect_parser.add_argument("--output", "-o", help="Output YAML path")
    introspect_parser.add_argument("--name", help="Service name override")

    # ── from-openapi ─────────────────────────────────────────────
    openapi_parser = subparsers.add_parser("from-openapi", help="Generate definition from OpenAPI spec")
    openapi_parser.add_argument("spec", help="Path or URL to OpenAPI spec")
    openapi_parser.add_argument("--connection", required=True, help="UC connection name")
    openapi_parser.add_argument("--output", "-o", help="Output YAML path")
    openapi_parser.add_argument("--name", help="Service name override")

    # ── build ────────────────────────────────────────────────────
    build_parser = subparsers.add_parser("build", help="Build .pex executable")
    build_parser.add_argument("definition", help="Path to YAML definition file")
    build_parser.add_argument("--scie", action="store_true", help="Build as SCIE")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "serve":
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        from uc_mcp.server import run_server

        run_server(args.definition)

    elif args.command == "validate":
        import pathlib

        import yaml

        from uc_mcp.schema import load_definition, validate_definition

        path = pathlib.Path(args.definition)
        if not path.exists():
            logger.error(f"File not found: {path}")
            sys.exit(1)

        data = yaml.safe_load(path.read_text())
        errors = validate_definition(data)
        if errors:
            for err in errors:
                logger.error(err)
            sys.exit(1)

        defn = load_definition(path)
        print(f"Valid: {defn.name} ({len(defn.tools)} tools)")

    elif args.command == "introspect":
        import asyncio

        from uc_mcp.codegen.introspect import introspect_server

        result = asyncio.run(
            introspect_server(
                args.command,
                args.connection,
                output_path=args.output,
                service_name=args.name,
            )
        )
        if not args.output:
            import yaml

            print(yaml.dump(result, default_flow_style=False))

    elif args.command == "from-openapi":
        from uc_mcp.codegen.from_openapi import generate_from_openapi

        result = generate_from_openapi(
            args.spec,
            args.connection,
            output_path=args.output,
            service_name=args.name,
        )
        if not args.output:
            import yaml

            print(yaml.dump(result, default_flow_style=False))

    elif args.command == "build":
        import subprocess

        build_script = pathlib.Path(__file__).resolve().parent.parent.parent / "build" / "build.sh"
        cmd = ["bash", str(build_script), args.definition]
        if args.scie:
            cmd.append("--scie")
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
