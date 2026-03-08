"""Unit-test level conftest — mocks external dependencies unavailable in test environment."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Mock 'databricks' and 'databricks.sdk' before any test module is imported.
# These packages are not installed in the test environment.
# ---------------------------------------------------------------------------

# Create a mock databricks package hierarchy so that
# `from databricks.sdk import WorkspaceClient` succeeds.
if "databricks" not in sys.modules:
    databricks_mock = MagicMock()
    databricks_sdk_mock = MagicMock()
    databricks_mock.sdk = databricks_sdk_mock
    sys.modules["databricks"] = databricks_mock
    sys.modules["databricks.sdk"] = databricks_sdk_mock
    sys.modules["databricks.sdk.service"] = MagicMock()
    sys.modules["databricks.sdk.service.iam"] = MagicMock()
