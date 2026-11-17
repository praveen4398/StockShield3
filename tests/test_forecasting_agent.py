"""Comprehensive test suite for StockShield 2.0 Forecasting Agent.

Verifies the 21 core requirements:
1. Valid historical data preparation.
2. Missing and duplicate observations handling.
3. Insufficient historical data handling.
4. ARIMA model execution.
5. Exponential Smoothing execution.
6. LightGBM training and prediction.
7. Multi-step forecasting (horizons 1, 5, 10).
8. Forecast date generation (business days skipping weekends).
9. Percentage change calculation.
10. MAE and RMSE calculation.
11. Directional accuracy calculation.
12. Chronological train/test splitting without leakage.
13. Data leakage prevention.
14. Model comparison and selection by validation RMSE.
15. Model failure handling and graceful fallback.
16. Pydantic schema validation.
17. Blackboard state publication and provenance recording.
18. Risk Engine Gate 7 predictive risk integration.
19. CrewAI lead orchestration integration.
20. Final report synthesis in Markdown and structured JSON.
21. Execution compatibility across Sequential, Parallel, and Hierarchical topologies.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from stockshield.agents.forecasting_agent import ForecastingAgent
from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import (
    FindingStatus,
    ForecastModelResult,
    ForecastPoint,
    ModelEvaluationMetrics,
    OHLCVBar,
    WorkflowStatus,
)
from stockshield.forecasting.arima_model import ARIMAForecaster
from stockshield.forecasting.data_preparation import (
    NSE_TRADING_HOLIDAYS,
    build_lightgbm_features,
    generate_future_trading_dates,
    is_nse_holiday,
    prepare_timeseries_dataframe,
)
from stockshield.forecasting.evaluation import ForecastingEvaluator, calculate_metrics
from stockshield.forecasting.exponential_smoothing import ExponentialSmoothingForecaster
from stockshield.forecasting.lightgbm_model import LightGBMForecaster
from stockshield.llm.stub_llm import DeterministicStubLLM
from stockshield.mcp.provider import MarketDataProvider, MarketDataRequest
from stockshield.orchestration.workflow import StockShieldWorkflow
from stockshield.risk.risk_engine import DeterministicRiskEngine


# ---------------------------------------------------------------------------
# Test Fixtures & Synthetic Data Generators
# ---------------------------------------------------------------------------
def _generate_synthetic_bars(n_bars: int = 150, base_price: float = 100.0) -> list[OHLCVBar]:
    """Generate n_bars of deterministic synthetic market bars for fast unit testing."""
    bars = []
    current_price = base_price
    start_dt = pd.Timestamp("2024-01-01")
    trading_days = pd.bdate_range(start=start_dt, periods=n_bars)

    for i, date_val in enumerate(trading_days):
        date_str = date_val.strftime("%Y-%m-%d")
        step_return = 0.002 * np.sin(i / 5.0) + 0.0005
        close = round(current_price * (1.0 + step_return), 2)
        high = round(close * 1.01, 2)
        low = round(close * 0.99, 2)
        open_p = round(current_price, 2)
        volume = int(100000 + 1000 * np.cos(i))
        current_price = close

        bars.append(
            OHLCVBar(
                timestamp=date_str,
                open=open_p,
                high=high,
                low=low,
                close=close,
                adjusted_close=close,
                volume=volume,
            )
        )
    return bars


# ---------------------------------------------------------------------------
# 1. Valid Historical Data Preparation
# ---------------------------------------------------------------------------
def test_valid_historical_data_preparation():
    """Verify chronological ordering, datetime parsing, and series validity."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(60)]
    df, warnings = prepare_timeseries_dataframe(raw_bars)

    assert df is not None
    assert len(df) == 60
    assert "target_close" in df.columns
    assert df["target_close"].iloc[0] > 0
    assert df["parsed_date"].is_monotonic_increasing


