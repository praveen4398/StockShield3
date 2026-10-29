"""Token usage and pricing model estimator for StockShield 2.0."""

import math

from pydantic import BaseModel

# Verified vendor rate table (v2025.1): Gemini 1.5 Flash
# Input: $0.075 per 1M tokens ($0.000000075 / token)
# Output: $0.30 per 1M tokens ($0.00000030 / token)
PRICE_TABLE_VERSION = "2025.1-gemini-flash"
RATE_INPUT_PER_MILLION = 0.075
RATE_OUTPUT_PER_MILLION = 0.30


class CostEstimate(BaseModel):
    model_name: str
    price_table_version: str = PRICE_TABLE_VERSION
    estimated_input_tokens: int
    estimated_output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    cost_status: str  # 'actual', 'estimated', 'zero_cost_stub'


def estimate_token_count(text: str) -> int:
    """Heuristic approximation: ~4 characters per token for English text and JSON."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4.0))


def compute_cost(
    input_text: str,
    output_text: str,
    model_name: str = "gemini-1.5-flash",
    is_stub: bool = True,
) -> CostEstimate:
    """Compute token counts and projected API expenditure."""
    in_tokens = estimate_token_count(input_text)
    out_tokens = estimate_token_count(output_text)
    tot_tokens = in_tokens + out_tokens

    # Standard commercial pricing calculation
    in_cost = (in_tokens / 1_000_000.0) * RATE_INPUT_PER_MILLION
    out_cost = (out_tokens / 1_000_000.0) * RATE_OUTPUT_PER_MILLION
    total_cost = in_cost + out_cost

    cost_status = "zero_cost_stub" if is_stub else "estimated"
    # If stub, API charge is 0.0, but projected commercial cost is retained for benchmarking
    reported_cost = 0.0 if is_stub else round(total_cost, 6)

    return CostEstimate(
        model_name=model_name,
        price_table_version=PRICE_TABLE_VERSION,
        estimated_input_tokens=in_tokens,
        estimated_output_tokens=out_tokens,
        total_tokens=tot_tokens,
        input_cost_usd=round(in_cost, 6),
        output_cost_usd=round(out_cost, 6),
        total_cost_usd=reported_cost,
        cost_status=cost_status,
    )
