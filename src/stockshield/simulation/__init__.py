"""StockShield 2.0 Scenario Simulation and Stress Testing Package."""

from stockshield.simulation.comparison import (
    format_baseline_summary_md,
    generate_scenario_comparison_table_md,
)
from stockshield.simulation.models import (
    BaselineMetrics,
    CustomScenarioInput,
    MonteCarloResult,
    ScenarioCategory,
    ScenarioComparison,
    ScenarioDefinition,
    ScenarioResult,
    ScenarioSimulationState,
    SimulatedMetrics,
    TechnicalTrendShock,
)
from stockshield.simulation.monte_carlo import MonteCarloSimulator
from stockshield.simulation.scenario_definitions import (
    PREDEFINED_SCENARIOS,
    get_combined_stress_scenarios,
    get_predefined_scenario_by_name,
    get_predefined_scenarios,
)
from stockshield.simulation.simulation_engine import (
    DeterministicSimulationEngine,
    compute_baseline_metrics,
)
from stockshield.simulation.stress_testing import StressTestingRunner
from stockshield.simulation.visualization import generate_scenario_risk_chart

__all__ = [
    "BaselineMetrics",
    "CustomScenarioInput",
    "DeterministicSimulationEngine",
    "MonteCarloResult",
    "MonteCarloSimulator",
    "PREDEFINED_SCENARIOS",
    "ScenarioCategory",
    "ScenarioComparison",
    "ScenarioDefinition",
    "ScenarioResult",
    "ScenarioSimulationState",
    "SimulatedMetrics",
    "StressTestingRunner",
    "TechnicalTrendShock",
    "compute_baseline_metrics",
    "format_baseline_summary_md",
    "generate_scenario_comparison_table_md",
    "generate_scenario_risk_chart",
    "get_combined_stress_scenarios",
    "get_predefined_scenario_by_name",
    "get_predefined_scenarios",
]
