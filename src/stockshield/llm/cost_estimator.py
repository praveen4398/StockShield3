"""Token usage and pricing model estimator for StockShield 2.0."""

import math
from typing import Optional

from pydantic import BaseModel

PRICE_TABLE_VERSION = "2026.1-gemini-pricing"

# Verified vendor rate table ($ per million tokens)
# Only models with published, verified institutional rates are listed here.
MODEL_PRICING_TABLE = {
    "gemini-1.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-2.0-flash": {"input_per_million": 0.10, "output_per_million": 0.40},
}


class CostEstimate(BaseModel):
    model_name: str
    price_table_version: str = PRICE_TABLE_VERSION
    estimated_input_tokens: int
    estimated_output_tokens: int
    total_tokens: int
    input_cost_usd: Optional[float] = None
    output_cost_usd: Optional[float] = None
    total_cost_usd: Optional[float] = None
    cost_status: str  # 'actual', 'estimated', 'zero_cost_stub', 'unavailable'


def estimate_token_count(text: str) -> int:
    """Heuristic approximation: ~4 characters per token for English text and JSON."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4.0))


def compute_cost(
    input_text: str = "",
    output_text: str = "",
    model_name: str = "gemini-3.8-flash",
    is_stub: bool = True,
    actual_input_tokens: Optional[int] = None,
    actual_output_tokens: Optional[int] = None,
) -> CostEstimate:
    """Compute token counts and projected API expenditure.

    If reliable model-specific pricing cannot be determined, cost fields return None (null).
    """
    in_tokens = actual_input_tokens if actual_input_tokens is not None else estimate_token_count(input_text)
    out_tokens = actual_output_tokens if actual_output_tokens is not None else estimate_token_count(output_text)
    tot_tokens = in_tokens + out_tokens

    if is_stub:
        return CostEstimate(
            model_name=model_name,
            price_table_version=PRICE_TABLE_VERSION,
            estimated_input_tokens=in_tokens,
            estimated_output_tokens=out_tokens,
            total_tokens=tot_tokens,
            input_cost_usd=0.0,
            output_cost_usd=0.0,
            total_cost_usd=0.0,
            cost_status="zero_cost_stub",
        )

    # Check if model has verified rate
    rates = MODEL_PRICING_TABLE.get(model_name)
    if rates is None:
        # If reliable cost cannot be determined for unverified/custom model, return None (null in JSON)
        return CostEstimate(
            model_name=model_name,
            price_table_version=PRICE_TABLE_VERSION,
            estimated_input_tokens=in_tokens,
            estimated_output_tokens=out_tokens,
            total_tokens=tot_tokens,
            input_cost_usd=None,
            output_cost_usd=None,
            total_cost_usd=None,
            cost_status="unavailable",
        )

    in_cost = (in_tokens / 1_000_000.0) * rates["input_per_million"]
    out_cost = (out_tokens / 1_000_000.0) * rates["output_per_million"]
    total_cost = round(in_cost + out_cost, 6)
    status = "actual" if (actual_input_tokens is not None and actual_output_tokens is not None) else "estimated"

    return CostEstimate(
        model_name=model_name,
        price_table_version=PRICE_TABLE_VERSION,
        estimated_input_tokens=in_tokens,
        estimated_output_tokens=out_tokens,
        total_tokens=tot_tokens,
        input_cost_usd=round(in_cost, 6),
        output_cost_usd=round(out_cost, 6),
        total_cost_usd=total_cost,
        cost_status=status,
    )
