#!/usr/bin/env python3
"""
Claude Code Skill Invocation Eval Runner

Usage:
    uv run skill-evals [test-cases/skill-routing.yaml]
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import yaml

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)
from claude_agent_sdk.types import ToolUseBlock

from .models import TestCase, TestResult

logger = logging.getLogger("skill-evals")

# evals/ directory
EVALS_DIR = Path(__file__).resolve().parent.parent.parent

# Repository root (parent of evals/)
REPO_ROOT = EVALS_DIR.parent


async def run_prompt_and_collect_skills(
    prompt: str,
    max_turns: int = 5,
    model: str | None = None,
) -> tuple[list[str], list[dict], dict]:
    """Run a prompt via Agent SDK, return (skills_invoked, tool_calls, result_info)."""
    logger.debug("Building ClaudeAgentOptions: plugins=%s, max_turns=%d, model=%s, cwd=%s",
                 REPO_ROOT, max_turns, model, REPO_ROOT)
    options = ClaudeAgentOptions(
        plugins=[{"type": "local", "path": str(REPO_ROOT)}],
        allowed_tools=["Skill", "Read", "Glob", "Grep", "Bash"],
        permission_mode="bypassPermissions",
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": "Never ask clarifying questions. Invoke skills directly.",
        },
        setting_sources=["project"],
        max_turns=max_turns,
        model=model,
        cwd=str(REPO_ROOT),
    )

    skills_invoked: list[str] = []
    tool_calls: list[dict] = []
    result_info: dict = {}

    logger.debug("Starting query: %.120s", prompt)
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    tool_calls.append({"tool": block.name, "input": block.input})
                    logger.debug("ToolUseBlock: %s  input=%s", block.name,
                                 json.dumps(block.input)[:200])
                    if block.name == "Skill":
                        skill_name = block.input.get("skill", "")
                        if skill_name:
                            skills_invoked.append(skill_name)
                            logger.debug("Skill invoked: %s", skill_name)

        elif isinstance(message, ResultMessage):
            result_info = {
                "session_id": message.session_id,
                "total_cost_usd": message.total_cost_usd,
                "num_turns": message.num_turns,
                "is_error": message.is_error,
                "duration_ms": message.duration_ms,
                "result": message.result,
            }
            logger.debug("ResultMessage: session=%s turns=%s cost=$%s error=%s duration=%sms",
                         message.session_id, message.num_turns,
                         message.total_cost_usd, message.is_error, message.duration_ms)

    logger.debug("Query complete: skills_invoked=%s", skills_invoked)
    return skills_invoked, tool_calls, result_info


async def run_test(test: TestCase, timeout: int = 180) -> TestResult:
    """Run a single test case and return result."""
    logger.debug("[%s] Starting test: prompt=%.120s", test.name, test.prompt)

    try:
        skills_invoked, tool_calls, result_info = await asyncio.wait_for(
            run_prompt_and_collect_skills(
                test.prompt,
                max_turns=test.max_turns,
                model=test.model,
            ),
            timeout=timeout,
        )

        logger.debug("[%s] Session ID: %s", test.name, result_info.get("session_id", "N/A"))
        logger.debug("[%s] Num turns: %s", test.name, result_info.get("num_turns", "N/A"))
        logger.debug("[%s] Is error: %s", test.name, result_info.get("is_error", "N/A"))
        logger.debug("[%s] Cost: $%.4f", test.name, result_info.get("total_cost_usd") or 0)
        logger.debug("[%s] Duration: %sms", test.name, result_info.get("duration_ms", "N/A"))

        result_text = result_info.get("result", "")
        if result_text:
            logger.debug("[%s] Result preview: %.1000s", test.name, result_text)

        if tool_calls:
            logger.debug("[%s] Tool calls (%d):", test.name, len(tool_calls))
            for tc in tool_calls:
                logger.debug("[%s]   - %s: %s", test.name, tc["tool"],
                             json.dumps(tc["input"])[:200])
        else:
            logger.debug("[%s] Tool calls: (none)", test.name)

        invoked = skills_invoked[: test.max_turns]
        invoked_set = set(invoked)

    except asyncio.TimeoutError:
        logger.debug("[%s] Timed out after %ds", test.name, timeout)
        return TestResult(
            name=test.name,
            passed=False,
            expected="completion",
            actual="timeout",
            error=f"Timed out after {timeout}s",
        )
    except Exception as e:
        logger.debug("[%s] Exception: %s", test.name, e, exc_info=True)
        return TestResult(
            name=test.name,
            passed=False,
            expected="completion",
            actual="error",
            error=str(e),
        )

    def skill_matches(expected: str, invoked_skills: set[str]) -> bool:
        """Check if expected skill matches any invoked skill.

        Handles both prefixed (plugin:skill) and unprefixed (skill) names.
        """
        if expected in invoked_skills:
            return True
        expected_name = expected.split(":")[-1] if ":" in expected else expected
        for inv in invoked_skills:
            inv_name = inv.split(":")[-1] if ":" in inv else inv
            if expected_name == inv_name:
                return True
        return False

    # Evaluate result
    if test.expected_skills:
        passed = all(skill_matches(exp, invoked_set) for exp in test.expected_skills)
        expected = f"all of {test.expected_skills}"
    elif test.expected_skill_one_of:
        passed = any(skill_matches(exp, invoked_set) for exp in test.expected_skill_one_of)
        expected = f"one of {test.expected_skill_one_of}"
    elif test.expected_skill:
        passed = skill_matches(test.expected_skill, invoked_set)
        expected = test.expected_skill
    else:
        passed = len(invoked) == 0
        expected = "null"

    actual_display = ", ".join(invoked) if invoked else "null"
    logger.debug("[%s] Evaluation: passed=%s expected='%s' actual='%s'",
                 test.name, passed, expected, actual_display)

    return TestResult(
        name=test.name,
        passed=passed,
        expected=expected,
        actual=actual_display,
    )


async def run_and_report(tests: list[TestCase], args: argparse.Namespace) -> None:
    """Run all tests and print summary."""
    logger.debug("Running %d tests (parallel=%d, timeout=%d)", len(tests), args.parallel, args.timeout)
    results: list[TestResult] = []
    parallel = args.parallel

    def print_result(result: TestResult) -> None:
        status = "PASS" if result.passed else "FAIL"
        print(f"  {result.name}: {status}")

    if parallel > 1:
        print(f"Running {len(tests)} tests with {parallel} workers...")
        semaphore = asyncio.Semaphore(parallel)

        async def bounded(test: TestCase) -> TestResult:
            async with semaphore:
                return await run_test(test, timeout=args.timeout)

        completed = await asyncio.gather(
            *[bounded(t) for t in tests], return_exceptions=True
        )

        for i, result in enumerate(completed):
            if isinstance(result, BaseException):
                err_result = TestResult(
                    name=tests[i].name,
                    passed=False,
                    expected="completion",
                    actual="error",
                    error=str(result),
                )
                results.append(err_result)
                print(f"  {tests[i].name}: ERROR - {result}")
            else:
                results.append(result)
                print_result(result)
    else:
        for test in tests:
            print(f"Running: {test.name}...", flush=True)
            result = await run_test(test, timeout=args.timeout)
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"  {status}")

    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    pass_percentage = (passed / total * 100) if total > 0 else 0
    passed_threshold = pass_percentage >= 95.0

    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} passed ({pass_percentage:.1f}%)")

    if passed < total:
        failed_tests = [r for r in results if not r.passed]

        if passed_threshold:
            print(f"\nPASSED with warnings (>= 95% threshold met)")
            print(f"\nWarning: {len(failed_tests)} test(s) failed but within acceptable threshold:")
        else:
            print(f"\nFAILED ({pass_percentage:.1f}% < 95% threshold)")
            print("\nFailed tests:")

        for r in failed_tests:
            print(f"  - {r.name}: expected '{r.expected}', got '{r.actual}'")
            if r.error:
                print(f"    Error: {r.error}")
    else:
        print(f"\nAll tests passed!")

    sys.exit(0 if passed_threshold else 1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Eval suite for Claude Code skill invocation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  skill-evals                              Run default test cases
  skill-evals test-cases/edge-cases.yaml   Run specific test file
  skill-evals --timeout 120                Run with longer timeout
  skill-evals -j 15                        Run 15 tests in parallel
  skill-evals -f update-skills             Run only matching tests
        """,
    )
    parser.add_argument(
        "test_file",
        nargs="?",
        default="test-cases/skill-routing.yaml",
        help="Path to test case YAML file (default: test-cases/skill-routing.yaml)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Timeout in seconds for each test (default: 180)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output for debugging",
    )
    parser.add_argument(
        "-j",
        "--parallel",
        type=int,
        default=15,
        help="Number of tests to run in parallel (default: 15)",
    )
    parser.add_argument(
        "--filter",
        "-f",
        type=str,
        default=None,
        help="Only run tests whose name contains this string",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load test cases — resolve relative to evals/ dir
    test_file = Path(args.test_file)
    if not test_file.is_absolute():
        test_file = EVALS_DIR / test_file

    with open(test_file) as f:
        suite = yaml.safe_load(f)

    tests = [TestCase(**t) for t in suite["tests"]]

    if args.filter:
        tests = [t for t in tests if args.filter in t.name]
        if not tests:
            print(f"No tests match filter: {args.filter}")
            sys.exit(1)

    asyncio.run(run_and_report(tests, args))


if __name__ == "__main__":
    main()
