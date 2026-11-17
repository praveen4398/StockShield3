"""Comprehensive test suite for StockShield 2.0 Scenario Simulation Agent.

Verifies the 25 core technical requirements:
1. Price shock calculations.
2. Positive price shock.
3. Negative price shock.
4. Volatility adjustment.
5. Sentiment scenario mapping.
6. Technical trend scenario handling.
7. Combined stress scenarios.
8. Custom scenario validation.
9. Invalid input rejection.
10. Baseline versus scenario comparison.
11. Worst-case scenario identification.
12. Recommendation change detection.
13. Pydantic schema validation.
14. Blackboard update and provenance.
15. Baseline state preservation.
16. Gate 8 integration.
17. Sequential workflow integration.
18. Parallel workflow integration.
19. Hierarchical workflow integration.
20. API /simulate endpoint validation.
21. API /analyze scenario integration.
22. Report generation Section 7 synthesis.
23. Security and prompt injection tests.
24. Missing upstream data handling.
25. Reproducibility of calculations.
26. Monte Carlo stochastic simulation.
27. Visualization chart generation.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from stockshield.agents.scenario_simulation_agent import ScenarioSimulationAgent
from stockshield.api.main import app
from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import (
    FindingStatus,
    OHLCVBar,
    WorkflowStatus,
)
from stockshield.orchestration.workflow import StockShieldWorkflow
from stockshield.risk.risk_engine import DeterministicRiskEngine
from stockshield.simulation.models import (
    BaselineMetrics,
    CustomScenarioInput,
    TechnicalTrendShock,
)
from stockshield.simulation.monte_carlo import MonteCarloSimulator
from stockshield.simulation.scenario_definitions import (
    get_combined_stress_scenarios,
)
from stockshield.simulation.simulation_engine import (
    DeterministicSimulationEngine,
)
from stockshield.simulation.stress_testing import StressTestingRunner
from stockshield.simulation.visualization import generate_scenario_risk_chart


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------
def _generate_synthetic_bars(n_bars: int = 100, base_price: float = 100.0) -> list[OHLCVBar]:
    """Deterministic synthetic market bars for testing."""
    bars = []
    current_price = base_price
    start_dt = pd.Timestamp("2024-01-01")
    trading_days = pd.bdate_range(start=start_dt, periods=n_bars)

    for i, date_val in enumerate(trading_days):
        date_str = date_val.strftime("%Y-%m-%d")
        step_return = 0.002 * np.sin(i / 5.0) + 0.0005
        close = round(current_price * (1.0 + step_return), 2)
        bars.append(
            OHLCVBar(
                timestamp=date_str,
                open=round(current_price, 2),
                high=round(close * 1.01, 2),
                low=round(close * 0.99, 2),
                close=close,
                adjusted_close=close,
                volume=100000,
            )
        )
        current_price = close
    return bars


@pytest.fixture
def sample_baseline() -> BaselineMetrics:
    return BaselineMetrics(
        stock_price=2000.0,
        volatility_pct=22.5,
        news_sentiment_score=0.15,
        news_sentiment_label="NEUTRAL",
        technical_signal="BULLISH",
        composite_risk_score=0.25,
        risk_level="LOW",
        recommendation="APPROVED",
    )


@pytest.fixture
def sim_engine() -> DeterministicSimulationEngine:
    return DeterministicSimulationEngine()


# ---------------------------------------------------------------------------
# 1. Price Shock Calculations
# ---------------------------------------------------------------------------
def test_price_shock_calculations(sim_engine, sample_baseline):
    """Verify formula: scenario_price = current_price * (1 + price_shock_pct / 100)."""
    inp = CustomScenarioInput(name="Test 5% Drop", price_shock_pct=-5.0)
    res = sim_engine.simulate(inp, sample_baseline, historical_peak=2100.0)

    # 2000 * (1 - 0.05) = 1900.0
    assert res.simulated.hypothetical_price == 1900.0
    assert res.simulated.absolute_price_change == -100.0
    assert res.simulated.percentage_price_change == -5.0


# ---------------------------------------------------------------------------
# 2. Positive Price Shock
# ---------------------------------------------------------------------------
def test_positive_price_shock(sim_engine, sample_baseline):
    """Verify positive price shocks of +5% and +10% and portfolio value gain."""
    inp5 = CustomScenarioInput(
        name="Gain 5%",
        price_shock_pct=5.0,
        portfolio_exposure_shares=100.0,
    )
    res5 = sim_engine.simulate(inp5, sample_baseline, historical_peak=2000.0)
    assert res5.simulated.hypothetical_price == 2100.0
    assert res5.simulated.portfolio_value_impact == 10000.0  # +100 * 100 shares

    inp10 = CustomScenarioInput(
        name="Gain 10%",
        price_shock_pct=10.0,
        portfolio_exposure_value=50000.0,
    )
    res10 = sim_engine.simulate(inp10, sample_baseline, historical_peak=2000.0)
    assert res10.simulated.hypothetical_price == 2200.0
    assert res10.simulated.portfolio_value_impact == 5000.0  # +10% of 50,000


# ---------------------------------------------------------------------------
# 3. Negative Price Shock
# ---------------------------------------------------------------------------
def test_negative_price_shock(sim_engine, sample_baseline):
    """Verify negative price shocks of -5%, -10%, and -15% expand drawdown."""
    for shock in [-5.0, -10.0, -15.0]:
        inp = CustomScenarioInput(name=f"Drop {abs(shock)}%", price_shock_pct=shock)
        res = sim_engine.simulate(inp, sample_baseline, historical_peak=2000.0)
        expected_p = round(2000.0 * (1.0 + shock / 100.0), 2)
        assert res.simulated.hypothetical_price == expected_p
        assert res.simulated.absolute_price_change < 0


# ---------------------------------------------------------------------------
# 4. Volatility Adjustment
# ---------------------------------------------------------------------------
def test_volatility_adjustment(sim_engine, sample_baseline):
    """Verify volatility expansion (+25%, +50%, +100% doubling) and contraction (-25%)."""
    # Baseline volatility is 22.5%
    inp_v25 = CustomScenarioInput(name="Vol +25%", volatility_shock_pct=25.0)
    res_v25 = sim_engine.simulate(inp_v25, sample_baseline, historical_peak=2000.0)
    assert res_v25.simulated.hypothetical_volatility_pct == round(22.5 * 1.25, 2)

    # Volatility doubling via 100% shock
    inp_v100 = CustomScenarioInput(name="Vol Doubling", volatility_shock_pct=100.0)
    res_v100 = sim_engine.simulate(inp_v100, sample_baseline, historical_peak=2000.0)
    assert res_v100.simulated.hypothetical_volatility_pct == 45.0

    # Volatility doubling via multiplier 2.0x
    inp_mult = CustomScenarioInput(name="Vol Multiplier", volatility_multiplier=2.0)
    res_mult = sim_engine.simulate(inp_mult, sample_baseline, historical_peak=2000.0)
    assert res_mult.simulated.hypothetical_volatility_pct == 45.0

    # Volatility contraction -25%
    inp_down = CustomScenarioInput(name="Vol -25%", volatility_shock_pct=-25.0)
    res_down = sim_engine.simulate(inp_down, sample_baseline, historical_peak=2000.0)
    assert res_down.simulated.hypothetical_volatility_pct == round(22.5 * 0.75, 2)


# ---------------------------------------------------------------------------
# 5. Sentiment Scenario Mapping
# ---------------------------------------------------------------------------
def test_sentiment_scenario_mapping(sim_engine, sample_baseline):
    """Verify hypothetical sentiment levels map accurately to POSITIVE, NEUTRAL, and NEGATIVE."""
    # Strongly positive
    res_pos = sim_engine.simulate(CustomScenarioInput(sentiment_score=0.80), sample_baseline, 2000.0)
    assert res_pos.simulated.hypothetical_sentiment_label == "POSITIVE"

    # Neutral
    res_neu = sim_engine.simulate(CustomScenarioInput(sentiment_score=0.0), sample_baseline, 2000.0)
    assert res_neu.simulated.hypothetical_sentiment_label == "NEUTRAL"

    # Moderately negative
    res_mneg = sim_engine.simulate(CustomScenarioInput(sentiment_score=-0.50), sample_baseline, 2000.0)
    assert res_mneg.simulated.hypothetical_sentiment_label == "NEGATIVE"

    # Strongly negative
    res_sneg = sim_engine.simulate(CustomScenarioInput(sentiment_score=-0.90), sample_baseline, 2000.0)
    assert res_sneg.simulated.hypothetical_sentiment_label == "NEGATIVE"
    assert res_sneg.simulated.scenario_risk_score > res_pos.simulated.scenario_risk_score


# ---------------------------------------------------------------------------
# 6. Technical Trend Scenario Handling
# ---------------------------------------------------------------------------
def test_technical_trend_scenario_handling(sim_engine, sample_baseline):
    """Verify technical trend transitions into moving average breakdowns and recoveries."""
    # Bullish to neutral
    r1 = sim_engine.simulate(
        CustomScenarioInput(technical_trend=TechnicalTrendShock.BULLISH_TO_NEUTRAL), sample_baseline, 2000.0
    )
    assert r1.simulated.hypothetical_technical_signal == "NEUTRAL"

    # Neutral to bearish
    r2 = sim_engine.simulate(
        CustomScenarioInput(technical_trend=TechnicalTrendShock.NEUTRAL_TO_BEARISH), sample_baseline, 2000.0
    )
    assert r2.simulated.hypothetical_technical_signal == "BEARISH"

    # Break below SMA-200
    r3 = sim_engine.simulate(
        CustomScenarioInput(technical_trend=TechnicalTrendShock.BREAK_BELOW_SMA200), sample_baseline, 2000.0
    )
    assert r3.simulated.hypothetical_technical_signal == "BEARISH"
    assert r3.simulated.scenario_risk_score >= 0.35  # Escalates risk

    # Bullish recovery
    r4 = sim_engine.simulate(
        CustomScenarioInput(technical_trend=TechnicalTrendShock.BULLISH_RECOVERY), sample_baseline, 2000.0
    )
    assert r4.simulated.hypothetical_technical_signal == "BULLISH"


# ---------------------------------------------------------------------------
# 7. Combined Market Stress Scenarios
# ---------------------------------------------------------------------------
def test_combined_stress_scenarios(sim_engine, sample_baseline):
    """Verify the 5 standard combined market stress scenarios."""
    combined_defs = get_combined_stress_scenarios()
    assert len(combined_defs) == 5

    names = [s.name for s in combined_defs]
    assert "Mild Correction" in names
    assert "Market Downturn" in names
    assert "Severe Market Crash" in names
    assert "Bullish Recovery" in names
    assert "High Volatility Without Price Decline" in names

    # Run Severe Market Crash
    crash_def = next(s for s in combined_defs if s.name == "Severe Market Crash")
    crash_inp = CustomScenarioInput(
        name=crash_def.name,
        price_shock_pct=crash_def.price_shock_pct,
        volatility_shock_pct=crash_def.volatility_shock_pct,
        sentiment_score=crash_def.sentiment_score,
        technical_trend=crash_def.technical_trend,
    )
    res_crash = sim_engine.simulate(crash_inp, sample_baseline, historical_peak=2000.0)

    # 15% drop on 2000 = 1700
    assert res_crash.simulated.hypothetical_price == 1700.0
    # Volatility doubles (22.5 * 2 = 45.0)
    assert res_crash.simulated.hypothetical_volatility_pct == 45.0
    # Risk escalated significantly
    assert res_crash.simulated.scenario_risk_score >= 0.65
    assert res_crash.simulated.scenario_recommendation == "REJECTED_HIGH_RISK"
    assert res_crash.comparison.material_risk_increase is True


# ---------------------------------------------------------------------------
# 8. Custom Scenario Validation
# ---------------------------------------------------------------------------
def test_custom_scenario_validation(sim_engine, sample_baseline):
    """Verify custom scenario input with price shock, vol shock, sentiment, and portfolio impact."""
    inp = CustomScenarioInput(
        name="Custom Regulatory Shock",
        price_shock_pct=-8.0,
        volatility_shock_pct=40.0,
        sentiment_score=-0.70,
        technical_trend=TechnicalTrendShock.NEUTRAL_TO_BEARISH,
        portfolio_exposure_shares=500.0,
    )
    res = sim_engine.simulate(inp, sample_baseline, historical_peak=2000.0)

    assert res.simulated.hypothetical_price == 1840.0
    assert res.simulated.portfolio_value_impact == -80000.0  # -160 * 500
    assert res.simulated.hypothetical_sentiment_score == -0.70
    assert res.simulated.hypothetical_technical_signal == "BEARISH"


# ---------------------------------------------------------------------------
# 9. Invalid Input Rejection
# ---------------------------------------------------------------------------
def test_invalid_input_rejection():
    """Verify Pydantic validation rejects out-of-bounds or malformed scenario inputs."""
    # Price shock < -90%
    with pytest.raises(ValidationError):
        CustomScenarioInput(price_shock_pct=-95.0)

    # Price shock > 200%
    with pytest.raises(ValidationError):
        CustomScenarioInput(price_shock_pct=250.0)

    # Volatility multiplier <= 0
    with pytest.raises(ValidationError):
        CustomScenarioInput(volatility_multiplier=-1.0)

    # Sentiment score > 1.0
    with pytest.raises(ValidationError):
        CustomScenarioInput(sentiment_score=1.5)


# ---------------------------------------------------------------------------
# 10. Baseline Versus Scenario Comparison
# ---------------------------------------------------------------------------
def test_baseline_versus_scenario_comparison(sim_engine, sample_baseline):
    """Verify delta calculation between scenario metrics and ground-truth baseline."""
    inp = CustomScenarioInput(name="Downturn", price_shock_pct=-10.0, sentiment_score=-0.80)
    res = sim_engine.simulate(inp, sample_baseline, historical_peak=2000.0)

    comp = res.comparison
    expected_delta = round(res.simulated.scenario_risk_score - sample_baseline.composite_risk_score, 3)
    assert comp.risk_score_delta == expected_delta
    assert comp.explanation != ""


# ---------------------------------------------------------------------------
# 11. Worst-Case Scenario Identification
# ---------------------------------------------------------------------------
def test_worst_case_scenario_identification(sample_baseline):
    """Verify runner correctly finds scenario with maximum risk score."""
    runner = StressTestingRunner()
    results, worst_case, best_case, flips, material = runner.run_scenarios(
        baseline=sample_baseline,
        historical_peak=2000.0,
        predefined_names=["Price Gain 10%", "Price Drop 5%", "Severe Market Crash"],
    )

    assert worst_case is not None
    assert worst_case.scenario_name == "Severe Market Crash"
    assert best_case is not None
    assert best_case.scenario_name == "Price Gain 10%"


# ---------------------------------------------------------------------------
# 12. Recommendation Change Detection
# ---------------------------------------------------------------------------
def test_recommendation_change_detection(sample_baseline):
    """Verify detection when scenario flips recommendation from APPROVED to REJECTED_HIGH_RISK."""
    runner = StressTestingRunner()
    # Baseline is APPROVED
    assert sample_baseline.recommendation == "APPROVED"

    results, worst_case, best_case, flips, material = runner.run_scenarios(
        baseline=sample_baseline,
        historical_peak=2000.0,
        predefined_names=["Severe Market Crash", "Price Gain 5%"],
    )

    assert "Severe Market Crash" in flips
    assert "Price Gain 5%" not in flips


# ---------------------------------------------------------------------------
# 13. Pydantic Schema Validation
# ---------------------------------------------------------------------------
def test_pydantic_schema_validation(sim_engine, sample_baseline):
    """Verify complete scenario models serialize cleanly via model_dump()."""
    inp = CustomScenarioInput(name="Pydantic Test", price_shock_pct=-5.0)
    res = sim_engine.simulate(inp, sample_baseline, historical_peak=2000.0)

    data = res.model_dump()
    assert data["scenario_name"] == "Pydantic Test"
    assert "baseline" in data
    assert "simulated" in data
    assert "comparison" in data
    assert data["simulated"]["hypothetical_price"] == 1900.0


# ---------------------------------------------------------------------------
# 14. Blackboard Update and Provenance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_blackboard_update_and_provenance(sample_baseline):
    """Verify atomic update to Blackboard and provenance logging."""
    blackboard = BlackboardManager(
        run_id="run_sim_test",
        trace_id="trace_sim_test",
        ticker="TCS.NS",
        user_prompt="Run scenario simulation test.",
    )

    runner = StressTestingRunner()
    scens, worst, best, flips, mat = runner.run_scenarios(sample_baseline, historical_peak=2000.0)

    await blackboard.update_scenario_simulation(
        producer="ScenarioSimulationAgent",
        baseline_price=sample_baseline.stock_price,
        baseline_risk_score=sample_baseline.composite_risk_score,
        scenarios=scens,
        worst_case_scenario=worst,
        status=FindingStatus.AVAILABLE,
    )

    state = blackboard.state
    assert state.scenario_simulation.status == FindingStatus.AVAILABLE
    assert state.scenario_simulation.total_scenarios_evaluated == len(scens)
    assert state.scenario_simulation.worst_case_scenario is not None

    # Provenance record check
    prov = [p for p in state.provenance_trail if p.field_name == "scenario_simulation"]
    assert len(prov) == 1
    assert prov[0].producer == "ScenarioSimulationAgent"


# ---------------------------------------------------------------------------
# 15. Baseline State Preservation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_baseline_state_preservation():
    """Verify scenario simulation NEVER mutates actual Market, Technical, News, or Baseline Risk states."""
    blackboard = BlackboardManager(
        run_id="run_preservation",
        trace_id="trace_preservation",
        ticker="TCS.NS",
        user_prompt="Preservation test.",
    )

    bars = [b.model_dump() for b in _generate_synthetic_bars(60, base_price=1500.0)]
    await blackboard.update_market_data(
        producer="test_provider",
        source="fixture",
        bars=bars,
        status=FindingStatus.AVAILABLE,
    )
    original_last_close = blackboard.state.market_data.bars[-1].close

    agent = ScenarioSimulationAgent()
    await agent.execute(blackboard)

    # Verify Market Data Close was NOT overwritten by hypothetical price
    assert blackboard.state.market_data.bars[-1].close == original_last_close
    assert len(blackboard.state.market_data.bars) == 60


# ---------------------------------------------------------------------------
# 16. Risk Engine Gate 8 Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_risk_engine_gate8_integration(sample_baseline):
    """Verify DeterministicRiskEngine Gate 8 evaluates scenario stress without diluting baseline risk."""
    blackboard = BlackboardManager(
        run_id="run_gate8_test",
        trace_id="trace_gate8_test",
        ticker="TCS.NS",
        user_prompt="Evaluate Gate 8.",
    )

    bars = [b.model_dump() for b in _generate_synthetic_bars(100, base_price=2000.0)]
    await blackboard.update_market_data(
        producer="test_provider",
        source="fixture",
        bars=bars,
        status=FindingStatus.AVAILABLE,
    )

    # 1. Run baseline risk engine
    risk_engine = DeterministicRiskEngine()
    risk_res = await risk_engine.execute(blackboard)
    assert risk_res["status"] == "completed"

    # Check Gate 8 deferred note prior to scenario simulation
    gate8_pre = next(c for c in risk_res["checks"] if c["name"] == "scenario_stress_testing")
    assert "pending or deferred" in gate8_pre["message"]

    # 2. Run Scenario Simulation Agent
    agent = ScenarioSimulationAgent()
    await agent.execute(blackboard)

    # 3. Re-evaluate Gate 8
    g8_res = await risk_engine.evaluate_gate_8(blackboard)
    assert g8_res["status"] == "completed"

    # Verify updated check
    state = blackboard.state
    gate8_post = next(c for c in state.risk_findings.checks if c.name == "scenario_stress_testing")
    assert "Worst-case stress scenario" in gate8_post.message


# ---------------------------------------------------------------------------
# 17. Sequential Workflow Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sequential_workflow_integration():
    """Verify Scenario Simulation executes in Sequential workflow topology."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "TCS.NS",
        "user_prompt": "Run sequential workflow with scenario simulation.",
        "lookback_days": 100,
        "workflow_mode": "sequential",
    }
    state = await workflow.run(raw_request=req, workflow_mode="sequential")

    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.scenario_simulation.status == FindingStatus.AVAILABLE
    assert state.scenario_simulation.total_scenarios_evaluated > 0

    # Verify execution event logged
    sim_events = [e for e in state.execution_events if e.get("component") == "ScenarioSimulationAgent"]
    assert len(sim_events) >= 2  # start and complete