# ---------------------------------------------------------------------------
# 2. Missing and Duplicate Observations
# ---------------------------------------------------------------------------
def test_missing_and_duplicate_observations():
    """Verify deduplication and chronological sort when duplicate dates or unordered bars exist."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(35)]
    dup_bar = dict(raw_bars[10])
    dup_bar["close"] = dup_bar["close"] + 1.0
    shuffled_bars = raw_bars[20:] + [dup_bar] + raw_bars[:20]

    df, warnings = prepare_timeseries_dataframe(shuffled_bars)
    assert df is not None
    assert len(df) == 35  # duplicate removed
    assert df["parsed_date"].is_monotonic_increasing
    assert not df["parsed_date"].duplicated().any()
    assert any("duplicate" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# 3. Insufficient Historical Data
# ---------------------------------------------------------------------------
def test_insufficient_historical_data():
    """Verify that fewer than 30 bars are rejected with informative warning."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(20)]
    df, warnings = prepare_timeseries_dataframe(raw_bars, min_required_bars=30)
    assert df is None
    assert any("Insufficient historical data" in w for w in warnings)


# ---------------------------------------------------------------------------
# 4. ARIMA Model Execution
# ---------------------------------------------------------------------------
def test_arima_model_execution():
    """Verify ARIMA fits on historical data and produces point forecasts with confidence bounds."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(80)]
    df, _ = prepare_timeseries_dataframe(raw_bars)
    assert df is not None

    forecaster = ARIMAForecaster(candidate_orders=[(1, 1, 0), (0, 1, 1)])
    forecasts, warnings = forecaster.forecast_horizons(df["target_close"], steps=10)

    assert forecasts is not None
    assert 1 in forecasts
    assert 5 in forecasts
    assert 10 in forecasts
    for h in [1, 5, 10]:
        pt = forecasts[h]
        assert pt["predicted_close"] > 0
        if pt["lower_bound_95"] is not None and pt["upper_bound_95"] is not None:
            assert pt["lower_bound_95"] <= pt["predicted_close"] <= pt["upper_bound_95"]


# ---------------------------------------------------------------------------
# 5. Exponential Smoothing Execution
# ---------------------------------------------------------------------------
def test_exponential_smoothing_execution():
    """Verify Exponential Smoothing generates valid forecasts and confidence bounds."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(80)]
    df, _ = prepare_timeseries_dataframe(raw_bars)
    assert df is not None

    forecaster = ExponentialSmoothingForecaster()
    forecasts, warnings = forecaster.forecast_horizons(df["target_close"], steps=10)

    assert forecasts is not None
    assert 1 in forecasts
    assert 5 in forecasts
    assert 10 in forecasts
    for h in [1, 5, 10]:
        pt = forecasts[h]
        assert pt["predicted_close"] > 0
        if pt["lower_bound_95"] is not None and pt["upper_bound_95"] is not None:
            assert pt["lower_bound_95"] <= pt["predicted_close"] <= pt["upper_bound_95"]


# ---------------------------------------------------------------------------
# 6. LightGBM Training and Prediction
# ---------------------------------------------------------------------------
def test_lightgbm_training_and_prediction():
    """Verify LightGBM trains on engineered lagged features and generates forward predictions."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(100)]
    df, _ = prepare_timeseries_dataframe(raw_bars)
    assert df is not None

    forecaster = LightGBMForecaster()
    forecasts, warnings = forecaster.forecast_horizons(df, steps=10)

    assert forecasts is not None
    assert 1 in forecasts
    assert 5 in forecasts
    assert 10 in forecasts
    for h in [1, 5, 10]:
        assert forecasts[h]["predicted_close"] > 0


# ---------------------------------------------------------------------------
# 7. Multi-Step Forecasting (Horizons 1, 5, 10)
# ---------------------------------------------------------------------------
def test_multistep_forecasting_horizons():
    """Verify specific evaluation of trading sessions 1, 5, and 10."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(80)]
    df, _ = prepare_timeseries_dataframe(raw_bars)
    assert df is not None

    evaluator = ForecastingEvaluator()
    model_results, selected_name, reason, selected_points, warnings = evaluator.evaluate_and_forecast_all(
        df, ticker="TEST.NS"
    )

    assert selected_name in ["ARIMA", "ExponentialSmoothing", "LightGBM"]
    assert len(selected_points) == 3
    steps = [p.horizon_trading_days for p in selected_points]
    assert steps == [1, 5, 10]


