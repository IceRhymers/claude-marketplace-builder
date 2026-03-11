#!/usr/bin/env python3
"""
Claude Code Skill Invocation Eval Runner

Usage:
    uv run skill-evals [test-cases/all.yaml]
"""

import argparse
import asyncio
import json
import logging
import random
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


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Check if an exception is a rate limit error from the CLI subprocess."""
    return "rate_limit" in str(exc).lower()


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


def _check_pass(skills_invoked: list[str], test: TestCase) -> bool:
    """Return True if the pass condition is already satisfied by the current invoked list.

    Returns False for tests with no expected skill — those can only be confirmed
    at the end of the run (pass = nothing was invoked).
    """
    if not skills_invoked:
        return False

    invoked_set = set(skills_invoked)

    if test.expected_skills:
        # AND: all required skills must have appeared
        return all(skill_matches(exp, invoked_set) for exp in test.expected_skills)
    elif test.expected_skill_one_of:
        # OR: any one of the listed skills is sufficient
        return any(skill_matches(exp, invoked_set) for exp in test.expected_skill_one_of)
    elif test.expected_skill:
        # Single skill match
        return skill_matches(test.expected_skill, invoked_set)
    else:
        # No expected skill — cannot short-circuit, must run to completion
        return False


async def run_prompt_and_collect_skills(
    prompt: str,
    test: TestCase,
    max_retries: int = 5,
) -> tuple[list[str], list[dict], dict]:
    """Run a prompt via Agent SDK, return (skills_invoked, tool_calls, result_info).

    Stops streaming as soon as the pass condition for `test` is satisfied —
    i.e., the expected skill(s) have been invoked. The skill's own workflow
    never executes for passing routing evals.

    For tests with no expected skill, the full conversation runs to completion.
    """
    logger.debug("Building ClaudeAgentOptions: plugins=%s, max_turns=%d, model=%s, cwd=%s",
                 REPO_ROOT, test.max_turns, test.model, REPO_ROOT)
    stderr_lines: list[str] = []

    def capture_stderr(line: str) -> None:
        stderr_lines.append(line)
        logger.debug("CLI stderr: %s", line.rstrip())

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
        max_turns=test.max_turns,
        model=test.model,
        cwd=str(REPO_ROOT),
        stderr=capture_stderr,
    )

    for attempt in range(max_retries + 1):
        try:
            skills_invoked: list[str] = []
            tool_calls: list[dict] = []
            result_info: dict = {}
            _pass_met = False

            logger.debug("Starting query (attempt %d/%d): %.120s",
                         attempt + 1, max_retries + 1, prompt)

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
                                    # Check pass condition inline — stop as soon as it's met
                                    if _check_pass(skills_invoked, test):
                                        logger.debug(
                                            "Pass condition met after invoking '%s' — stopping early",
                                            skill_name,
                                        )
                                        _pass_met = True
                                        break  # exit inner block loop

                    if _pass_met:
                        break  # exit outer async-for, closes the generator

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

            logger.debug("Query complete: skills_invoked=%s early_exit=%s",
                         skills_invoked, _pass_met)
            result_info["stderr"] = "".join(stderr_lines)
            result_info["early_exit"] = _pass_met
            return skills_invoked, tool_calls, result_info

        except Exception as exc:
            if _is_rate_limit_error(exc) and attempt < max_retries:
                delay = (2 ** attempt) + random.uniform(0, 1)
                logger.warning("Rate limit hit (attempt %d/%d), retrying in %.1fs...",
                               attempt + 1, max_retries + 1, delay)
                stderr_lines.clear()
                await asyncio.sleep(delay)
            else:
                raise

    # Unreachable, but satisfies type checker
    raise RuntimeError("Exhausted retries")


async def run_test(test: TestCase, timeout: int = 30, max_retries: int = 5) -> TestResult:
    """Run a single test case and return result."""
    logger.debug("[%s] Starting test: prompt=%.120s", test.name, test.prompt)

    result_info: dict = {}

    try:
        skills_invoked, tool_calls, result_info = await asyncio.wait_for(
            run_prompt_and_collect_skills(
                test.prompt,
                test=test,
                max_retries=max_retries,
            ),
            timeout=timeout,
        )

        logger.debug("[%s] Session ID: %s", test.name, result_info.get("session_id", "N/A"))
        logger.debug("[%s] Num turns: %s", test.name, result_info.get("num_turns", "N/A"))
        logger.debug("[%s] Is error: %s", test.name, result_info.get("is_error", "N/A"))
        logger.debug("[%s] Cost: $%.4f", test.name, result_info.get("total_cost_usd") or 0)
        logger.debug("[%s] Duration: %sms", test.name, result_info.get("duration_ms", "N/A"))
        logger.debug("[%s] Early exit: %s", test.name, result_info.get("early_exit", False))

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
        stderr = result_info.get("stderr", "")
        logger.debug("[%s] Exception: %s", test.name, e, exc_info=True)
        if stderr:
            logger.debug("[%s] CLI stderr:\n%s", test.name, stderr)
        error_msg = str(e)
        if stderr:
            error_msg = f"{error_msg}\nstderr: {stderr.strip()}"
        return TestResult(
            name=test.name,
            passed=False,
            expected="completion",
            actual="error",
            error=error_msg,
        )

    # Evaluate result — early exit means pass condition was already confirmed inline;
    # we still compute passed here for consistency (it will always be True on early exit).
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
                return await run_test(test, timeout=args.timeout, max_retries=args.max_retries)

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
            result = await run_test(test, timeout=args.timeout, max_retries=args.max_retries)
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"  {status}")

    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    pass_percentage = (passed / total * 100) if total > 0 else 0
    threshold = args.threshold
    passed_threshold = pass_percentage >= threshold

    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} passed ({pass_percentage:.1f}%)")

    if passed < total:
        failed_tests = [r for r in results if not r.passed]

        if passed_threshold:
            print(f"\nPASSED with warnings (>= {threshold}% threshold met)")
            print(f"\nWarning: {len(failed_tests)} test(s) failed but within acceptable threshold:")
        else:
            print(f"\nFAILED ({pass_percentage:.1f}% < {threshold}% threshold)")
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
  skill-evals test-cases/all.yaml          Run specific test file
  skill-evals --timeout 60                 Run with custom timeout
  skill-evals -j 15                        Run 15 tests in parallel
  skill-evals -f update-skills             Run only matching tests
  skill-evals --threshold 80               Pass if >= 80% of tests pass
        """,
    )
    parser.add_argument(
        "test_file",
        nargs="?",
        default="test-cases/all.yaml",
        help="Path to test case YAML file (default: test-cases/all.yaml)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds for each test (default: 30 — passing tests exit after one turn)",
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
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Max retries on rate limit errors (default: 5)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=95.0,
        help="Minimum pass percentage to exit 0 (default: 95.0)",
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

    loop = asyncio.new_event_loop()

    def _exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        # Suppress the benign RuntimeError thrown by anyio when we break out of
        # the SDK's async generator early (early-exit optimisation).  The error
        # occurs because anyio's cancel scope is exited from a different task
        # than the one that entered it, but tests still pass correctly.
        if isinstance(exc, RuntimeError) and "cancel scope" in str(exc):
            return
        loop.default_exception_handler(context)

    loop.set_exception_handler(_exception_handler)
    try:
        loop.run_until_complete(run_and_report(tests, args))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
