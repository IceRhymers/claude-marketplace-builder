"""Reference pricing for Databricks pay-per-token models.

Updated: 2026-03-06
Source (proprietary): https://www.databricks.com/product/pricing/proprietary-foundation-model-serving
Source (open-source): https://www.databricks.com/product/pricing/foundation-model-serving

Keys are endpoint_name values from system.ai_gateway.usage.
Values are (dbu_per_input_token, dbu_per_output_token).
Rates use Global endpoint pricing and Short Context where applicable.
"""

PRICING: dict[str, tuple[float, float]] = {
    # Anthropic — Claude
    "databricks-claude-opus-4-6": (0.000071429, 0.000357143),
    "databricks-claude-opus-4-5": (0.000071429, 0.000357143),
    "databricks-claude-opus-4-1": (0.000214286, 0.001071429),
    "databricks-claude-opus-4": (0.000214286, 0.001071429),
    "databricks-claude-sonnet-4-6": (0.000042857, 0.000214286),
    "databricks-claude-sonnet-4-5": (0.000042857, 0.000214286),
    "databricks-claude-sonnet-4-1": (0.000042857, 0.000214286),
    "databricks-claude-sonnet-4": (0.000042857, 0.000214286),
    "databricks-claude-sonnet-3-7": (0.000042857, 0.000214286),
    "databricks-claude-haiku-4-5": (0.000014286, 0.000071429),
    # OpenAI — GPT
    "databricks-gpt-5-2": (0.000025000, 0.000200000),
    "databricks-gpt-5-1": (0.000017857, 0.000142857),
    "databricks-gpt-5-1-codex-max": (0.000017857, 0.000142857),
    "databricks-gpt-5": (0.000017857, 0.000142857),
    "databricks-gpt-5-mini": (0.000003571, 0.000028571),
    "databricks-gpt-5-1-codex-mini": (0.000003571, 0.000028571),
    "databricks-gpt-5-nano": (0.000000714, 0.000005714),
    # Google — Gemini
    "databricks-gemini-3-0-pro": (0.000035714, 0.000214286),
    "databricks-gemini-3-1-pro": (0.000035714, 0.000214286),
    "databricks-gemini-3-0-flash": (0.000008929, 0.000053571),
    "databricks-gemini-2-5-pro": (0.000017857, 0.000142857),
    "databricks-gemini-2-5-flash": (0.000004286, 0.000035714),
    # Open-source — Llama
    "databricks-llama-4-maverick": (0.000007143, 0.000021429),
    "databricks-llama-3-3-70b": (0.000007143, 0.000021429),
    "databricks-llama-3-1-8b": (0.000002143, 0.000006429),
    # Open-source — GPT OSS
    "databricks-gpt-oss-120b": (0.000002143, 0.000008571),
    "databricks-gpt-oss-20b": (0.000001000, 0.000004286),
    # Open-source — Gemma
    "databricks-gemma-3-12b": (0.000002143, 0.000007143),
}