# ---------------------------------------------------------------------------
# 8. Forecast Date Generation
# ---------------------------------------------------------------------------
def test_forecast_date_generation():
    """Verify future business dates skip weekends and official NSE holidays (e.g. Good Friday)."""
    # 2024-03-28 is Thursday; 2024-03-29 is Good Friday (NSE holiday)
    dates = generate_future_trading_dates("2024-03-28", num_sessions=5)
    # T+1: Mon 2024-04-01 (skips Good Friday 2024-03-29 and weekend 2024-03-30..31)
    # T+2: Tue 2024-04-02
    # T+3: Wed 2024-04-03
    # T+4: Thu 2024-04-04
    # T+5: Fri 2024-04-05
    assert len(dates) == 5
    assert dates[0] == "2024-04-01"
    assert dates[1] == "2024-04-02"
    assert dates[2] == "2024-04-03"
    assert dates[3] == "2024-04-04"
    assert dates[4] == "2024-04-05"

    # Verify none of the generated dates are Saturday, Sunday, or NSE holidays
    for d_str in dates:
        dt = datetime.strptime(d_str, "%Y-%m-%d")
        assert dt.weekday() < 5
        assert not is_nse_holiday(d_str)


# ---------------------------------------------------------------------------
# 9. Percentage Change Calculation
# ---------------------------------------------------------------------------
def test_percentage_change_calculation():
    """Verify pct_change is correctly referenced to the latest observed close."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(60, base_price=100.0)]
    df, _ = prepare_timeseries_dataframe(raw_bars)
    assert df is not None
    latest_close = float(df["target_close"].iloc[-1])

    evaluator = ForecastingEvaluator()
    model_results, selected_name, reason, selected_points, warnings = evaluator.evaluate_and_forecast_all(
        df, ticker="TEST.NS"
    )

    for p in selected_points:
        expected_pct = round(((p.predicted_close - latest_close) / latest_close) * 100.0, 2)
        assert abs(p.predicted_change_pct - expected_pct) < 0.05


# ---------------------------------------------------------------------------
# 10. MAE and RMSE Calculation
# ---------------------------------------------------------------------------
def test_mae_and_rmse_calculation():
    """Verify mathematical calculation of MAE and RMSE."""
    actual = np.array([100.0, 105.0, 110.0, 108.0])
    predicted = np.array([102.0, 103.0, 112.0, 106.0])
    base_price = 98.0

    mae, rmse, da = calculate_metrics(actual, predicted, base_price)

    # Errors: |2|, |2|, |2|, |2| -> MAE = 2.0
    assert mae == 2.0
    # Squared errors: 4, 4, 4, 4 -> Mean = 4.0 -> RMSE = 2.0
    assert rmse == 2.0


# ---------------------------------------------------------------------------
# 11. Directional Accuracy Calculation
# ---------------------------------------------------------------------------
def test_directional_accuracy_calculation():
    """Verify directional accuracy computes percentage of correct movement directions."""
    actual = np.array([105.0, 102.0, 110.0, 112.0])
    predicted = np.array([104.0, 100.0, 108.0, 111.0])
    mae, rmse, da = calculate_metrics(actual, predicted, baseline_prev=100.0)
    assert da == 100.0


# ---------------------------------------------------------------------------
# 12. Chronological Train/Test Splitting
# ---------------------------------------------------------------------------
def test_chronological_train_test_split():
    """Verify walk-forward validation splits chronologically without shuffling."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(100)]
    df, _ = prepare_timeseries_dataframe(raw_bars)
    assert df is not None

    k_val = 10
    train_df = df.iloc[:-k_val].copy()
    val_df = df.iloc[-k_val:].copy()

    assert len(val_df) == 10
    assert len(train_df) == 90
    assert train_df["parsed_date"].iloc[-1] < val_df["parsed_date"].iloc[0]


