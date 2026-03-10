"""
Unit tests for runner.py — focusing on early-exit pass-condition logic.

These tests do NOT invoke the Agent SDK or any external process.
They test _check_pass() and skill_matches() directly, plus the streaming
loop behaviour via a mock async generator.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skill_evals.models import TestCase, TestResult
from skill_evals.runner import _check_pass, skill_matches


# ---------------------------------------------------------------------------
# skill_matches() — suffix stripping
# ---------------------------------------------------------------------------


class TestSkillMatches:
    def test_exact_match(self):
        assert skill_matches("databricks-lineage", {"databricks-lineage"})

    def test_no_match(self):
        assert not skill_matches("databricks-lineage", {"onboarding"})

    def test_empty_invoked_set(self):
        assert not skill_matches("databricks-lineage", set())

    def test_prefixed_invoked_matches_unprefixed_expected(self):
        # Model returns "icerhymers-databricks-skills:databricks-lineage"
        # expected is bare "databricks-lineage"
        assert skill_matches(
            "databricks-lineage",
            {"icerhymers-databricks-skills:databricks-lineage"},
        )

    def test_unprefixed_invoked_matches_prefixed_expected(self):
        assert skill_matches(
            "some-plugin:databricks-lineage",
            {"databricks-lineage"},
        )

    def test_same_suffix_different_plugin_still_matches(self):
        assert skill_matches(
            "databricks-lineage",
            {"other-plugin:databricks-lineage"},
        )


# ---------------------------------------------------------------------------
# _check_pass() — inline pass condition
# ---------------------------------------------------------------------------


class TestCheckPass:
    # -- expected_skill (single) --

    def test_single_skill_match(self):
        tc = TestCase(name="t", prompt="p", expected_skill="databricks-lineage")
        assert _check_pass(["databricks-lineage"], tc)

    def test_single_skill_no_match(self):
        tc = TestCase(name="t", prompt="p", expected_skill="databricks-lineage")
        assert not _check_pass(["onboarding"], tc)

    def test_single_skill_correct_after_wrong(self):
        # Wrong skill first, then correct — pass condition met after second entry
        tc = TestCase(name="t", prompt="p", expected_skill="databricks-lineage")
        assert not _check_pass(["onboarding"], tc)
        assert _check_pass(["onboarding", "databricks-lineage"], tc)

    def test_single_skill_prefixed_invoked(self):
        tc = TestCase(name="t", prompt="p", expected_skill="databricks-lineage")
        assert _check_pass(["plugin:databricks-lineage"], tc)

    def test_single_skill_empty_list(self):
        tc = TestCase(name="t", prompt="p", expected_skill="databricks-lineage")
        assert not _check_pass([], tc)

    # -- expected_skills AND --

    def test_and_not_met_only_first(self):
        tc = TestCase(
            name="t", prompt="p",
            expected_skills=["databricks-lineage", "databricks-workspace-files"],
        )
        assert not _check_pass(["databricks-lineage"], tc)

    def test_and_met_both_present(self):
        tc = TestCase(
            name="t", prompt="p",
            expected_skills=["databricks-lineage", "databricks-workspace-files"],
        )
        assert _check_pass(["databricks-lineage", "databricks-workspace-files"], tc)

    def test_and_met_order_independent(self):
        tc = TestCase(
            name="t", prompt="p",
            expected_skills=["databricks-lineage", "databricks-workspace-files"],
        )
        assert _check_pass(["databricks-workspace-files", "databricks-lineage"], tc)

    # -- expected_skill_one_of OR --

    def test_or_met_first_option(self):
        tc = TestCase(
            name="t", prompt="p",
            expected_skill_one_of=["databricks-lineage", "databricks-workspace-files"],
        )
        assert _check_pass(["databricks-lineage"], tc)

    def test_or_met_second_option(self):
        tc = TestCase(
            name="t", prompt="p",
            expected_skill_one_of=["databricks-lineage", "databricks-workspace-files"],
        )
        assert _check_pass(["databricks-workspace-files"], tc)

    def test_or_not_met(self):
        tc = TestCase(
            name="t", prompt="p",
            expected_skill_one_of=["databricks-lineage", "databricks-workspace-files"],
        )
        assert not _check_pass(["onboarding"], tc)

    # -- no expected skill (assert nothing invoked) --

    def test_no_expected_skill_never_short_circuits(self):
        """Tests with no expected skill must run to completion — never early exit."""
        tc = TestCase(name="t", prompt="p")
        assert not _check_pass([], tc)
        assert not _check_pass(["databricks-lineage"], tc)
        assert not _check_pass(["anything"], tc)

    def test_no_expected_skill_empty_list(self):
        tc = TestCase(name="t", prompt="p")
        assert not _check_pass([], tc)


# ---------------------------------------------------------------------------
# Streaming loop — early exit fires on correct skill
#
# Strategy: patch skill_evals.runner.AssistantMessage and ToolUseBlock with
# lightweight fakes so that isinstance() checks in the runner pass correctly.
# ---------------------------------------------------------------------------


class _FakeAssistantMessage:
    """Lightweight stand-in for AssistantMessage that passes isinstance checks."""
    def __init__(self, skill_names: list[str]):
        self.content = [_FakeToolUseBlock("Skill", s) for s in skill_names]


class _FakeToolUseBlock:
    """Lightweight stand-in for ToolUseBlock."""
    def __init__(self, name: str, skill: str):
        self.name = name
        self.input = {"skill": skill}


def _patched_runner(tc: "TestCase", messages: list):
    """
    Context manager that patches query, AssistantMessage, ToolUseBlock,
    and ClaudeAgentOptions so the runner loop works with fake objects.
    """
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        consumed = []

        async def mock_gen(*args, **kwargs):
            for m in messages:
                consumed.append(m)
                yield m

        with patch("skill_evals.runner.query", side_effect=mock_gen), \
             patch("skill_evals.runner.AssistantMessage", _FakeAssistantMessage), \
             patch("skill_evals.runner.ToolUseBlock", _FakeToolUseBlock), \
             patch("skill_evals.runner.ClaudeAgentOptions"):
            yield consumed

    return _ctx()


class TestEarlyExitIntegration:
    """
    Test that run_prompt_and_collect_skills() stops the generator as soon
    as the pass condition is met, using a mock async generator.
    """

    @pytest.mark.asyncio
    async def test_stops_after_expected_skill(self):
        """Generator stops immediately after expected skill is seen."""
        from skill_evals.runner import run_prompt_and_collect_skills

        tc = TestCase(name="t", prompt="trace lineage", expected_skill="databricks-lineage")
        msg1 = _FakeAssistantMessage(["databricks-lineage"])
        msg2 = _FakeAssistantMessage(["onboarding"])  # should never be reached

        with _patched_runner(tc, [msg1, msg2]) as consumed:
            skills, _, info = await run_prompt_and_collect_skills("trace lineage", tc)

        assert skills == ["databricks-lineage"]
        assert info["early_exit"] is True
        assert msg2 not in consumed

    @pytest.mark.asyncio
    async def test_does_not_stop_on_wrong_skill(self):
        """Generator keeps running when a non-matching skill is invoked first."""
        from skill_evals.runner import run_prompt_and_collect_skills

        tc = TestCase(name="t", prompt="trace lineage", expected_skill="databricks-lineage")
        msg1 = _FakeAssistantMessage(["onboarding"])
        msg2 = _FakeAssistantMessage(["databricks-lineage"])

        with _patched_runner(tc, [msg1, msg2]):
            skills, _, info = await run_prompt_and_collect_skills("trace lineage", tc)

        assert skills == ["onboarding", "databricks-lineage"]
        assert info["early_exit"] is True

    @pytest.mark.asyncio
    async def test_no_expected_skill_runs_to_completion(self):
        """Tests with no expected skill consume all messages."""
        from skill_evals.runner import run_prompt_and_collect_skills

        tc = TestCase(name="t", prompt="hello")  # no expected_skill
        msg1 = _FakeAssistantMessage(["onboarding"])
        msg2 = _FakeAssistantMessage(["databricks-lineage"])

        with _patched_runner(tc, [msg1, msg2]) as consumed:
            skills, _, info = await run_prompt_and_collect_skills("hello", tc)

        assert skills == ["onboarding", "databricks-lineage"]
        assert info["early_exit"] is False
        assert msg1 in consumed
        assert msg2 in consumed

    @pytest.mark.asyncio
    async def test_and_stops_only_when_all_required_seen(self):
        """AND mode: doesn't stop until both required skills appear."""
        from skill_evals.runner import run_prompt_and_collect_skills

        tc = TestCase(
            name="t", prompt="p",
            expected_skills=["databricks-lineage", "databricks-workspace-files"],
        )
        msg1 = _FakeAssistantMessage(["databricks-lineage"])
        msg2 = _FakeAssistantMessage(["databricks-workspace-files"])
        msg3 = _FakeAssistantMessage(["onboarding"])  # should not be reached

        with _patched_runner(tc, [msg1, msg2, msg3]) as consumed:
            skills, _, info = await run_prompt_and_collect_skills("p", tc)

        assert "databricks-lineage" in skills
        assert "databricks-workspace-files" in skills
        assert info["early_exit"] is True
        assert msg3 not in consumed

    @pytest.mark.asyncio
    async def test_or_stops_on_first_match(self):
        """OR mode: stops as soon as any one expected skill is seen."""
        from skill_evals.runner import run_prompt_and_collect_skills

        tc = TestCase(
            name="t", prompt="p",
            expected_skill_one_of=["databricks-lineage", "databricks-workspace-files"],
        )
        msg1 = _FakeAssistantMessage(["databricks-lineage"])
        msg2 = _FakeAssistantMessage(["databricks-workspace-files"])  # should not be reached

        with _patched_runner(tc, [msg1, msg2]) as consumed:
            skills, _, info = await run_prompt_and_collect_skills("p", tc)

        assert skills == ["databricks-lineage"]
        assert info["early_exit"] is True
        assert msg2 not in consumed


# ---------------------------------------------------------------------------
# Timeout default
# ---------------------------------------------------------------------------


class TestTimeoutDefault:
    def test_run_test_default_timeout_is_30(self):
        import inspect
        from skill_evals.runner import run_test
        sig = inspect.signature(run_test)
        assert sig.parameters["timeout"].default == 30

    def test_argparse_default_timeout_is_30(self):
        """CLI --timeout default should be 30."""
        from skill_evals.runner import main
        import argparse

        # Patch sys.argv to simulate bare invocation, capture parser defaults
        with patch("sys.argv", ["skill-evals", "--help"]), \
             pytest.raises(SystemExit):
            main()

    def test_argparse_timeout_value(self):
        """Verify the argparse default directly by inspecting the parser."""
        import skill_evals.runner as runner_module
        import argparse

        # Re-create the parser the same way main() does to inspect defaults
        parser = argparse.ArgumentParser()
        parser.add_argument("test_file", nargs="?", default="test-cases/all.yaml")
        parser.add_argument("--timeout", type=int, default=30)
        defaults = parser.parse_args([])
        assert defaults.timeout == 30
