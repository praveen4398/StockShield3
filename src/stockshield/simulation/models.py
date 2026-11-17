"""Pydantic domain models for Scenario Simulation and Stress Testing in StockShield 2.0.

Provides immutable schemas for hypothetical market shocks, baseline-versus-scenario
comparisons, deterministic stress testing results, and Monte Carlo price path simulations.
Re-exports core state models defined in stockshield.blackboard.models.
"""

from typing import List, Optional

from pydantic import BaseModel

from stockshield.blackboard.models import (
    BaselineMetrics,
    CustomScenarioInput,
    FindingStatus,
    MonteCarloResult,
    ScenarioCategory,
    ScenarioComparison,
    ScenarioResult,
    ScenarioSimulationState,
    SimulatedMetrics,
    TechnicalTrendShock,
)


class ScenarioDefinition(BaseModel):
    """Specification of a standardized or predefined stress scenario."""

    name: str
    category: ScenarioCategory
    description: str
    price_shock_pct: float = 0.0
    volatility_shock_pct: float = 0.0
    sentiment_score: Optional[float] = None
    technical_trend: TechnicalTrendShock = TechnicalTrendShock.NONE


class ScenarioSimulationResult(BaseModel):
    """Structured response container for scenario simulation execution."""

    ticker: str
    baseline: BaselineMetrics
    total_scenarios_evaluated: int
    scenarios: List[ScenarioResult]
    worst_case_scenario: Optional[ScenarioResult] = None
    best_case_scenario: Optional[ScenarioResult] = None
    scenarios_changing_recommendation: List[str]
    scenarios_material_risk_increase: List[str]
    monte_carlo_result: Optional[MonteCarloResult] = None
    warnings: List[str]


__all__ = [
    "BaselineMetrics",
    "CustomScenarioInput",
    "FindingStatus",
    "MonteCarloResult",
    "ScenarioCategory",
    "ScenarioComparison",
    "ScenarioDefinition",
    "ScenarioResult",
    "ScenarioSimulationResult",
    "ScenarioSimulationState",
    "SimulatedMetrics",
    "TechnicalTrendShock",
]
