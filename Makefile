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
	icerhymers-databricks-mcp

MARKETPLACE := icerhymers-marketplace

# Overridable variables
APP       ?= usage-limits ## Databricks app name for test targets (default: usage-limits)
SKILL     ?=           ## Path to a single skill dir (default: all)
FILTER    ?=           ## Eval name filter substring (default: none)
WORKERS   ?= 8         ## Parallel eval workers (default: 8)
TIMEOUT   ?= 180       ## Per-test timeout in seconds (default: 180)
THRESHOLD ?= 95        ## Minimum pass percentage (default: 95)
RETRIES   ?= 5         ## Max retries on rate limit (default: 5)
DEF       ?=           ## YAML definition path for uc-mcp commands
CONN      ?=           ## UC connection name for uc-mcp-introspect
CMD       ?=           ## MCP server command for uc-mcp-introspect

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

# ------------------------------------------------------------------------------
# UC MCP Server targets
# ------------------------------------------------------------------------------

## Install uc-mcp-server Python dependencies
uc-mcp-install:
	cd uc-mcp-server && uv sync

## Run uc-mcp-server tests (supports FILTER=)
uc-mcp-test:
	cd uc-mcp-server && uv run pytest -v $(if $(FILTER),-k $(FILTER))

## Run uc-mcp-server tests with coverage
uc-mcp-coverage:
	cd uc-mcp-server && uv run pytest --cov=uc_mcp --cov-report=term-missing -v $(if $(FILTER),-k $(FILTER))

## Validate a YAML definition (DEF=path)
uc-mcp-validate:
ifeq ($(DEF),)
	@echo "Usage: make uc-mcp-validate DEF=uc-mcp-server/definitions/slack.yaml" >&2 && exit 1
else
	cd uc-mcp-server && uv run uc-mcp validate $(DEF)
endif

## Build Databricks App bundle (DEF=path)
uc-mcp-build:
ifeq ($(DEF),)
	@echo "Usage: make uc-mcp-build DEF=uc-mcp-server/definitions/slack.yaml" >&2 && exit 1
else
	cd uc-mcp-server && bash build/build.sh $(DEF)
endif

## Generate Databricks App Bundle (DEF=path)
uc-mcp-app:
ifeq ($(DEF),)
	@echo "Usage: make uc-mcp-app DEF=uc-mcp-server/definitions/slack.yaml" >&2 && exit 1
else
	cd uc-mcp-server && uv run uc-mcp app $(DEF) $(if $(OUTPUT),-o $(OUTPUT))
endif

## Introspect MCP server (CMD=, CONN=)
uc-mcp-introspect:
ifeq ($(CMD),)
	@echo "Usage: make uc-mcp-introspect CMD='npx server' CONN=my_conn" >&2 && exit 1
else ifeq ($(CONN),)
	@echo "Usage: make uc-mcp-introspect CMD='npx server' CONN=my_conn" >&2 && exit 1
else
	cd uc-mcp-server && uv run uc-mcp introspect "$(CMD)" --connection $(CONN)
endif

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

.PHONY: help validate evals evals-install install-local uninstall-local init configure \
	uc-mcp-install uc-mcp-test uc-mcp-coverage uc-mcp-validate uc-mcp-build uc-mcp-app uc-mcp-introspect \
	app-install test-app test-app-coverage test-app-unit test-app-integration