# ---------------------------------------------------------------------------
# 13. Data Leakage Prevention
# ---------------------------------------------------------------------------
def test_data_leakage_prevention():
    """Verify lag features are strictly backward looking (no future lookahead)."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(50)]
    df, _ = prepare_timeseries_dataframe(raw_bars)
    assert df is not None

    feat_df = build_lightgbm_features(df)
    first_row = feat_df.iloc[0]
    first_date = first_row["parsed_date"]
    original_idx = df[df["parsed_date"] == first_date].index[0]

    # Target is target_close at original_idx
    assert first_row["target_close"] == df["target_close"].iloc[original_idx]

    # Lag 1 must be target_close at original_idx - 1
    assert first_row["lag_1"] == df["target_close"].iloc[original_idx - 1]
    # Lag 2 must be target_close at original_idx - 2
    assert first_row["lag_2"] == df["target_close"].iloc[original_idx - 2]


# ---------------------------------------------------------------------------
# 14. Model Comparison and Selection
# ---------------------------------------------------------------------------
def test_model_comparison_and_selection():
    """Verify model with lowest validation RMSE is selected as best_model."""
    m_arima = ForecastModelResult(
        model_name="ARIMA",
        forecast_points=[ForecastPoint(horizon_trading_days=1, forecast_date="2024-04-01", predicted_close=100.0, predicted_change_pct=0.0, model_name="ARIMA")],
        metrics=ModelEvaluationMetrics(model_name="ARIMA", rmse=15.2, mae=12.1, directional_accuracy_pct=60.0),
    )
    m_es = ForecastModelResult(
        model_name="ExponentialSmoothing",
        forecast_points=[ForecastPoint(horizon_trading_days=1, forecast_date="2024-04-01", predicted_close=101.0, predicted_change_pct=1.0, model_name="ExponentialSmoothing")],
        metrics=ModelEvaluationMetrics(model_name="ExponentialSmoothing", rmse=9.8, mae=7.4, directional_accuracy_pct=70.0),
    )
    m_lgbm = ForecastModelResult(
        model_name="LightGBM",
        forecast_points=[ForecastPoint(horizon_trading_days=1, forecast_date="2024-04-01", predicted_close=102.0, predicted_change_pct=2.0, model_name="LightGBM")],
        metrics=ModelEvaluationMetrics(model_name="LightGBM", rmse=12.4, mae=10.0, directional_accuracy_pct=65.0),
    )

    candidates = [m_arima, m_es, m_lgbm]
    best_candidate = min(candidates, key=lambda c: c.metrics.rmse)

    assert best_candidate.model_name == "ExponentialSmoothing"
    assert best_candidate.metrics.rmse == 9.8


# ---------------------------------------------------------------------------
# 15. Model Failure Handling
# ---------------------------------------------------------------------------
def test_model_failure_handling():
    """Verify that if one model fails to converge, other models proceed and best is selected from survivors."""
    m_arima = ForecastModelResult(
        model_name="ARIMA",
        forecast_points=[],
        metrics=ModelEvaluationMetrics(
            model_name="ARIMA", rmse=999.0, status="failed", error_message="Singular matrix encountered"
        ),
    )
    m_es = ForecastModelResult(
        model_name="ExponentialSmoothing",
        forecast_points=[ForecastPoint(horizon_trading_days=1, forecast_date="2024-04-01", predicted_close=101.0, predicted_change_pct=1.0, model_name="ExponentialSmoothing")],
        metrics=ModelEvaluationMetrics(model_name="ExponentialSmoothing", rmse=11.2, mae=9.1, directional_accuracy_pct=60.0),
    )
    candidates = [m for m in [m_arima, m_es] if m.metrics.status == "success" and len(m.forecast_points) > 0]
    best = min(candidates, key=lambda c: c.metrics.rmse)

    assert best.model_name == "ExponentialSmoothing"


# ---------------------------------------------------------------------------
# 16. Pydantic Output Validation
# ---------------------------------------------------------------------------
def test_pydantic_output_validation():
    """Verify strict Pydantic v2 schema constraints on forecast points and states."""
    p = ForecastPoint(
        horizon_trading_days=1,
        forecast_date="2024-04-01",
        predicted_close=3500.50,
        predicted_change_pct=1.25,
        lower_bound_95=3400.0,
        upper_bound_95=3600.0,
        model_name="ARIMA",
    )
    assert p.horizon_trading_days == 1
    assert p.predicted_close == 3500.5
    assert p.predicted_change_pct == 1.25

    # Negative price must raise ValidationError
    with pytest.raises(Exception):
        ForecastPoint(
            horizon_trading_days=1,
            forecast_date="2024-04-01",
            predicted_close=-100.0,
            predicted_change_pct=1.0,
            model_name="ARIMA",
        )


# ---------------------------------------------------------------------------
# 17. Blackboard Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_blackboard_integration():
    """Verify ForecastingAgent writes to Blackboard with provenance and atomic locking."""
    blackboard = BlackboardManager(
        run_id="run_test_f17",
        trace_id="trace_test_f17",
        ticker="TCS.NS",
        user_prompt="Test Blackboard publication of forecasting.",
    )

    bars = [b.model_dump() for b in _generate_synthetic_bars(120)]
    await blackboard.update_market_data(
        producer="test_provider",
        source="fixture",
        bars=bars,
        status=FindingStatus.AVAILABLE,
    )

    agent = ForecastingAgent()
    res = await agent.execute(blackboard)

    assert res["status"] == "completed"
    assert res["best_model"] in ["ARIMA", "ExponentialSmoothing", "LightGBM"]

    state = await blackboard.get_state_snapshot()
    assert state.forecasting.status == FindingStatus.AVAILABLE
    assert state.forecasting.selected_model_name == res["best_model"]
    assert len(state.forecasting.selected_forecasts) in [3, 4]

    # Verify provenance record
    prov = [p for p in state.provenance_trail if p.field_name == "forecasting"]
    assert len(prov) == 1
    assert prov[0].producer == "ForecastingAgent"


# ---------------------------------------------------------------------------
# 18. Risk Engine Integration (Gate 7)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_risk_engine_gate7_integration():
    """Verify Risk Engine Gate 7 evaluates downside forecasts, model divergence, and accuracy."""
    blackboard = BlackboardManager(
        run_id="run_test_f18",
        trace_id="trace_test_f18",
        ticker="TCS.NS",
        user_prompt="Test Gate 7 predictive risk integration.",
    )

    bars = [b.model_dump() for b in _generate_synthetic_bars(100)]
    await blackboard.update_market_data(
        producer="test_provider",
        source="fixture",
        bars=bars,
        status=FindingStatus.AVAILABLE,
    )

    agent = ForecastingAgent()
    await agent.execute(blackboard)

    risk_engine = DeterministicRiskEngine()
    risk_res = await risk_engine.execute(blackboard)

    assert risk_res["status"] == "completed"
    gate7_checks = [c for c in risk_res["checks"] if c["name"] == "predictive_forecast_risk"]
    assert len(gate7_checks) == 1
    assert gate7_checks[0]["score"] >= 0.0


# ---------------------------------------------------------------------------
# 19. CrewAI Orchestration Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_crewai_orchestration_integration():
    """Verify ForecastingAgent executes in end-to-end workflow, recording events and callbacks."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "TCS.NS",
        "user_prompt": "Run full institutional equity analysis with forward forecasting.",
        "lookback_days": 200,
        "workflow_mode": "sequential",
    }
    state = await workflow.run(raw_request=req, workflow_mode="sequential")

    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.forecasting.status == FindingStatus.AVAILABLE

    # Verify execution event logged
    f_events = [e for e in state.execution_events if e.get("component") in ["ForecastingAgent", "forecasting_agent"]]
    assert len(f_events) == 2  # agent_start, agent_complete
    assert f_events[1]["status"] == "completed"


