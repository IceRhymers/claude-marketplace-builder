#!/usr/bin/env python3
"""
generate-routing-tests.py

Walks all plugins/*/skills/*/evals/evals.json files, extracts should_trigger:true
entries, and emits:
  - evals/test-cases/<plugin-name>.yaml   (per-plugin)
  - evals/test-cases/all.yaml             (full catalog)

Usage:
    python evals/scripts/generate-routing-tests.py
    python evals/scripts/generate-routing-tests.py --plugins-dir plugins/ --out-dir evals/test-cases/
    make evals-generate
"""

import argparse
import json
import re
import sys
from pathlib import Path


def slugify_query(query: str, max_words: int = 5) -> str:
    """Return first max_words words of query, lowercased, non-alphanumeric stripped, joined by hyphens."""
    words = query.lower().split()[:max_words]
    slugged = [re.sub(r"[^a-z0-9]", "", w) for w in words]
    slugged = [w for w in slugged if w]
    return "-".join(slugged)


def derive_test_name(skill_name: str, query: str, seen: set[str]) -> str:
    """Derive a unique test name: <skill-name>-<first-5-words-slug>, max 80 chars."""
    slug = slugify_query(query)
    base = f"{skill_name}-{slug}"[:80]
    name = base
    counter = 2
    while name in seen:
        suffix = f"-{counter}"
        name = base[: 80 - len(suffix)] + suffix
        counter += 1
    seen.add(name)
    return name


def load_evals_json(path: Path) -> list[dict]:
    """Load and validate an evals.json file. Raises ValueError on bad format."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e

    if not isinstance(data, list):
        raise ValueError(f"{path}: top-level value must be a JSON array, got {type(data).__name__}")

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}[{i}]: each entry must be an object, got {type(entry).__name__}")
        if "query" not in entry:
            raise ValueError(f"{path}[{i}]: missing required field 'query'")
        if "should_trigger" not in entry:
            raise ValueError(f"{path}[{i}]: missing required field 'should_trigger'")
        if not isinstance(entry["query"], str):
            raise ValueError(f"{path}[{i}]: 'query' must be a string")
        if not isinstance(entry["should_trigger"], bool):
            raise ValueError(f"{path}[{i}]: 'should_trigger' must be a boolean")

    return data


def build_test_case(skill_name: str, query: str, seen_names: set[str]) -> dict:
    return {
        "name": derive_test_name(skill_name, query, seen_names),
        "prompt": query,
        "expected_skill": skill_name,
    }


def format_yaml_test_cases(test_cases: list[dict]) -> str:
    """Format test cases as YAML compatible with runner.py (no PyYAML dependency)."""
    lines = ["tests:"]
    for tc in test_cases:
        lines.append(f"  - name: {tc['name']}")
        # Quote the prompt to handle special characters
        prompt_escaped = tc["prompt"].replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    prompt: "{prompt_escaped}"')
        lines.append(f"    expected_skill: {tc['expected_skill']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate routing test YAMLs from per-skill evals.json files."
    )
    parser.add_argument(
        "--plugins-dir",
        default="plugins/",
        help="Root plugins directory (default: plugins/)",
    )
    parser.add_argument(
        "--out-dir",
        default="evals/test-cases/",
        help="Output directory for generated YAMLs (default: evals/test-cases/)",
    )
    args = parser.parse_args()

    plugins_dir = Path(args.plugins_dir)
    out_dir = Path(args.out_dir)

    if not plugins_dir.is_dir():
        print(f"ERROR: plugins dir not found: {plugins_dir}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    # Walk plugins/*/skills/*/evals/evals.json
    evals_files = sorted(plugins_dir.glob("*/skills/*/evals/evals.json"))

    if not evals_files:
        print(f"WARN: no evals.json files found under {plugins_dir}", file=sys.stderr)

    # plugin_name -> list of test cases
    per_plugin: dict[str, list[dict]] = {}
    had_error = False

    for evals_path in evals_files:
        # plugins/<plugin-name>/skills/<skill-name>/evals/evals.json
        parts = evals_path.parts
        try:
            plugin_name = parts[-5]  # e.g. "databricks-skills"
            skill_name = parts[-3]   # e.g. "databricks-lineage"
        except IndexError:
            print(f"WARN: unexpected path structure, skipping: {evals_path}", file=sys.stderr)
            continue

        try:
            entries = load_evals_json(evals_path)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            had_error = True
            continue

        positive = [e for e in entries if e["should_trigger"]]
        if not positive:
            print(f"WARN: no should_trigger:true entries in {evals_path}, skipping skill", file=sys.stderr)
            continue

        seen_names: set[str] = set()
        test_cases = [build_test_case(skill_name, e["query"], seen_names) for e in positive]

        if plugin_name not in per_plugin:
            per_plugin[plugin_name] = []
        per_plugin[plugin_name].extend(test_cases)

    if had_error:
        print("ERROR: one or more evals.json files failed to parse — aborting", file=sys.stderr)
        return 1

    # Write per-plugin YAMLs
    total_cases = 0
    for plugin_name, test_cases in sorted(per_plugin.items()):
        out_path = out_dir / f"{plugin_name}.yaml"
        header = f"# Generated by generate-routing-tests.py — do not edit manually\n# Source: plugins/{plugin_name}/skills/*/evals/evals.json\n\n"
        out_path.write_text(header + format_yaml_test_cases(test_cases))
        print(f"  wrote {out_path}  ({len(test_cases)} test cases)")
        total_cases += len(test_cases)

    # Write all.yaml (stitch all per-plugin entries)
    all_cases: list[dict] = []
    for plugin_name in sorted(per_plugin.keys()):
        all_cases.extend(per_plugin[plugin_name])

    all_path = out_dir / "all.yaml"
    header = "# Generated by generate-routing-tests.py — do not edit manually\n# Source: plugins/*/skills/*/evals/evals.json\n\n"
    all_path.write_text(header + format_yaml_test_cases(all_cases))
    print(f"  wrote {all_path}  ({len(all_cases)} test cases total)")

    skipped = [p for p in plugins_dir.glob("*/skills/*/evals/evals.json") if not any(True for _ in [p])]
    missing = [
        p for p in plugins_dir.glob("*/skills/*/")
        if (p / "SKILL.md").exists() and not (p / "evals" / "evals.json").exists()
    ]
    for m in missing:
        print(f"WARN: skipping {m} — missing evals/evals.json", file=sys.stderr)

    print(f"\nDone. {len(per_plugin)} plugin(s), {total_cases} test case(s) generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
