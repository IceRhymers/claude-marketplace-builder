---
name: update-pricing
description: >
  Refresh the static pricing table in usage-limits/app/core/pricing.py with current
  Databricks pay-per-token model rates. Use when new models are added, pricing changes,
  or coverage needs expanding beyond Claude to GPT, Gemini, Llama, etc.
user-invocable: true
allowed-tools: Read, Bash, Grep, Glob, Write, Edit
---

# Update Pricing

Refreshes the per-token pricing data used by the usage-limits app to calculate dollar costs.

## Prerequisites

- Chrome DevTools MCP configured (for scraping the pricing page)
- Databricks CLI authenticated (for discovering workspace models)
- SQL warehouse ID available (via `SQL_WAREHOUSE_ID` env var or user input)

## Workflow

### Step 1: Scrape current pricing

Use Chrome DevTools MCP to extract per-token rates from **two** Databricks pricing pages:

**Page 1 — Proprietary models** (Claude, GPT, Gemini):
1. Navigate to `https://www.databricks.com/product/pricing/proprietary-foundation-model-serving`
2. Wait for the DBU rates table to render
3. Use the "Select model vendor" dropdown to cycle through: **OpenAI**, **Anthropic**, **Google**
4. For each vendor, take a snapshot and extract: model name, Input DBU/1M tokens, Output DBU/1M tokens
5. Use Global endpoint and Short Context rates as the default

**Page 2 — Open-source models** (Llama, Gemma, GPT OSS):
1. Navigate to `https://www.databricks.com/product/pricing/foundation-model-serving`
2. The DBU rates table is at the bottom — extract Input/Output DBU/1M tokens per model
3. Skip models with "n/a" pay-per-token rates (PT-only or embedding-only)

**Convert rates**: DBU/1M tokens → DBU/token = value / 1,000,000
**Normalize names**: Add `databricks-` prefix, lowercase, spaces to hyphens (use `normalize_model_name()` from `scripts/scrape_pricing.py`)

### Step 2: Discover workspace models

Run the discovery script to find all pay-per-token models in use:

```bash
cd .claude/skills/update-pricing
python scripts/discover_models.py --warehouse-id <WAREHOUSE_ID>
```

This outputs JSON with `discovered_models`, `available_endpoints`, `models_with_pricing`, and `models_missing_pricing`.

### Step 3: Review gaps

Present any `models_missing_pricing` to the user. For each:
- Check if pricing was found in the scrape (Step 1)
- If not, ask the user for manual input or mark as $0 cost

### Step 4: Generate updated code

Option A — Use the generator script:
```bash
python scripts/generate_pricing.py > /tmp/pricing_preview.py
```

Option B — Manually update `references/pricing_reference.py` with new rates, then regenerate.

### Step 5: Apply

Write the generated code to `usage-limits/app/core/pricing.py`.

### Step 6: Update reference

Ensure `references/pricing_reference.py` reflects all current rates:
```bash
python scripts/generate_pricing.py --update-reference scraped_data.json
```

### Step 7: Update tests

If new model families were added, update `test_pricing_cte_contains_non_claude_models` in `usage-limits/app/tests/unit/test_pricing.py` to assert the new models are present.

### Step 8: Verify

```bash
cd usage-limits && make test
```

All tests must pass.

## Key Files

| File | Purpose |
|------|---------|
| `usage-limits/app/core/pricing.py` | Production pricing CTE + query |
| `references/pricing_reference.py` | Source of truth for per-token rates |
| `scripts/discover_models.py` | Find models in the workspace |
| `scripts/scrape_pricing.py` | Scraping helpers + documentation |
| `scripts/generate_pricing.py` | Code generation from reference data |
| `usage-limits/app/tests/unit/test_pricing.py` | Pricing unit tests |
