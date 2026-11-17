"""Scenario Simulation and Stress Testing Agent for StockShield 2.0.

Consumes verified market data, technical indicators, news sentiment, and baseline
risk assessments from the Blackboard to evaluate how hypothetical shocks affect
the stock's price, volatility, sentiment, and overall institutional risk profile.
"""

import time
from typing import Any, Dict, List, Optional

from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus
from stockshield.simulation.models import CustomScenarioInput, MonteCarloResult, ScenarioResult
from stockshield.simulation.monte_carlo import MonteCarloSimulator
from stockshield.simulation.simulation_engine import compute_baseline_metrics
from stockshield.simulation.stress_testing import StressTestingRunner


class ScenarioSimulationAgent:
    """Specialized agent executing deterministic stress testing and stochastic Monte Carlo paths."""

    def __init__(
        self,
        name: str = "ScenarioSimulationAgent",
        include_monte_carlo: bool = True,
        monte_carlo_simulations: int = 1000,
        monte_carlo_horizon_days: int = 20,
        random_seed: int = 42,
    ):
        self.name = name
        self.runner = StressTestingRunner()
        self.include_monte_carlo = include_monte_carlo
        self.mc_simulator = MonteCarloSimulator(
            num_simulations=monte_carlo_simulations,
            horizon_days=monte_carlo_horizon_days,
            random_seed=random_seed,
        )

    async def execute(
        self,
        blackboard: BlackboardManager,
        custom_scenarios: Optional[List[CustomScenarioInput]] = None,
        predefined_scenario_names: Optional[List[str]] = None,
        include_mc: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Execute scenario simulation battery on the Blackboard state.

        Parameters:
            blackboard: Shared Blackboard manager.
            custom_scenarios: Optional user-supplied custom scenarios.
            predefined_scenario_names: Optional filter to run specific predefined scenarios.
            include_mc: Explicit flag overriding default Monte Carlo execution.

        Returns:
            Execution summary dictionary with status, duration, and scenario statistics.
        """
        start_time = time.perf_counter()
        await blackboard.log_event(
            component=self.name,
            event_type="agent_start",
            status="running",
            details={"type": "scenario_simulation_and_stress_testing"},
        )

        state = await blackboard.get_state_snapshot()
        ticker = state.ticker
        market_data = state.market_data

        # -------------------------------------------------------------
        # Prerequisite Validation
        # -------------------------------------------------------------
        if market_data.status != FindingStatus.AVAILABLE or not market_data.bars:
            duration_ms = (time.perf_counter() - start_time) * 1000
            notes = "Scenario simulation unavailable: market data observations missing."
            await blackboard.update_scenario_simulation(
                producer=self.name,
                status=FindingStatus.UNAVAILABLE,
                notes=notes,
            )
            await blackboard.log_event(
                component=self.name,
                event_type="agent_complete",
                status="unavailable",
                details={"duration_ms": duration_ms, "reason": notes},
            )
            return {"status": "unavailable", "duration_ms": duration_ms, "error": notes}

        # -------------------------------------------------------------
        # 1. Compute Ground-Truth Baseline
        # -------------------------------------------------------------
        baseline, historical_peak, inds_dict = compute_baseline_metrics(state)

        # -------------------------------------------------------------
        # 2. Run Stress Scenario Battery
        # -------------------------------------------------------------
        scenarios: List[ScenarioResult]
        worst_case: Optional[ScenarioResult]
        best_case: Optional[ScenarioResult]
        flips: List[str]
        material_increases: List[str]

        scenarios, worst_case, best_case, flips, material_increases = self.runner.run_scenarios(
            baseline=baseline,
            historical_peak=historical_peak,
            predefined_names=predefined_scenario_names,
            custom_inputs=custom_scenarios,
        )

        # -------------------------------------------------------------
        # 3. Optional Monte Carlo Price Path Simulation
        # -------------------------------------------------------------
        run_mc = self.include_monte_carlo if include_mc is None else include_mc
        mc_result: Optional[MonteCarloResult] = None
        if run_mc:
            closes = [float(b.close) for b in market_data.bars]
            time_horizon = getattr(state, "time_horizon", "short_term")
            mc_days = 20
            if time_horizon == "mid_term":
                mc_days = 63
            elif time_horizon == "long_term":
                mc_days = 252

            sim = MonteCarloSimulator(
                num_simulations=self.mc_simulator.num_simulations,
                horizon_days=mc_days,
                random_seed=self.mc_simulator.random_seed,
            )
            mc_result = sim.simulate(closes)

        # -------------------------------------------------------------
        # 4. Synthesize Warnings & Findings
        # -------------------------------------------------------------
        warnings: List[str] = []
        if worst_case and worst_case.simulated.scenario_recommendation == "REJECTED_HIGH_RISK":
            warnings.append(
                f"Worst-case scenario '{worst_case.scenario_name}' yields risk score "
                f"{worst_case.simulated.scenario_risk_score:.3f} ({worst_case.simulated.scenario_recommendation})."
            )

        if flips:
            warnings.append(
                f"{len(flips)} stress scenario(s) flip institutional recommendation: {', '.join(flips[:3])}."
            )

        if material_increases:
            warnings.append(
                f"{len(material_increases)} scenario(s) cause material risk increase (delta >= +0.15)."
            )

        # -------------------------------------------------------------
        # 5. Atomic Publication to Blackboard
        # -------------------------------------------------------------
        duration_ms = (time.perf_counter() - start_time) * 1000

        await blackboard.update_scenario_simulation(
            producer=self.name,
            baseline_price=baseline.stock_price,
            baseline_volatility_pct=baseline.volatility_pct,
            baseline_sentiment_score=baseline.news_sentiment_score,
            baseline_risk_score=baseline.composite_risk_score,
            baseline_risk_level=baseline.risk_level,
            baseline_recommendation=baseline.recommendation,
            scenarios=scenarios,
            worst_case_scenario=worst_case,
            best_case_scenario=best_case,
            scenarios_changing_recommendation=flips,
            scenarios_material_risk_increase=material_increases,
            monte_carlo_result=mc_result,
            warnings=warnings,
            status=FindingStatus.AVAILABLE,
            notes=(
                f"Evaluated {len(scenarios)} stress scenarios for {ticker}. "
                f"Worst-case: {worst_case.scenario_name if worst_case else 'N/A'} "
                f"(score: {worst_case.simulated.scenario_risk_score if worst_case else 0.0:.3f})."
            ),
        )

        await blackboard.log_event(
            component=self.name,
            event_type="agent_complete",
            status="completed",
            details={
                "duration_ms": duration_ms,
                "scenarios_evaluated": len(scenarios),
                "worst_case_scenario": worst_case.scenario_name if worst_case else None,
                "worst_case_score": worst_case.simulated.scenario_risk_score if worst_case else None,
                "recommendation_flips_count": len(flips),
                "has_monte_carlo": mc_result is not None,
            },
        )

        return {
            "status": "completed",
            "duration_ms": duration_ms,
            "scenarios_evaluated": len(scenarios),
            "worst_case_scenario": worst_case.scenario_name if worst_case else None,
            "worst_case_score": worst_case.simulated.scenario_risk_score if worst_case else None,
            "recommendation_flips": flips,
            "material_risk_increases": material_increases,
            "monte_carlo_simulated": mc_result is not None,
        }