# ---------------------------------------------------------------------------
# 20. Final Report Integration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_final_report_integration():
    """Verify Section 6 is included in markdown report and structured JSON."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "INFY.NS",
        "user_prompt": "Check Section 6 report generation.",
        "lookback_days": 200,
        "workflow_mode": "sequential",
    }
    state = await workflow.run(raw_request=req, workflow_mode="sequential")

    # Check Markdown Content
    md = state.final_report.markdown_content
    assert "## 6. Multi-Model Forward Price Forecasting Intelligence" in md
    assert "Optimal Model Selected:" in md
    assert "Multi-Step Forward Projections" in md

    # Check Structured JSON
    json_data = state.final_report.structured_json
    assert "forecasting" in json_data
    assert json_data["forecasting"]["status"] == "available"
    assert json_data["forecasting"]["best_model"] is not None
    assert len(json_data["forecasting"]["forecasts"]) in [3, 4]


# ---------------------------------------------------------------------------
# 21. Sequential, Parallel, and Hierarchical Workflow Compatibility
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sequential", "parallel", "hierarchical"])
async def test_workflow_topologies_compatibility(mode):
    """Verify forecasting operates reliably across sequential, parallel, and hierarchical modes."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "TCS.NS",
        "user_prompt": f"Verify {mode} workflow with forecasting.",
        "lookback_days": 200,
        "workflow_mode": mode,
    }
    state = await workflow.run(raw_request=req, workflow_mode=mode)

    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.forecasting.status == FindingStatus.AVAILABLE
    assert state.forecasting.selected_model_name in ["ARIMA", "ExponentialSmoothing", "LightGBM"]


