# DEPRECATED: This package is deprecated in favor of claude-marketplace-evaluator (cme).
# Use `uvx claude-marketplace-evaluator` for coverage checks and overlap detection.
# This code is preserved for reference and will be removed in a future cleanup (see issue #23).

from .models import TestCase, TestResult

__all__ = ["TestCase", "TestResult"]
