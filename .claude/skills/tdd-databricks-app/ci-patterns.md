# CI Patterns

Makefile targets, coverage configuration, and build verification for Databricks APX apps.

## Makefile Targets

Add to the project root `Makefile`:

```makefile
# ---------------------------------------------------------------------------
# APX App Testing
# ---------------------------------------------------------------------------

APP_DIR ?= usage-limits/app  ## Path to the APX app directory

## Run backend (Python) tests
test-backend:
	cd $(APP_DIR) && uv run pytest tests/ -v

## Run backend tests with coverage report
test-backend-coverage:
	cd $(APP_DIR) && uv run pytest tests/ --cov=core --cov-report=term-missing --cov-fail-under=80

## Run only backend unit tests (fast feedback)
test-backend-unit:
	cd $(APP_DIR) && uv run pytest tests/ -m unit -v

## Run only backend integration tests
test-backend-integration:
	cd $(APP_DIR) && uv run pytest tests/ -m integration -v

## Run frontend (React) tests
test-frontend:
	cd $(APP_DIR)/frontend && npx vitest run

## Run frontend tests with coverage
test-frontend-coverage:
	cd $(APP_DIR)/frontend && npx vitest run --coverage

## TypeScript type check (no emit)
type-check:
	cd $(APP_DIR)/frontend && npx tsc --noEmit

## Build frontend for production
build-frontend:
	cd $(APP_DIR)/frontend && npm run build

## Run all tests (backend + frontend)
test-all: test-backend test-frontend

## Full validation: tests + type check + build
validate: test-all type-check build-frontend
```

Add to `.PHONY`:
```makefile
.PHONY: test-backend test-backend-coverage test-backend-unit test-backend-integration test-frontend test-frontend-coverage type-check build-frontend test-all validate
```

## Backend Coverage Configuration

Add to the app's `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["core"]
branch = true
omit = [
    "tests/*",
    "setup/*",
    "frontend/*",
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

## Frontend Coverage Configuration

If using `@vitest/coverage-v8`, install it:

```bash
cd usage-limits/app/frontend && npm install -D @vitest/coverage-v8
```

Coverage is configured in `vite.config.ts` under the `test` key:

```ts
test: {
  // ...existing config...
  coverage: {
    provider: "v8",
    include: ["src/**/*.{ts,tsx}"],
    exclude: [
      "src/__tests__/**",
      "src/routeTree.gen.ts",
      "src/types/**",
      "src/components/ui/**",  // shadcn primitives -- not custom code
    ],
    thresholds: {
      statements: 70,
      branches: 70,
      functions: 70,
      lines: 70,
    },
  },
},
```

## Usage

```bash
# From repo root -- run all backend tests
make test-backend

# Backend with coverage enforcement
make test-backend-coverage

# Fast backend unit tests only
make test-backend-unit

# Frontend tests
make test-frontend

# Frontend with coverage
make test-frontend-coverage

# TypeScript validation
make type-check

# Build frontend (ensures production build works)
make build-frontend

# Run everything
make test-all

# Full validation pipeline (tests + types + build)
make validate
```