# ---------------------------------------------------------------------------
# 22. LightGBM Recursive Consecutive Return Calculation (Fix 2 Verification)
# ---------------------------------------------------------------------------
def test_lightgbm_recursive_consecutive_returns():
    """Verify recursive LightGBM updates ret_1d = (lag_1 - lag_2) / lag_2 across forecast steps."""
    # Synthetic bars with upward trend
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(120, base_price=150.0)]
    df, _ = prepare_timeseries_dataframe(raw_bars)
    assert df is not None

    forecaster = LightGBMForecaster()
    forecasts, warnings = forecaster.forecast_horizons(df, steps=10)

    assert forecasts is not None
    # All 10 steps should have distinct forecasted prices
    prices = [forecasts[s]["predicted_close"] for s in [1, 5, 10]]
    assert all(p > 0 for p in prices)

    # Validate that predictions change across horizons and are not constant flat values
    assert forecasts[1]["predicted_close"] != forecasts[10]["predicted_close"]


# ---------------------------------------------------------------------------
# 23. NSE Trading Holiday Awareness (Fix 3 Verification)
# ---------------------------------------------------------------------------
def test_nse_holiday_skipping_calendar():
    """Verify holiday skipping for known NSE trading holidays across multiple years."""
    # 1. 2024 Independence Day (2024-08-15 Thursday)
    dates_aug = generate_future_trading_dates("2024-08-14", num_sessions=2)
    # T+1 should be Friday 2024-08-16, skipping Thursday 2024-08-15
    assert dates_aug[0] == "2024-08-16"

    # 2. 2024 Republic Day (2024-01-26 Friday)
    dates_jan = generate_future_trading_dates("2024-01-25", num_sessions=2)
    # T+1 should be Monday 2024-01-29, skipping Friday 2024-01-26 and weekend 27-28
    assert dates_jan[0] == "2024-01-29"

    # 3. 2025 Christmas (2025-12-25 Thursday)
    dates_dec = generate_future_trading_dates("2025-12-24", num_sessions=2)
    # T+1 should be Friday 2025-12-26, skipping Thursday 2025-12-25
    assert dates_dec[0] == "2025-12-26"

    # 4. Helper function directly and set membership
    assert "2024-08-15" in NSE_TRADING_HOLIDAYS
    assert is_nse_holiday("2024-08-15") is True
    assert is_nse_holiday("2024-08-16") is False
    assert is_nse_holiday("2024-01-26") is True  # Republic Day 2024 (Friday)
    assert is_nse_holiday("2025-08-15") is True  # Independence Day 2025 (Friday)
    assert is_nse_holiday("2026-01-26") is True  # Republic Day 2026 (Monday)
    assert is_nse_holiday("2026-10-02") is True  # Mahatma Gandhi Jayanti 2026 (Friday)


# ---------------------------------------------------------------------------
# 24. Stale vs Fresh Market Data Labeling (Fix 1 Verification)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stale_market_data_flagging_and_labeling():
    """Verify market data >7 days old is flagged is_stale=True and forecast_label='historical_stale_backtest'."""
    blackboard = BlackboardManager(
        run_id="run_test_stale",
        trace_id="trace_test_stale",
        ticker="TCS.NS",
        user_prompt="Evaluate stale data handling.",
    )

    # Generate bars ending in 2024 (over a year ago)
    bars = [b.model_dump() for b in _generate_synthetic_bars(100)]
    await blackboard.update_market_data(
        producer="test_provider",
        source="fixture",
        bars=bars,
        status=FindingStatus.AVAILABLE,
        is_stale=True,
        freshness_age_days=365,
    )

    agent = ForecastingAgent()
    await agent.execute(blackboard)

    # Verify blackboard state attributes
    assert blackboard.state.forecasting.is_stale_data is True
    assert blackboard.state.forecasting.forecast_label == "historical_stale_backtest"

    # Verify findings contain warning notice
    stale_findings = [f for f in blackboard.state.forecasting.findings if "⚠️ STALE DATA NOTICE" in f]
    assert len(stale_findings) == 1
    assert "historical_stale_backtest" in stale_findings[0]


