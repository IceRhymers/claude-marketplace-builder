.DEFAULT_GOAL := help

APP_DIR   := app
FE_DIR    := $(APP_DIR)/frontend
TARGET    ?= dev

# ── Frontend ─────────────────────────────────────────────────────────────

.PHONY: fe-install
fe-install: ## Install frontend dependencies
	cd $(FE_DIR) && pnpm install

.PHONY: fe-dev
fe-dev: ## Start frontend dev server (Vite)
	cd $(FE_DIR) && pnpm dev

.PHONY: fe-build
fe-build: ## Build frontend for production
	cd $(FE_DIR) && pnpm build

.PHONY: fe-test
fe-test: ## Run frontend vitest suite
	cd $(FE_DIR) && pnpm test:run

.PHONY: fe-typecheck
fe-typecheck: ## Run TypeScript type checking (no emit)
	cd $(FE_DIR) && pnpm exec tsc --noEmit

# ── Backend ──────────────────────────────────────────────────────────────

.PHONY: backend-install
backend-install: ## Install backend Python dependencies via uv
	cd $(APP_DIR) && uv sync --all-groups

.PHONY: serve
serve: ## Run the FastAPI backend locally with uvicorn
	cd $(APP_DIR) && uv run uvicorn main:app --reload --port 8000

.PHONY: test
test: ## Run backend pytest suite
	cd $(APP_DIR) && uv run pytest

.PHONY: test-unit
test-unit: ## Run only unit tests
	cd $(APP_DIR) && uv run pytest tests/unit/

.PHONY: test-integration
test-integration: ## Run integration tests
	cd $(APP_DIR) && uv run pytest tests/integration/

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	cd $(APP_DIR) && uv run pytest --cov=core --cov=routers --cov-report=term-missing

# ── Artifact ─────────────────────────────────────────────────────────────

.PHONY: build-artifact
build-artifact: ## Build versioned skill artifact (VERSION required)
	bash scripts/build-artifact.sh $(VERSION)

.PHONY: test-artifact
test-artifact: ## Run artifact build script tests
	bash scripts/test-build-artifact.sh

# ── Deploy ───────────────────────────────────────────────────────────────

.PHONY: deploy
deploy: fe-build ## Build frontend then deploy
	databricks bundle deploy --target $(TARGET)

.PHONY: start
start: ## Start the Databricks app compute
	databricks bundle run --target $(TARGET)

# ── Combined ─────────────────────────────────────────────────────────────

.PHONY: install
install: backend-install fe-install ## Install all dependencies (backend + frontend)

.PHONY: check
check: fe-typecheck test fe-test ## Run all checks

# ── Help ─────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