# ---------------------------------------------------------------------------
# 18. Parallel Workflow Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_parallel_workflow_integration():
    """Verify Scenario Simulation executes after concurrent steps in Parallel workflow topology."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "INFY.NS",
        "user_prompt": "Run parallel workflow with scenario simulation.",
        "lookback_days": 100,
        "workflow_mode": "parallel",
    }
    state = await workflow.run(raw_request=req, workflow_mode="parallel")

    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.scenario_simulation.status == FindingStatus.AVAILABLE


# ---------------------------------------------------------------------------
# 19. Hierarchical Workflow Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hierarchical_workflow_integration():
    """Verify Scenario Simulation executes in Hierarchical workflow topology."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "RELIANCE.NS",
        "user_prompt": "Run hierarchical workflow with scenario simulation.",
        "lookback_days": 100,
        "workflow_mode": "hierarchical",
    }
    state = await workflow.run(raw_request=req, workflow_mode="hierarchical")

    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.scenario_simulation.status == FindingStatus.AVAILABLE


# ---------------------------------------------------------------------------
# 20. API /simulate Endpoint Validation
# ---------------------------------------------------------------------------
def test_api_simulate_endpoint():
    """Verify FastAPI POST /simulate endpoint returns structured comparison and 200 OK."""
    client = TestClient(app)
    payload = {
        "ticker": "TCS.NS",
        "user_prompt": "Simulate stress tests.",
        "lookback_days": 100,
        "predefined_scenarios": ["mild_correction", "severe_market_crash"],
        "custom_scenarios": [
            {
                "name": "Custom API Shock",
                "price_shock_pct": -7.5,
                "volatility_shock_pct": 30.0,
            }
        ],
        "include_monte_carlo": True,
    }

    response = client.post("/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["ticker"] == "TCS.NS"
    assert data["status"] == "available"
    assert data["total_scenarios_evaluated"] == 3
    assert data["worst_case_scenario"] is not None
    assert "monte_carlo" in data
    assert data["monte_carlo"]["num_simulations"] == 1000


# ---------------------------------------------------------------------------
# 21. API /analyze Scenario Inclusion
# ---------------------------------------------------------------------------
def test_api_analyze_scenario_inclusion():
    """Verify FastAPI POST /analyze endpoint includes scenario_simulation block."""
    client = TestClient(app)
    payload = {
        "ticker": "TCS.NS",
        "user_prompt": "Standard institutional review.",
        "lookback_days": 100,
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "scenario_simulation" in data
    assert data["scenario_simulation"]["status"] == "available"
    assert data["scenario_simulation"]["total_scenarios"] > 0


# ---------------------------------------------------------------------------
# 22. Report Generation Section 7 Synthesis
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_report_generation_section_7():
    """Verify Section 7 is generated in Markdown and structured_json."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "TCS.NS",
        "user_prompt": "Test report Section 7.",
        "lookback_days": 100,
    }
    state = await workflow.run(raw_request=req, workflow_mode="sequential")

    md = state.final_report.markdown_content
    assert "## 7. Scenario Simulation & Stress Testing Intelligence" in md
    assert "Worst-Case Stress Scenario:" in md
    assert "Comprehensive Scenario Stress Testing Matrix:" in md

    struct = state.final_report.structured_json
    assert "scenario_simulation" in struct
    assert struct["scenario_simulation"]["status"] == "available"
    assert struct["scenario_simulation"]["total_scenarios"] > 0


# ---------------------------------------------------------------------------
# 23. Security and Prompt Injection Tests
# ---------------------------------------------------------------------------
def test_security_and_prompt_injection():
    """Verify script tags or executable expressions are strictly rejected."""
    # Attempting <script> tag
    with pytest.raises(ValidationError):
        CustomScenarioInput(
            name="<script>alert(1)</script>",
            price_shock_pct=-5.0,
        )

    # Attempting eval expression
    with pytest.raises(ValidationError):
        CustomScenarioInput(
            name="Normal Name",
            description="eval(import('os').system('dir'))",
            price_shock_pct=-5.0,
        )


# ---------------------------------------------------------------------------
# 24. Missing Upstream Data Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_upstream_data_handling():
    """Verify graceful handling when market data bars are absent."""
    blackboard = BlackboardManager(
        run_id="run_missing",
        trace_id="trace_missing",
        ticker="EMPTY.NS",
        user_prompt="Missing bars test.",
    )

    agent = ScenarioSimulationAgent()
    res = await agent.execute(blackboard)

    assert res["status"] == "unavailable"
    assert blackboard.state.scenario_simulation.status == FindingStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# 25. Reproducibility of Calculations
# ---------------------------------------------------------------------------
def test_reproducibility_of_calculations(sim_engine, sample_baseline):
    """Verify deterministic calculations yield identical results on repeated calls."""
    inp = CustomScenarioInput(name="Deterministic Run", price_shock_pct=-10.0, volatility_shock_pct=50.0)

    res1 = sim_engine.simulate(inp, sample_baseline, historical_peak=2000.0)
    res2 = sim_engine.simulate(inp, sample_baseline, historical_peak=2000.0)

    assert res1.simulated.hypothetical_price == res2.simulated.hypothetical_price
    assert res1.simulated.scenario_risk_score == res2.simulated.scenario_risk_score
    assert res1.comparison.risk_score_delta == res2.comparison.risk_score_delta


# ---------------------------------------------------------------------------
# 26. Monte Carlo Stochastic Simulation
# ---------------------------------------------------------------------------
def test_monte_carlo_simulation():
    """Verify Monte Carlo percentiles order, loss probability, disclosures, and seed reproducibility."""
    closes = [float(b.close) for b in _generate_synthetic_bars(80, base_price=100.0)]

    sim1 = MonteCarloSimulator(num_simulations=500, horizon_days=15, random_seed=123)
    res1 = sim1.simulate(closes)

    # Check percentile monotonicity: P5 <= P25 <= Median <= P75 <= P95
    assert res1.percentile_5_price <= res1.percentile_25_price
    assert res1.percentile_25_price <= res1.median_terminal_price
    assert res1.median_terminal_price <= res1.percentile_75_price
    assert res1.percentile_75_price <= res1.percentile_95_price

    # Check loss probabilities within valid range
    assert 0.0 <= res1.probability_loss_pct <= 100.0
    assert 0.0 <= res1.probability_severe_loss_pct <= 100.0

    # Check reproducibility with identical seed
    sim2 = MonteCarloSimulator(num_simulations=500, horizon_days=15, random_seed=123)
    res2 = sim2.simulate(closes)
    assert res1.median_terminal_price == res2.median_terminal_price
    assert res1.percentile_5_price == res2.percentile_5_price

    # Disclosures present
    assert len(res1.assumptions_and_disclosures) >= 3


# ---------------------------------------------------------------------------
# 27. Visualization Chart Generation
# ---------------------------------------------------------------------------
def test_scenario_risk_chart_generation(sim_engine, sample_baseline, tmp_path):
    """Verify matplotlib horizontal bar chart is generated without GUI dependency."""
    inp1 = CustomScenarioInput(name="Drop 5%", price_shock_pct=-5.0)
    inp2 = CustomScenarioInput(name="Crash 15%", price_shock_pct=-15.0, volatility_shock_pct=100.0)

    res1 = sim_engine.simulate(inp1, sample_baseline, 2000.0)
    res2 = sim_engine.simulate(inp2, sample_baseline, 2000.0)

    out_file = str(tmp_path / "test_chart.png")
    chart_path = generate_scenario_risk_chart(
        scenarios=[res1, res2],
        baseline_risk_score=sample_baseline.composite_risk_score,
        ticker="TEST.NS",
        output_path=out_file,
    )

    assert chart_path is not None
    assert Path(chart_path).exists()
    assert Path(chart_path).stat().st_size > 1000  # Valid PNG image bytes written


# ---------------------------------------------------------------------------
# 28. Predefined Scenario Exact Count Reconciliation (23 Predefined vs 24 with Custom)
# ---------------------------------------------------------------------------
def test_predefined_scenario_exact_count_reconciliation(sample_baseline):
    """Reconcile exact scenario battery counts: 23 predefined, 23+K with custom scenarios."""
    from stockshield.simulation.scenario_definitions import PREDEFINED_SCENARIOS, ScenarioCategory

    # 1. Exact count of predefined scenarios is 23
    assert len(PREDEFINED_SCENARIOS) == 23

    # Breakdown by category
    counts = {}
    for s in PREDEFINED_SCENARIOS:
        counts[s.category] = counts.get(s.category, 0) + 1

    assert counts[ScenarioCategory.PRICE_SHOCK] == 5
    assert counts[ScenarioCategory.VOLATILITY_SHOCK] == 4
    assert counts[ScenarioCategory.NEWS_SENTIMENT] == 4
    assert counts[ScenarioCategory.TECHNICAL_TREND] == 5
    assert counts[ScenarioCategory.COMBINED_STRESS] == 5
    assert sum(counts.values()) == 23

    runner = StressTestingRunner()

    # 2. Battery without custom inputs executes exactly 23 scenarios
    scens_default, _, _, _, _ = runner.run_scenarios(sample_baseline, historical_peak=2000.0)
    assert len(scens_default) == 23

    # 3. Battery with 1 custom input executes exactly 24 scenarios (23 predefined + 1 custom)
    custom_scen = CustomScenarioInput(
        name="Custom Regulatory Shock",
        price_shock_pct=-12.0,
        volatility_shock_pct=40.0,
        sentiment_score=-0.75,
    )
    scens_with_custom, _, _, _, _ = runner.run_scenarios(
        sample_baseline,
        historical_peak=2000.0,
        custom_inputs=[custom_scen],
    )
    assert len(scens_with_custom) == 24
    assert scens_with_custom[-1].scenario_name == "Custom Regulatory Shock"


# ---------------------------------------------------------------------------
# 29. Monte Carlo GBM Mathematical Derivation and Convergence
# ---------------------------------------------------------------------------
def test_monte_carlo_gbm_mathematical_derivation():
    """Verify log-normal Geometric Brownian Motion mathematical formulas, drift, and probability of loss."""
    import math

    from scipy.stats import norm

    # Construct synthetic series of 250 bars with known negative drift simulating long-term drawdown
    # E.g. starting at 3500 and trending down to 2405
    n_bars = 250
    initial_p = 3500.0
    terminal_p = 2405.0
    t_vals = np.linspace(0, 1, n_bars)
    # Monotonic log-linear drift with modest noise
    np.random.seed(99)
    noise = np.random.normal(0, 0.008, n_bars)
    log_prices = np.log(initial_p) + (np.log(terminal_p) - np.log(initial_p)) * t_vals + noise
    closes = list(np.exp(log_prices))

    p0 = closes[-1]
    log_returns = np.diff(np.log(closes))
    daily_mu = float(np.mean(log_returns))
    daily_sigma = float(np.std(log_returns))

    assert daily_mu < 0.0  # Net historical decline over lookback window

    # Simulate T = 252 trading sessions (1 full year)
    T = 252
    sim = MonteCarloSimulator(num_simulations=5000, horizon_days=T, random_seed=42)
    res = sim.simulate(closes)

    # 1. Theoretical analytical median under GBM: S_0 * exp( (mu - 0.5 * sigma^2) * T )
    analytical_drift = (daily_mu - 0.5 * (daily_sigma**2)) * T
    theoretical_median = p0 * math.exp(analytical_drift)

    # Simulated median should match theoretical median within 2.5% Monte Carlo sampling tolerance
    pct_diff = abs(res.median_terminal_price - theoretical_median) / theoretical_median * 100.0
    assert pct_diff < 2.5, f"Simulated median {res.median_terminal_price} differs from theoretical {theoretical_median} by {pct_diff:.2f}%"

    # 2. Theoretical loss probability: Phi( -(mu - 0.5*sigma^2)*sqrt(T) / sigma )
    z_loss = -analytical_drift / (daily_sigma * math.sqrt(T))
    theoretical_prob_loss = float(norm.cdf(z_loss) * 100.0)

    # For negative drift with T=252, probability of loss is substantially > 50%
    assert res.probability_loss_pct > 70.0
    assert abs(res.probability_loss_pct - theoretical_prob_loss) < 3.0, (
        f"Simulated prob loss {res.probability_loss_pct}% differs from theoretical {theoretical_prob_loss}%"
    )


# ---------------------------------------------------------------------------
# 30. Stored TCS Long-Term Monte Carlo Exact Derivation & Reproducibility
# ---------------------------------------------------------------------------
def test_tcs_long_term_gbm_analytical_reconciliation():
    """Verify exact analytical GBM statistics and bitwise reproducibility for stored run_642db5e60751."""
    import json
    import math
    from pathlib import Path

    from scipy.stats import norm

    snap_path = Path("evaluation_results/snapshots/run_642db5e60751.json")
    fixture_path = Path(__file__).parent / "fixtures" / "tcs_500_bars.json"

    if snap_path.exists():
        with open(snap_path, "r", encoding="utf-8") as f:
            snap = json.load(f)
        raw_market = json.loads(snap["market_data"]["raw_json"])
        bars = raw_market["bars"]
        closes = [float(b["close"]) for b in bars]
    elif fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            fix_data = json.load(f)
        closes = [float(c) for c in fix_data["closes"]]
    else:
        pytest.skip("Neither stored snapshot nor portable fixture found.")
    assert len(closes) == 500
    S0 = closes[-1]
    assert S0 == 2405.0
    T = 252

    # 1. Independent Unrounded Production Inputs
    log_returns = np.diff(np.log(np.asarray(closes, dtype=float)))
    daily_mu = float(np.mean(log_returns))
    daily_sigma = float(np.std(log_returns))

    # 2. Analytical Statistics Verification
    # Analytical Median: S0 * exp((mu - 0.5 * sigma^2) * T)
    drift = (daily_mu - 0.5 * (daily_sigma**2)) * T
    analytical_median = S0 * math.exp(drift)

    # Analytical Mean: S0 * exp(mu * T)
    analytical_mean = S0 * math.exp(daily_mu * T)

    # Analytical Standard Deviation: mean * sqrt(exp(sigma^2 * T) - 1)
    analytical_std = analytical_mean * math.sqrt(math.exp((daily_sigma**2) * T) - 1)

    # Analytical Probability of Loss: Phi(-drift / (sigma * sqrt(T)))
    z_loss = -drift / (daily_sigma * math.sqrt(T))
    analytical_prob_loss = float(norm.cdf(z_loss) * 100.0)

    assert round(analytical_median, 2) == 1766.23
    assert round(analytical_mean, 2) == 1825.64
    assert round(analytical_std, 2) == 477.46
    assert round(analytical_prob_loss, 2) == 88.50

    # 3. Production Engine Bitwise Reproducibility Check
    sim = MonteCarloSimulator(num_simulations=1000, horizon_days=T, random_seed=42)
    res = sim.simulate(closes)

    assert res.initial_price == 2405.00
    assert res.mean_terminal_price == 1810.58
    assert res.median_terminal_price == 1769.04
    assert res.percentile_5_price == 1144.85
    assert res.percentile_25_price == 1476.60
    assert res.percentile_75_price == 2055.62
    assert res.percentile_95_price == 2676.67
    assert res.probability_loss_pct == 89.10
    assert res.probability_severe_loss_pct == 80.40
    assert res.expected_annualized_volatility == 25.72