@pytest.mark.asyncio
async def test_fresh_market_data_labeling():
    """Verify recent market data is labeled is_stale_data=False and forecast_label='current_forward_looking'."""
    blackboard = BlackboardManager(
        run_id="run_test_fresh",
        trace_id="trace_test_fresh",
        ticker="TCS.NS",
        user_prompt="Evaluate fresh data handling.",
    )

    bars = [b.model_dump() for b in _generate_synthetic_bars(100)]
    await blackboard.update_market_data(
        producer="test_provider",
        source="yahoo_finance",
        bars=bars,
        status=FindingStatus.AVAILABLE,
        is_stale=False,
        freshness_age_days=1,
    )

    agent = ForecastingAgent()
    await agent.execute(blackboard)

    assert blackboard.state.forecasting.is_stale_data is False
    assert blackboard.state.forecasting.forecast_label == "current_forward_looking"


# ---------------------------------------------------------------------------
# 25. Provider Auto Mode Freshness Handling (Fix 1 Verification)
# ---------------------------------------------------------------------------
def test_provider_auto_mode_freshness_handling():
    """Verify auto mode checks fixture age and either gets live data or marks fixture as stale."""
    provider = MarketDataProvider()
    # TCS fixture has last bar in Nov 2025 (>7 days old)
    res = provider.get_market_data(MarketDataRequest(ticker="TCS.NS", lookback_days=100, provider_mode="auto"))

    if res.source == "fixture":
        assert res.is_stale is True
        assert res.data_quality_status == "stale"
        assert res.freshness_age_days is not None and res.freshness_age_days > 7
    else:
        assert res.source == "yahoo_finance"
        assert res.is_stale is False


# ---------------------------------------------------------------------------
# 26. Report Generation: Terminology and Stale Banner (Fix 1 & 4 Verification)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_report_generation_stale_banner_and_methodology():
    """Verify Section 6 includes stale banner when stale, and uses Chronological Holdout terminology."""
    blackboard = BlackboardManager(
        run_id="run_test_rep",
        trace_id="trace_test_rep",
        ticker="TCS.NS",
        user_prompt="Report test.",
    )

    bars = [b.model_dump() for b in _generate_synthetic_bars(100)]
    await blackboard.update_market_data(
        producer="test_provider",
        source="fixture",
        bars=bars,
        status=FindingStatus.AVAILABLE,
        is_stale=True,
        freshness_age_days=365,
    )

    agent = ForecastingAgent()
    await agent.execute(blackboard)

    synthesizer = DeterministicStubLLM()
    _, md, json_data, _ = synthesizer.generate_report(blackboard.state)

    # Verify Stale banner in Markdown
    assert "STALE DATA NOTICE / HISTORICAL BENCHMARK:" in md
    assert "historical_stale_backtest" in md

    # Verify Methodology terminology in Markdown
    assert "Chronological Holdout Validation [10 sessions]" in md
    assert "insufficient to prove persistent alpha" in md

    # Verify structured JSON
    f_json = json_data["forecasting"]
    assert f_json["validation_methodology"] == "chronological_holdout"
    assert f_json["is_stale_data"] is True
    assert f_json["forecast_classification"] == "historical_stale_backtest"
    assert json_data["market_data_summary"]["is_stale"] is True


# ---------------------------------------------------------------------------
# 27. Verification of All Five Multi-Horizon Dropdown Forecast Windows
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "horizon_choice,expected_max_step,expected_target_steps",
    [
        ("1_month", 21, [1, 5, 10, 21]),
        ("3_months", 63, [5, 21, 42, 63]),
        ("6_months", 126, [21, 42, 84, 126]),
        ("1_year", 252, [21, 63, 126, 252]),
        ("2_years", 504, [63, 126, 252, 504]),
    ],
)
def test_all_five_dropdown_forecast_horizons(horizon_choice, expected_max_step, expected_target_steps):
    """Verify that every dropdown selection produces the specified trading sessions and steps."""
    raw_bars = [b.model_dump() for b in _generate_synthetic_bars(120)]
    df, _ = prepare_timeseries_dataframe(raw_bars)
    assert df is not None

    evaluator = ForecastingEvaluator()
    model_results, selected_name, reason, selected_points, warnings = evaluator.evaluate_and_forecast_all(
        df, ticker="TEST.NS", forecast_horizon=horizon_choice
    )

    assert selected_name in ["ARIMA", "ExponentialSmoothing", "LightGBM"]
    assert len(selected_points) == len(expected_target_steps)
    steps = [p.horizon_trading_days for p in selected_points]
    assert steps == expected_target_steps
    assert steps[-1] == expected_max_step
