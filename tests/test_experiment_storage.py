"""Tests for StockShield 2.0 Persistent Experiment Result Storage.

Covers:
- Database creation, schema versioning, and WAL journal mode.
- Clean run creation and immediate status registration.
- Duplicate run ID rejection and overwrite prevention.
- Stage-by-stage incremental persistence.
- Complete run recording with all stages populated.
- Partial run retention upon simulated agent failure.
- Judge failure isolation in storage.
- Token and cost metadata persistence.
- Secret redaction and credential safety.
- CSV export content and structure verification.
- JSON snapshot generation and integrity.
- Retrieval by run ID, ticker, status, and experiment_id.
- Concurrent run creation thread-safety.
- Recovery after simulated application restart.
- FastAPI evaluation endpoints.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stockshield.api.main import app
from stockshield.blackboard.models import (
    FindingStatus,
    ForecastingState,
    ForecastModelResult,
    ForecastPoint,
    JudgeEvaluationState,
    MarketDataState,
    ModelEvaluationMetrics,
    NewsSentimentState,
    RiskCheck,
    RiskFindingsState,
    ScenarioSimulationState,
    StockShieldBlackboard,
    TechnicalFindingsState,
    TechnicalIndicators,
)
from stockshield.evaluation.storage import (
    CURRENT_SCHEMA_VERSION,
    ExperimentStorage,
    RunStatus,
)
from stockshield.judge.models import DimensionScore


@pytest.fixture
def temp_storage(tmp_path: Path):
    """Provide an isolated ExperimentStorage instance per test."""
    db_file = tmp_path / "test_experiments.db"
    snap_dir = tmp_path / "snapshots"
    exp_dir = tmp_path / "exports"
    storage = ExperimentStorage(
        db_path=str(db_file),
        snapshot_dir=str(snap_dir),
        export_dir=str(exp_dir),
    )
    return storage


def test_database_initialization_and_schema(temp_storage: ExperimentStorage):
    """Verify database tables, indexes, WAL mode, and schema version."""
    assert temp_storage.db_path.exists()
    conn = temp_storage._get_connection()
    try:
        # Check WAL mode
        cur = conn.execute("PRAGMA journal_mode;")
        journal_mode = cur.fetchone()[0].lower()
        assert journal_mode == "wal"

        # Check schema version
        cur = conn.execute("SELECT version FROM schema_version;")
        row = cur.fetchone()
        assert row is not None
        assert row["version"] == CURRENT_SCHEMA_VERSION

        # Check tables existence
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {r["name"] for r in cur.fetchall()}
        expected_tables = {
            "schema_version",
            "runs",
            "stage_market_data",
            "stage_technical",
            "stage_news_sentiment",
            "stage_forecasting",
            "stage_risk",
            "stage_scenario_simulation",
            "stage_judge",
            "stage_performance",
        }
        assert expected_tables.issubset(tables)
    finally:
        conn.close()


def test_create_run_and_duplicate_rejection(temp_storage: ExperimentStorage):
    """Verify clean run creation, RUNNING status, and duplicate run ID rejection."""
    run_id = "run_test_001"
    temp_storage.create_run(
        run_id=run_id,
        experiment_id="test_exp",
        ticker="TCS.NS",
        workflow_mode="sequential",
        config={"lookback_days": 200, "gemini_api_key": "AIzaSySecret123"},
    )

    run = temp_storage.get_run(run_id)
    assert run is not None
    assert run["run_id"] == run_id
    assert run["experiment_id"] == "test_exp"
    assert run["ticker"] == "TCS.NS"
    assert run["status"] == RunStatus.RUNNING.value
    assert run["workflow_mode"] == "sequential"
    # Secret redaction check in stored config
    assert run["config"]["gemini_api_key"] == "[REDACTED]"
    assert run["config"]["lookback_days"] == 200

    # Overwrite prevention check
    with pytest.raises(ValueError, match="already exists in database"):
        temp_storage.create_run(
            run_id=run_id,
            experiment_id="test_exp_2",
            ticker="INFY.NS",
            workflow_mode="parallel",
        )


def test_incremental_stage_persistence(temp_storage: ExperimentStorage):
    """Verify that stage results can be committed incrementally without losing earlier stages."""
    run_id = "run_test_incremental"
    temp_storage.create_run(
        run_id=run_id,
        experiment_id="pilot_test",
        ticker="INFY.NS",
        workflow_mode="sequential",
    )

    # 1. Market data stage
    mkt = MarketDataState(
        status=FindingStatus.AVAILABLE,
        source="yahoo_finance",
        bar_count=200,
        data_quality_status="valid",
        is_stale=False,
        freshness_age_days=0,
    )
    temp_storage.record_stage_market_data(run_id, mkt)

    run = temp_storage.get_run(run_id)
    assert run["market_data"] is not None
    assert run["market_data"]["source"] == "yahoo_finance"
    assert run["market_data"]["bar_count"] == 200
    assert run["technical"] is None

    # 2. Technical analysis stage
    tech = TechnicalFindingsState(
        status=FindingStatus.AVAILABLE,
        signal="BULLISH",
        signal_confidence=0.85,
        indicators=TechnicalIndicators(rsi_14=62.5, sma_20=1820.0, sma_50=1780.0),
        summary="Technical momentum positive above key moving averages.",
    )
    temp_storage.record_stage_technical(run_id, tech)

    run = temp_storage.get_run(run_id)
    assert run["market_data"] is not None
    assert run["technical"] is not None
    assert run["technical"]["signal"] == "BULLISH"
    assert run["technical"]["confidence"] == 0.85
    assert run["news_sentiment"] is None


def test_partial_run_retention_on_agent_failure(temp_storage: ExperimentStorage):
    """Verify that if an agent crashes, completed stage outputs are preserved and status is PARTIAL."""
    run_id = "run_test_partial"
    temp_storage.create_run(
        run_id=run_id,
        experiment_id="pilot_test",
        ticker="RELIANCE.NS",
        workflow_mode="sequential",
    )

    mkt = MarketDataState(
        status=FindingStatus.AVAILABLE,
        source="yahoo_finance",
        bar_count=200,
        data_quality_status="valid",
    )
    temp_storage.record_stage_market_data(run_id, mkt)

    tech = TechnicalFindingsState(
        status=FindingStatus.AVAILABLE,
        signal="NEUTRAL",
        signal_confidence=0.5,
    )
    temp_storage.record_stage_technical(run_id, tech)

    # Simulate failure in subsequent agent
    error_msg = "NewsSentimentAgent encountered unexpected RSS parse exception"
    temp_storage.fail_run(
        run_id=run_id,
        error_message=error_msg,
        duration_ms=4500.0,
        is_partial=True,
    )

    run = temp_storage.get_run(run_id)
    assert run["status"] == RunStatus.PARTIAL.value
    assert run["error_message"] == error_msg
    assert run["total_duration_ms"] == 4500.0
    # Crucially, earlier stages are intact!
    assert run["market_data"] is not None
    assert run["market_data"]["status"] == "available"
    assert run["technical"] is not None
    assert run["technical"]["signal"] == "NEUTRAL"


def test_judge_failure_isolation_in_storage(temp_storage: ExperimentStorage):
    """Verify that a failed judge evaluation does NOT compromise financial results."""
    run_id = "run_test_judge_failure"
    temp_storage.create_run(
        run_id=run_id,
        experiment_id="pilot_test",
        ticker="TCS.NS",
        workflow_mode="sequential",
    )

    # Financial analysis succeeds
    risk = RiskFindingsState(
        status=FindingStatus.AVAILABLE,
        overall_risk_level="LOW",
        composite_risk_score=0.12,
        recommendation="APPROVED",
    )
    temp_storage.record_stage_risk(run_id, risk)

    # Judge fails
    failed_judge = JudgeEvaluationState(
        status="failed",
        configured_model="gemini-3.8-flash",
        actual_model="gemini-3.8-flash",
        error_message="API connection timeout after 60s",
        cost_status="unavailable",
    )
    temp_storage.record_stage_judge(run_id, failed_judge)

    # Mark run complete because core analysis completed
    temp_storage.complete_run(run_id=run_id, duration_ms=12000.0)

    run = temp_storage.get_run(run_id)
    assert run["status"] == RunStatus.COMPLETED.value
    assert run["risk"]["recommendation"] == "APPROVED"
    assert run["risk"]["composite_score"] == 0.12
    assert run["judge"]["status"] == "failed"
    assert run["judge"]["error_message"] == "API connection timeout after 60s"
    assert run["judge"]["overall_score"] is None


def test_complete_run_recording_and_snapshot(temp_storage: ExperimentStorage):
    """Verify end-to-end atomic record_state, snapshot generation, and token metadata."""
    run_id = "run_test_complete_state"
    temp_storage.create_run(
        run_id=run_id,
        experiment_id="benchmark_run",
        ticker="HDFCBANK.NS",
        workflow_mode="hierarchical",
    )

    # Create dummy blackboard
    bb = StockShieldBlackboard(
        run_id=run_id,
        trace_id="trace_test_001",
        ticker="HDFCBANK.NS",
        user_prompt="Run full institutional review.",
        workflow_mode="hierarchical",
    )
    bb.market_data = MarketDataState(status=FindingStatus.AVAILABLE, source="yahoo_finance", bar_count=200)
    bb.technical_findings = TechnicalFindingsState(
        status=FindingStatus.AVAILABLE,
        signal="BULLISH",
        signal_confidence=0.78,
        indicators=TechnicalIndicators(rsi_14=68.2, macd_hist=4.5),
    )
    bb.news_sentiment = NewsSentimentState(
        status=FindingStatus.AVAILABLE,
        overall_sentiment="POSITIVE",
        sentiment_score=0.45,
        total_articles=12,
        positive_count=8,
        neutral_count=3,
        negative_count=1,
    )

    metrics = ModelEvaluationMetrics(model_name="LightGBM", rmse=12.4, mae=8.2, directional_accuracy_pct=70.0)
    forecast_pt = ForecastPoint(
        horizon_trading_days=1,
        forecast_date="2026-11-20",
        predicted_close=1750.5,
        predicted_change_pct=1.2,
        model_name="LightGBM",
    )
    model_res = ForecastModelResult(model_name="LightGBM", metrics=metrics, forecast_points=[forecast_pt])
    bb.forecasting = ForecastingState(
        status=FindingStatus.AVAILABLE,
        selected_model_name="LightGBM",
        selection_reason="Minimal validation RMSE",
        model_results={"LightGBM": model_res},
        selected_forecasts=[forecast_pt],
    )

    bb.risk_findings = RiskFindingsState(
        status=FindingStatus.AVAILABLE,
        overall_risk_level="MODERATE",
        composite_risk_score=0.18,
        recommendation="APPROVED_WITH_CAUTION",
        checks=[RiskCheck(name="Volatility Gate", passed=True, score=0.15, message="Acceptable volatility")],
    )

    bb.scenario_simulation = ScenarioSimulationState(
        status=FindingStatus.AVAILABLE,
        total_scenarios_evaluated=24,
    )

    bb.judge_evaluation = JudgeEvaluationState(
        status="available",
        configured_model="gemini-3.8-flash",
        actual_model="gemini-3.8-flash",
        overall_score=9.2,
        verdict="EXCELLENT",
        dimensions={
            "factual_grounding": DimensionScore(
                dimension="factual_grounding", score=9.5, explanation="Accurate data grounding with zero hallucinations."
            ),
            "completeness": DimensionScore(
                dimension="completeness", score=9.0, explanation="Comprehensive coverage of all six evaluation areas."
            ),
            "cross_agent_consistency": DimensionScore(
                dimension="cross_agent_consistency", score=9.2, explanation="Signals align seamlessly between agents."
            ),
            "forecasting_assessment": DimensionScore(
                dimension="forecasting_assessment", score=9.0, explanation="Statistical models evaluated with low RMSE."
            ),
            "risk_reasoning": DimensionScore(
                dimension="risk_reasoning", score=9.3, explanation="Deterministic risk gates applied methodically."
            ),
            "financial_safety": DimensionScore(
                dimension="financial_safety", score=9.5, explanation="Clear disclaimers and conservative capital rules."
            ),
        },
        input_tokens=2500,
        output_tokens=600,
        total_tokens=3100,
        latency_ms=1850.0,
        estimated_cost_usd=0.00032,
        cost_status="actual",
    )

    bb.execution_events = [
        {"component": "mcp_market_data", "details": {"duration_ms": 320.0}},
        {"component": "GoogleADKTechnicalAgent", "details": {"duration_ms": 110.0}},
        {"component": "news_sentiment_agent", "details": {"duration_ms": 450.0}},
        {"component": "forecasting_agent", "details": {"duration_ms": 1200.0}},
        {"component": "risk_engine", "details": {"duration_ms": 15.0}},
        {"component": "scenario_simulation_agent", "details": {"duration_ms": 680.0}},
        {"component": "crewai_orchestrator", "details": {"duration_ms": 42.0}},
        {"component": "gemini_llm_judge", "details": {"duration_ms": 1850.0}},
    ]

    final_resp = {"status": "success", "run_id": run_id, "score": 9.2}
    temp_storage.record_state(
        run_id=run_id,
        state=bb,
        status=RunStatus.COMPLETED,
        duration_ms=4667.0,
        final_response=final_resp,
    )

    # Verify retrieval
    run = temp_storage.get_run(run_id)
    assert run["status"] == RunStatus.COMPLETED.value
    assert run["market_data"]["bar_count"] == 200
    assert run["technical"]["signal"] == "BULLISH"
    assert run["news_sentiment"]["sentiment_score"] == 0.45
    assert run["forecasting"]["selected_model"] == "LightGBM"
    assert run["forecasting"]["directional_accuracy"] == 70.0
    assert run["risk"]["composite_score"] == 0.18
    assert run["judge"]["overall_score"] == 9.2
    assert run["judge"]["verdict"] == "EXCELLENT"
    assert run["judge"]["total_tokens"] == 3100
    assert run["judge"]["estimated_cost_usd"] == 0.00032
    assert run["judge"]["factual_grounding"] == 9.5
    assert run["performance"]["total_duration_ms"] == 4667.0

    # Verify snapshot file on disk
    snap_file = temp_storage.snapshot_dir / f"{run_id}.json"
    assert snap_file.exists()
    snap_content = json.loads(snap_file.read_text(encoding="utf-8"))
    assert snap_content["run_id"] == run_id
    assert snap_content["score"] == 9.2


def test_csv_exports_structure_and_completeness(temp_storage: ExperimentStorage):
    """Verify the 4 canonical academic CSV files, headers, and absence of fabricated zeroes."""
    run_id_1 = "run_csv_complete"
    run_id_2 = "run_csv_failed"

    temp_storage.create_run(run_id=run_id_1, experiment_id="exp_csv", ticker="TCS.NS", workflow_mode="sequential")
    temp_storage.create_run(run_id=run_id_2, experiment_id="exp_csv", ticker="INFY.NS", workflow_mode="parallel")

    # Complete run 1
    mkt = MarketDataState(status=FindingStatus.AVAILABLE, bar_count=200)
    temp_storage.record_stage_market_data(run_id_1, mkt)
    risk = RiskFindingsState(
        status=FindingStatus.AVAILABLE,
        overall_risk_level="LOW",
        composite_risk_score=0.10,
        recommendation="APPROVED",
    )
    temp_storage.record_stage_risk(run_id_1, risk)
    judge = JudgeEvaluationState(
        status="available",
        configured_model="gemini-3.8-flash",
        actual_model="gemini-3.8-flash",
        overall_score=8.8,
        verdict="GOOD",
        total_tokens=2800,
        latency_ms=1600.0,
        cost_status="actual",
        estimated_cost_usd=0.00028,
    )
    temp_storage.record_stage_judge(run_id_1, judge)
    temp_storage.complete_run(run_id_1, duration_ms=5000.0)

    # Fail run 2 (e.g. market data failure)
    temp_storage.fail_run(run_id_2, error_message="Network error contacting Yahoo Finance", duration_ms=1200.0)

    exported = temp_storage.export_csv(experiment_id="exp_csv")
    assert "runs_summary" in exported
    assert "judge_scores" in exported
    assert "performance_metrics" in exported
    assert "forecast_metrics" in exported

    # 1. runs_summary.csv check
    runs_summary_text = exported["runs_summary"].read_text(encoding="utf-8")
    assert "run_id,experiment_id,ticker,workflow_mode,status" in runs_summary_text
    assert "run_csv_complete" in runs_summary_text
    assert "run_csv_failed" in runs_summary_text
    assert "Network error contacting Yahoo Finance" in runs_summary_text

    # 2. judge_scores.csv check
    judge_text = exported["judge_scores"].read_text(encoding="utf-8")
    assert "factual_grounding,completeness,cross_agent_consistency" in judge_text
    assert "gemini-3.8-flash" in judge_text
    # Run 2 had no judge evaluation, so fields must be empty string, NOT coerced to "0"
    for line in judge_text.splitlines():
        if "run_csv_failed" in line:
            parts = line.split(",")
            # Overall score should be empty
            assert parts[8] == "" or parts[8] == "FAILED"

    # 3. performance_metrics.csv check
    perf_text = exported["performance_metrics"].read_text(encoding="utf-8")
    assert "total_duration_ms,mcp_market_duration_ms,adk_technical_duration_ms" in perf_text

    # 4. forecast_metrics.csv check
    forecast_text = exported["forecast_metrics"].read_text(encoding="utf-8")
    assert "arima_rmse,arima_mae,arima_directional_accuracy" in forecast_text


def test_retrieval_and_filtering(temp_storage: ExperimentStorage):
    """Verify querying runs by ticker, status, and experiment_id with pagination."""
    temp_storage.create_run("r1", "pilot_group", "TCS.NS", "sequential")
    temp_storage.complete_run("r1", 3000.0)

    temp_storage.create_run("r2", "pilot_group", "INFY.NS", "sequential")
    temp_storage.fail_run("r2", "Aborted", 1000.0)

    temp_storage.create_run("r3", "other_group", "TCS.NS", "parallel")
    temp_storage.complete_run("r3", 4000.0)

    # Filter by ticker
    tcs_runs = temp_storage.list_runs(ticker="TCS.NS")
    assert len(tcs_runs) == 2
    assert {r["run_id"] for r in tcs_runs} == {"r1", "r3"}

    # Filter by status
    failed_runs = temp_storage.list_runs(status="FAILED")
    assert len(failed_runs) == 1
    assert failed_runs[0]["run_id"] == "r2"

    # Filter by experiment_id
    pilot_runs = temp_storage.list_runs(experiment_id="pilot_group")
    assert len(pilot_runs) == 2
    assert {r["run_id"] for r in pilot_runs} == {"r1", "r2"}

    # Summary
    summary = temp_storage.get_experiment_summary(experiment_id="pilot_group")
    assert summary["total_runs"] == 2
    assert summary["status_counts"]["COMPLETED"] == 1
    assert summary["status_counts"]["FAILED"] == 1


def test_concurrent_run_creation_thread_safety(temp_storage: ExperimentStorage):
    """Verify SQLite WAL handling under concurrent multi-threaded writes."""
    num_threads = 16

    def worker(idx: int):
        r_id = f"run_concurrent_{idx:03d}"
        temp_storage.create_run(r_id, "concurrent_exp", "TCS.NS", "parallel")
        mkt = MarketDataState(status=FindingStatus.AVAILABLE, bar_count=200)
        temp_storage.record_stage_market_data(r_id, mkt)
        temp_storage.complete_run(r_id, duration_ms=100.0 + idx)
        return r_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, range(num_threads)))

    assert len(results) == num_threads
    stored_runs = temp_storage.list_runs(experiment_id="concurrent_exp", limit=50)
    assert len(stored_runs) == num_threads
    assert all(r["status"] == "COMPLETED" for r in stored_runs)


def test_recovery_after_restart(tmp_path: Path):
    """Verify that re-instantiating ExperimentStorage preserves all previous runs and stages."""
    db_file = tmp_path / "restart_test.db"
    storage1 = ExperimentStorage(db_path=str(db_file), snapshot_dir=str(tmp_path / "snaps"))
    run_id = "run_restart_001"
    storage1.create_run(run_id, "restart_exp", "ICICIBANK.NS", "sequential")
    storage1.record_stage_risk(
        run_id,
        RiskFindingsState(
            status=FindingStatus.AVAILABLE,
            overall_risk_level="LOW",
            composite_risk_score=0.11,
            recommendation="APPROVED",
        ),
    )
    storage1.complete_run(run_id, duration_ms=2500.0)

    # Simulate restart by destroying storage1 and instantiating storage2 on the same db
    del storage1
    storage2 = ExperimentStorage(db_path=str(db_file), snapshot_dir=str(tmp_path / "snaps"))
    recovered = storage2.get_run(run_id)
    assert recovered is not None
    assert recovered["run_id"] == run_id
    assert recovered["ticker"] == "ICICIBANK.NS"
    assert recovered["status"] == RunStatus.COMPLETED.value
    assert recovered["risk"]["composite_score"] == 0.11
    assert recovered["risk"]["recommendation"] == "APPROVED"


def test_fastapi_evaluation_endpoints(monkeypatch, temp_storage: ExperimentStorage):
    """Verify that the 5 FastAPI /evaluations endpoints correctly query storage."""
    from stockshield.api.main import _workflow

    # Inject isolated storage fixture into global workflow
    monkeypatch.setattr(_workflow, "storage", temp_storage)

    run_id = "run_api_test_001"
    temp_storage.create_run(run_id, "api_exp", "TCS.NS", "sequential")
    temp_storage.complete_run(run_id, duration_ms=1800.0, snapshot_data={"run_id": run_id, "status": "ok"})

    client = TestClient(app)

    # 1. GET /evaluations/runs
    res = client.get("/evaluations/runs?experiment_id=api_exp")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 1
    assert data["runs"][0]["run_id"] == run_id

    # 2. GET /evaluations/runs/{run_id}
    res = client.get(f"/evaluations/runs/{run_id}")
    assert res.status_code == 200
    assert res.json()["run_id"] == run_id
    assert res.json()["ticker"] == "TCS.NS"

    # 3. GET /evaluations/summary
    res = client.get("/evaluations/summary?experiment_id=api_exp")
    assert res.status_code == 200
    assert res.json()["total_runs"] == 1
    assert res.json()["status_counts"]["COMPLETED"] == 1

    # 4. GET /evaluations/export/csv
    res = client.get("/evaluations/export/csv?experiment_id=api_exp")
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "runs_summary" in res.json()["exported_files"]

    # 5. GET /evaluations/snapshots/{run_id}
    res = client.get(f"/evaluations/snapshots/{run_id}")
    assert res.status_code == 200
    assert res.json()["run_id"] == run_id
    assert res.json()["status"] == "ok"
