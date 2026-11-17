"""Pydantic v2 structured domain models for the Forecasting Agent in StockShield 2.0.

Re-exports core forecasting models defined in stockshield.blackboard.models.
"""

from typing import List

from pydantic import BaseModel, Field

from stockshield.blackboard.models import (
    ForecastingState,
    ForecastModelResult,
    ForecastPoint,
    ModelEvaluationMetrics,
)


class ForecastingResult(BaseModel):
    """Payload returned by the Forecasting Agent after model execution and selection."""

    ticker: str
    latest_observed_close: float
    latest_observed_date: str
    selected_model_name: str
    selection_reason: str
    selected_forecasts: List[ForecastPoint]
    model_results: dict[str, ForecastModelResult] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


__all__ = [
    "ForecastPoint",
    "ModelEvaluationMetrics",
    "ForecastModelResult",
    "ForecastingState",
    "ForecastingResult",
]
