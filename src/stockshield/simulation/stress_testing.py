"""Stress Testing and Sensitivity Battery Orchestration for StockShield 2.0.

Executes predefined and custom scenario simulation batteries, evaluates portfolio sensitivity,
and identifies worst-case capital drawdown and institutional recommendation transitions.
"""

from typing import List, Optional, Tuple

from stockshield.simulation.models import (
    BaselineMetrics,
    CustomScenarioInput,
    ScenarioDefinition,
    ScenarioResult,
)
from stockshield.simulation.scenario_definitions import (
    PREDEFINED_SCENARIOS,
    get_combined_stress_scenarios,
    get_predefined_scenario_by_name,
)
from stockshield.simulation.simulation_engine import DeterministicSimulationEngine


class StressTestingRunner:
    """Orchestrates comprehensive stress testing suites against baseline market states."""

    def __init__(self, engine: Optional[DeterministicSimulationEngine] = None):
        self.engine = engine or DeterministicSimulationEngine()

    def run_scenarios(
        self,
        baseline: BaselineMetrics,
        historical_peak: float,
        predefined_names: Optional[List[str]] = None,
        custom_inputs: Optional[List[CustomScenarioInput]] = None,
    ) -> Tuple[List[ScenarioResult], Optional[ScenarioResult], Optional[ScenarioResult], List[str], List[str]]:
        """Execute a battery of stress tests against the baseline.

        Returns:
            (results, worst_case_scenario, best_case_scenario, scenarios_flipping_rec, scenarios_material_risk)
        """
        results: List[ScenarioResult] = []
        definitions_to_run: List[ScenarioDefinition] = []

        if predefined_names:
            for name in predefined_names:
                scen = get_predefined_scenario_by_name(name)
                if scen:
                    definitions_to_run.append(scen)
        else:
            # Default: run all 23 predefined scenarios
            definitions_to_run = list(PREDEFINED_SCENARIOS)

        # Execute predefined scenarios
        for defn in definitions_to_run:
            inp = CustomScenarioInput(
                name=defn.name,
                category=defn.category,
                description=defn.description,
                price_shock_pct=defn.price_shock_pct,
                volatility_shock_pct=defn.volatility_shock_pct,
                sentiment_score=defn.sentiment_score,
                technical_trend=defn.technical_trend,
            )
            res = self.engine.simulate(inp, baseline, historical_peak)
            results.append(res)

        # Execute custom scenarios if provided
        if custom_inputs:
            for cust_inp in custom_inputs:
                res = self.engine.simulate(cust_inp, baseline, historical_peak)
                results.append(res)

        # Identify Worst-Case Scenario (highest simulated risk score)
        worst_case = None
        best_case = None
        if results:
            worst_case = max(results, key=lambda r: (r.simulated.scenario_risk_score, -r.simulated.hypothetical_price))
            best_case = min(results, key=lambda r: (r.simulated.scenario_risk_score, -r.simulated.hypothetical_price))

        # Identify recommendation flips and material risk increases
        scenarios_flipping_rec = [
            r.scenario_name for r in results if r.comparison.recommendation_changed
        ]
        scenarios_material_risk = [
            r.scenario_name for r in results if r.comparison.material_risk_increase
        ]

        return results, worst_case, best_case, scenarios_flipping_rec, scenarios_material_risk

    def run_combined_stress_only(
        self,
        baseline: BaselineMetrics,
        historical_peak: float,
    ) -> List[ScenarioResult]:
        """Convenience method to execute only the 5 combined market stress scenarios."""
        combined_defs = get_combined_stress_scenarios()
        results: List[ScenarioResult] = []
        for defn in combined_defs:
            inp = CustomScenarioInput(
                name=defn.name,
                category=defn.category,
                description=defn.description,
                price_shock_pct=defn.price_shock_pct,
                volatility_shock_pct=defn.volatility_shock_pct,
                sentiment_score=defn.sentiment_score,
                technical_trend=defn.technical_trend,
            )
            results.append(self.engine.simulate(inp, baseline, historical_peak))
        return results

