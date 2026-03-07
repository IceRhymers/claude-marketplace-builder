#!/usr/bin/env python3
"""Scrape Databricks Foundation Model Serving pricing via Chrome DevTools MCP.

This script is NOT run directly — it documents the extraction pattern that
Claude Code executes via Chrome DevTools MCP tool calls.

## Workflow (executed by Claude Code, not as a standalone script):

### Page 1 — Proprietary models (Claude, GPT, Gemini):
1. Navigate to: https://www.databricks.com/product/pricing/proprietary-foundation-model-serving
2. Wait for the DBU rates table to render (wait for "DBU" text)
3. Use the "Select model vendor" combobox to cycle through vendors:
   - OpenAI (selected by default)
   - Anthropic
   - Google
4. For each vendor, take_snapshot() and extract rows from the
   "Proprietary Foundation Model Serving DBU rates" table
5. Use Global endpoint and Short Context rates as the default

### Page 2 — Open-source models (Llama, Gemma, GPT OSS):
1. Navigate to: https://www.databricks.com/product/pricing/foundation-model-serving
2. Scroll to "Foundation Model Serving DBU rates" table
3. take_snapshot() and extract rows
4. Skip models with "n/a" pay-per-token rates

## DOM Structure (accessibility tree)

The DBU rates table renders as StaticText nodes in the a11y tree.
For proprietary models, the columns are:
- Model name, Endpoint type (Global/In-geo), Context Length,
  Input DBU/1M, Output DBU/1M, Cache writes, Cache reads, Batch DBU/hour

For open-source models, the columns are:
- Model name, Input DBU/1M, Output DBU/1M, PT entry DBU/hour, PT scaling DBU/hour

### Conversion:
- Page shows DBU per 1M tokens
- We need DBU per token: divide by 1,000,000
- Endpoint name: add "databricks-" prefix, lowercase, spaces to hyphens

## Output format (JSON to stdout):

```json
{
  "databricks-claude-sonnet-4": {
    "input_dbu_per_million": 42.857,
    "output_dbu_per_million": 214.286,
    "dbu_per_input_token": 0.000042857,
    "dbu_per_output_token": 0.000214286
  },
  ...
}
```
"""

import json
import sys


def parse_pricing_from_snapshot(snapshot_text: str) -> dict:
    """Parse pricing data from a Chrome DevTools accessibility snapshot.

    This is a helper for Claude Code to call after taking a snapshot
    of the pricing page. The snapshot_text is the accessibility tree text.

    Returns dict mapping endpoint_name -> pricing info.
    """
    # This function is intentionally a skeleton — Claude Code reads the
    # actual DOM snapshot and extracts data using its understanding of
    # the page structure. The function exists to document the expected
    # output format.
    raise NotImplementedError(
        "This function is a template. Use Chrome DevTools MCP to scrape "
        "the pricing page and parse the snapshot manually."
    )


def normalize_model_name(raw_name: str) -> str:
    """Convert a raw model name from the pricing page to endpoint_name format.

    Examples:
        "Claude Sonnet 4" -> "databricks-claude-sonnet-4"
        "GPT-4o"          -> "databricks-gpt-4o"
        "Llama 3.3 70B"   -> "databricks-llama-3-3-70b"
    """
    name = raw_name.strip().lower()
    name = name.replace(" ", "-")
    if not name.startswith("databricks-"):
        name = f"databricks-{name}"
    return name


def dbu_per_million_to_per_token(dbu_per_million: float) -> float:
    """Convert DBU/1M tokens to DBU/token."""
    return dbu_per_million / 1_000_000


if __name__ == "__main__":
    print(
        "This script documents the scraping pattern for Claude Code.\n"
        "Run it via the /update-pricing skill, which uses Chrome DevTools MCP.",
        file=sys.stderr,
    )
    sys.exit(1)
