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
	icerhymers-specialized-tools \
	icerhymers-databricks-mcp \
	icerhymers-databricks-otel \
	icerhymers-budget-checker

MARKETPLACE := icerhymers-marketplace

# Overridable variables
APP       ?= usage-limits ## Databricks app name for test targets (default: usage-limits)
SKILL     ?=           ## Path to a single skill dir (default: all)
FILTER    ?=           ## Eval name filter substring (default: none)
PLUGIN    ?=           ## Plugin name for scoped evals, e.g. PLUGIN=databricks-skills (default: all)
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

## Run skill routing evals (uses all.yaml by default; set PLUGIN=<name> to scope to one plugin)
## NOTE: Run 'make evals-generate' first if you have modified any evals/evals.json files.
evals:
ifeq ($(PLUGIN),)
	@test -f evals/test-cases/all.yaml || (echo "ERROR: evals/test-cases/all.yaml not found — run 'make evals-generate' first" && exit 1)
	cd evals && uv run skill-evals \
		-f evals/test-cases/all.yaml \
		-j $(WORKERS) \
		--timeout $(TIMEOUT) \
		--threshold $(THRESHOLD) \
		--max-retries $(RETRIES) \
		$(if $(FILTER),--filter $(FILTER))
else
	@test -f evals/test-cases/$(PLUGIN).yaml || (echo "ERROR: evals/test-cases/$(PLUGIN).yaml not found — run 'make evals-generate' or check PLUGIN name" && exit 1)
	cd evals && uv run skill-evals \
		-f evals/test-cases/$(PLUGIN).yaml \
		-j $(WORKERS) \
		--timeout $(TIMEOUT) \
		--threshold $(THRESHOLD) \
		--max-retries $(RETRIES) \
		$(if $(FILTER),--filter $(FILTER))
endif

## Generate routing test YAMLs from per-skill evals/evals.json files
evals-generate:
	python3 evals/scripts/generate-routing-tests.py \
		--plugins-dir plugins/ \
		--out-dir evals/test-cases/

## Check that generated routing test YAMLs are up-to-date (used in CI)
evals-check-generated:
	@tmpdir=$$(mktemp -d) && \
	python3 evals/scripts/generate-routing-tests.py --plugins-dir plugins/ --out-dir $$tmpdir 2>&1 && \
	diff_out=$$(diff -r --exclude="*.pyc" evals/test-cases/ $$tmpdir/ 2>&1) && \
	rm -rf $$tmpdir && \
	if [ -n "$$diff_out" ]; then \
		echo "ERROR: Generated routing YAMLs are stale. Run 'make evals-generate' and commit the result."; \
		echo "$$diff_out"; \
		exit 1; \
	else \
		echo "OK: Generated routing YAMLs are up-to-date."; \
	fi

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

## Configure OTEL telemetry export to Databricks
configure-otel:
	bash scripts/configure-otel.sh

## Remove inference backend configuration from settings.json
unconfigure:
	bash scripts/configure-inference.sh --uninstall

## Remove OTEL telemetry configuration from settings.json
unconfigure-otel:
	bash scripts/configure-otel.sh --uninstall

# ------------------------------------------------------------------------------
# Databricks App targets
# ------------------------------------------------------------------------------

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

.PHONY: help validate evals evals-generate evals-check-generated evals-install \
	install-local uninstall-local init configure configure-otel \
	unconfigure unconfigure-otel \
	app-install test-app test-app-coverage test-app-unit test-app-integration
