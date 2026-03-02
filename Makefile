# ==============================================================================
# Claude Code Skills Marketplace — Makefile
#
# Run `make` or `make help` to see available targets.
# ==============================================================================

# Plugin install names (update when adding a new plugin)
PLUGINS := \
	icerhymers-databricks-skills \
	icerhymers-internal-skills \
	icerhymers-marketplace-management \
	icerhymers-specialized-tools

MARKETPLACE := icerhymers-marketplace

# Overridable variables
APP       ?= usage-limits ## Databricks app name for test targets (default: usage-limits)
SKILL     ?=           ## Path to a single skill dir (default: all)
FILTER    ?=           ## Eval name filter substring (default: none)
WORKERS   ?= 8         ## Parallel eval workers (default: 8)
TIMEOUT   ?= 180       ## Per-test timeout in seconds (default: 180)
THRESHOLD ?= 95        ## Minimum pass percentage (default: 95)
RETRIES   ?= 5         ## Max retries on rate limit (default: 5)

# Auto-source inference config if it exists
INFERENCE_ENV := config/inference.env
ifneq (,$(wildcard $(INFERENCE_ENV)))
include $(INFERENCE_ENV)
export
endif

.DEFAULT_GOAL := help

# ------------------------------------------------------------------------------
# Targets
# ------------------------------------------------------------------------------

## Show available targets and variables
help:
	@echo "Usage: make <target> [VAR=value ...]"
	@echo ""
	@echo "Targets:"
	@awk '/^## /{desc=$$0; next} /^[a-zA-Z_-]+:/{gsub(/:.*/, "", $$1); gsub(/^## /, "", desc); printf "  %-20s %s\n", $$1, desc}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Variables (override with VAR=value):"
	@awk '/^[A-Z_]+ +\?=/{split($$0,a,"## "); gsub(/\?=.*/, "", $$1); printf "  %-20s %s\n", $$1, a[2]}' $(MAKEFILE_LIST)

## Validate skill structure and frontmatter
validate:
ifeq ($(SKILL),)
	bash scripts/validate-skill.sh --all
else
	bash scripts/validate-skill.sh $(SKILL)
endif

## Run skill routing evals
evals:
	cd evals && uv run skill-evals \
		-j $(WORKERS) \
		--timeout $(TIMEOUT) \
		--threshold $(THRESHOLD) \
		--max-retries $(RETRIES) \
		$(if $(FILTER),-f $(FILTER))

## Install eval Python dependencies
evals-install:
	cd evals && uv sync

## Register marketplace and install all plugins locally
install-local:
	claude plugin marketplace add .
	@for p in $(PLUGINS); do \
		echo "Installing $$p..."; \
		claude plugin install $$p@$(MARKETPLACE); \
	done

## Uninstall all plugins and remove marketplace
uninstall-local:
	@for p in $(PLUGINS); do \
		echo "Uninstalling $$p..."; \
		claude plugin uninstall $$p@$(MARKETPLACE) || true; \
	done
	claude plugin marketplace remove $(MARKETPLACE) || true

## First-time repo initialization
init:
	bash scripts/init.sh

## Configure inference backend (Databricks, Anthropic, Bedrock, Vertex, custom)
configure:
	bash scripts/configure-inference.sh

## Install app Python dependencies (uv sync)
app-install:
	cd $(APP)/app && uv sync

## Run Databricks app tests
test-app:
	cd $(APP)/app && uv run pytest tests/ -v

## Run app tests with coverage report
test-app-coverage:
	cd $(APP)/app && uv run pytest tests/ --cov=core --cov-report=term-missing --cov-fail-under=80

## Run only app unit tests (fast feedback)
test-app-unit:
	cd $(APP)/app && uv run pytest tests/ -m unit -v

## Run only app integration tests
test-app-integration:
	cd $(APP)/app && uv run pytest tests/ -m integration -v

.PHONY: help validate evals evals-install install-local uninstall-local init configure app-install test-app test-app-coverage test-app-unit test-app-integration
