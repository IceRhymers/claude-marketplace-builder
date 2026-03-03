# CI Patterns

Makefile targets, coverage configuration, and pre-commit hooks for Databricks app testing.

## Makefile Targets

Add to the project root `Makefile`:

```makefile
# Overridable variable
APP ?= usage-limits  ## Databricks app name for test targets (default: usage-limits)

## Run Databricks app unit tests
test-app:
	cd plugins/databricks-skills/skills/$(APP)/app && python -m pytest tests/ -v

## Run app tests with coverage report
test-app-coverage:
	cd plugins/databricks-skills/skills/$(APP)/app && python -m pytest tests/ --cov=core --cov-report=term-missing --cov-fail-under=80

## Run only unit tests (fast feedback)
test-app-unit:
	cd plugins/databricks-skills/skills/$(APP)/app && python -m pytest tests/ -m unit -v

## Run only integration tests
test-app-integration:
	cd plugins/databricks-skills/skills/$(APP)/app && python -m pytest tests/ -m integration -v
```

Add to `.PHONY`:
```makefile
.PHONY: test-app test-app-coverage test-app-unit test-app-integration
```

## Coverage Configuration

Add to the app's `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["core"]
branch = true
omit = [
    "tests/*",
    "pages/*",
    "setup/*",
]

[tool.coverage.report]
show_missing = true
fail_under = 80
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.",
    "if TYPE_CHECKING:",
]
```

## Usage

```bash
# From repo root — run all tests for the usage-limits app
make test-app

# Run with coverage enforcement
make test-app-coverage

# Fast unit tests only
make test-app-unit

# Test a different app
make test-app APP=my-other-app
```
