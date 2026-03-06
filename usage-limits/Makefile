.DEFAULT_GOAL := help

APP_DIR   := app
FE_DIR    := $(APP_DIR)/frontend
TARGET    ?= dev

# ── Frontend ─────────────────────────────────────────────────────────────

.PHONY: fe-install
fe-install: ## Install frontend dependencies
	cd $(FE_DIR) && npm install

.PHONY: fe-dev
fe-dev: ## Start frontend dev server (Vite)
	cd $(FE_DIR) && npx vite

.PHONY: fe-build
fe-build: ## Build frontend for production
	cd $(FE_DIR) && npx tsc && npx vite build

.PHONY: fe-typecheck
fe-typecheck: ## Run TypeScript type checking (no emit)
	cd $(FE_DIR) && npx tsc --noEmit

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
	cd $(APP_DIR) && uv run pytest -m unit

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	cd $(APP_DIR) && uv run pytest --cov=core --cov=routers --cov-report=term-missing

# ── Deploy ───────────────────────────────────────────────────────────────

.PHONY: validate
validate: ## Validate the Databricks Asset Bundle
	bash scripts/deploy.sh validate --target $(TARGET)

.PHONY: deploy
deploy: fe-build ## Build frontend then full deploy (deploy → start → grant → app-deploy)
	bash scripts/deploy.sh full --target $(TARGET)

.PHONY: app-deploy
app-deploy: ## Deploy only the app source code (skip bundle deploy)
	bash scripts/deploy.sh app-deploy --target $(TARGET)

.PHONY: start
start: ## Start the Databricks app compute
	bash scripts/deploy.sh start --target $(TARGET)

.PHONY: stop
stop: ## Stop the Databricks app compute
	bash scripts/deploy.sh stop --target $(TARGET)

# ── Combined ─────────────────────────────────────────────────────────────

.PHONY: install
install: backend-install fe-install ## Install all dependencies (backend + frontend)

.PHONY: check
check: fe-typecheck test ## Run all checks (TypeScript + pytest)

# ── Help ─────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
