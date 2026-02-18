from dataclasses import dataclass
from typing import Optional


@dataclass
class TestCase:
    name: str
    prompt: str
    expected_skill: Optional[str] = None  # Single skill (legacy)
    expected_skills: Optional[list[str]] = None  # Multiple skills (AND logic)
    expected_skill_one_of: Optional[list[str]] = None  # Any of these (OR logic)
    max_turns: int = 5  # Number of turns to check for skill invocations
    model: Optional[str] = None  # Model to use: haiku, sonnet, opus


@dataclass
class TestResult:
    name: str
    passed: bool
    expected: str
    actual: Optional[str]
    error: Optional[str] = None
