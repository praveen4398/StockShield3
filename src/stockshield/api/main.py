"""FastAPI application for StockShield 2.0."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from stockshield import __version__
from stockshield.a2a.server import a2a_router
from stockshield.geni import geni_router
from stockshield.orchestration.workflow import StockShieldWorkflow
from stockshield.simulation.models import CustomScenarioInput

app = FastAPI(
    title="StockShield 2.0 — Agentic Stock Analysis & Risk Intelligence API",
    description="Institutional multi-agent stock analysis system built with Google ADK, CrewAI, MCP, and Blackboard Architecture.",
    version=__version__,
)

app.include_router(a2a_router)
app.include_router(geni_router)

# Enable CORS for institutional dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_workflow = StockShieldWorkflow()
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_INDEX_HTML_PATH = _STATIC_DIR / "index.html"

# Discover modern Frontend directory (in project root)
_FRONTEND_DIR = Path(__file__).resolve().parents[3] / "Frontend"
_FRONTEND_INDEX_PATH = _FRONTEND_DIR / "index.html"

# Mount static asset directories for the modern Frontend
if _FRONTEND_DIR.exists():
    for sub in ["css", "js", "assets"]:
        subdir = _FRONTEND_DIR / sub
        if subdir.exists():
            app.mount(f"/{sub}", StaticFiles(directory=str(subdir)), name=sub)


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the modern StockShield frontend dashboard."""
    no_cache_headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    if _FRONTEND_INDEX_PATH.exists():
        return HTMLResponse(
            content=_FRONTEND_INDEX_PATH.read_text(encoding="utf-8"),
            headers=no_cache_headers,
        )
    if _INDEX_HTML_PATH.exists():
        return HTMLResponse(
            content=_INDEX_HTML_PATH.read_text(encoding="utf-8"),
            headers=no_cache_headers,
        )
    return HTMLResponse("<h2>StockShield Dashboard not found.</h2>", status_code=404)


@app.get("/whiteboard", response_class=HTMLResponse)
async def serve_whiteboard():
    """Serve the visual whiteboard dashboard."""
    if _INDEX_HTML_PATH.exists():
        return HTMLResponse(content=_INDEX_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>StockShield Whiteboard not found.</h2>", status_code=404)


class AnalysisRequestPayload(BaseModel):
    ticker: str = Field(
        ...,
        description="Indian NSE equity ticker, e.g., TCS.NS, INFY.NS, RELIANCE.NS, HDFCBANK.NS, WIPRO.NS",
    )
    user_prompt: str = Field(
        default="Conduct institutional technical momentum and deterministic risk intelligence review.",
        description="User analysis directive or query",
    )
    lookback_days: int = Field(default=200, ge=1, le=1000, description="Lookback trading bars (sessions)")
    workflow_mode: str = Field(
        default="sequential",
        description="Execution topology: sequential, parallel, or hierarchical",
    )
    time_horizon: str = Field(
        default="short_term",
        description="Investment horizon: 'short_term' (tactical momentum, 1-30 days), 'mid_term' (positional trend, 1-6 months), or 'long_term' (fundamental/structural, 1-2+ years)",
    )
    forecast_horizon: str = Field(
        default="1_month",
        description="Prediction horizon dropdown selection: '1_month', '3_months', '6_months', '1_year', '2_years'",
    )
    risk_profile: str = Field(default="moderate", description="conservative, moderate, aggressive")
    provider_mode: str = Field(
        default="auto",
        description="Market data provider mode: 'auto' (fixture if available, else Yahoo Finance), 'fixture' (offline), or 'live' (Yahoo Finance)",
    )
    enable_judge: Optional[bool] = Field(
        default=True,
        description="Whether to execute Gemini LLM-as-a-Judge post-analysis evaluation. If None, inherits LLM_JUDGE_ENABLED setting.",
    )
    custom_scenarios: Optional[List[CustomScenarioInput]] = Field(
        default=None,
        description="Optional list of custom user-defined stress scenarios with validated parameters",
    )
    experiment_id: Optional[str] = Field(
        default="default_experiment",
        description="Empirical benchmark or pilot evaluation grouping identifier",
    )


class SimulationRequestPayload(BaseModel):
    ticker: str = Field(..., description="Indian NSE equity ticker, e.g., TCS.NS, INFY.NS")
    user_prompt: str = Field(
        default="Run scenario simulation, deterministic stress testing, and sensitivity analysis.",
        description="User simulation directive",
    )
    lookback_days: int = Field(default=200, ge=1, le=1000, description="Lookback trading bars (sessions)")
    workflow_mode: str = Field(default="sequential", description="sequential, parallel, or hierarchical")
    time_horizon: str = Field(default="short_term", description="short_term, mid_term, or long_term")
    forecast_horizon: str = Field(default="1_month", description="1_month, 3_months, 6_months, 1_year, 2_years")
    experiment_id: Optional[str] = Field(
        default="default_experiment",
        description="Empirical benchmark or pilot evaluation grouping identifier",
    )
    predefined_scenarios: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific predefined scenario names or slugs to evaluate",
    )
    custom_scenarios: Optional[List[CustomScenarioInput]] = Field(
        default=None,
        description="Optional list of custom user-defined stress scenarios with validated parameters",
    )
    include_monte_carlo: bool = Field(
        default=True,
        description="Whether to execute stochastic Monte Carlo price-path simulations",
    )
    monte_carlo_simulations: int = Field(default=1000, ge=10, le=10000)
    monte_carlo_horizon_days: int = Field(default=20, ge=1, le=100)
    portfolio_shares: Optional[float] = Field(default=None, ge=0.0)
    portfolio_value: Optional[float] = Field(default=None, ge=0.0)
    provider_mode: str = Field(default="auto")


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp_utc: str
    mcp_tools: List[str]
    allowed_tickers: List[str]
    supported_provider_modes: List[str] = Field(default_factory=lambda: ["auto", "fixture", "live"])
    gemini_judge_configured: bool = False
    environment: str


@app.get("/health", response_model=HealthResponse)
@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Liveness and health readiness probe."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        mcp_tools=["get_historical_market_data", "compute_financial_ratios", "search_financial_document"],
        allowed_tickers=["TCS.NS", "INFY.NS", "RELIANCE.NS"],
        supported_provider_modes=["auto", "fixture", "live"],
        gemini_judge_configured=bool(os.getenv("GEMINI_API_KEY")),
        environment="production" if False else "development",
    )


@app.get("/.well-known/agent.json")
async def get_adk_agent_card():
    """A2A protocol AgentCard discovery endpoint for Google ADK Technical Agent."""
    return _workflow.technical_agent.get_agent_card()


# ---------------------------------------------------------------------------
# Live Ticker Tape Market Data Endpoint
# ---------------------------------------------------------------------------
_DEFAULT_TICKER_ITEMS = [
    {"sym": "NIFTY50", "display": "NIFTY50", "ticker": "^NSEI", "price": "24,850.30", "change": "+0.45%", "is_up": True, "is_index": True},
    {"sym": "SENSEX", "display": "SENSEX", "ticker": "^BSESN", "price": "81,520.10", "change": "+0.38%", "is_up": True, "is_index": True},
    {"sym": "TCS", "display": "TCS", "ticker": "TCS.NS", "price": "₹3,842.50", "change": "+1.20%", "is_up": True, "is_index": False},
    {"sym": "INFY", "display": "INFY", "ticker": "INFY.NS", "price": "₹1,648.90", "change": "-0.40%", "is_up": False, "is_index": False},
    {"sym": "RELIANCE", "display": "RELIANCE", "ticker": "RELIANCE.NS", "price": "₹2,934.60", "change": "+0.80%", "is_up": True, "is_index": False},
    {"sym": "HDFCBANK", "display": "HDFCBANK", "ticker": "HDFCBANK.NS", "price": "₹1,789.40", "change": "+1.50%", "is_up": True, "is_index": False},
    {"sym": "WIPRO", "display": "WIPRO", "ticker": "WIPRO.NS", "price": "₹298.75", "change": "-0.90%", "is_up": False, "is_index": False},
    {"sym": "ICICIBANK", "display": "ICICIBANK", "ticker": "ICICIBANK.NS", "price": "₹1,245.30", "change": "+0.60%", "is_up": True, "is_index": False},
    {"sym": "BAJFINANCE", "display": "BAJFINANCE", "ticker": "BAJFINANCE.NS", "price": "₹7,129.80", "change": "+2.10%", "is_up": True, "is_index": False},
    {"sym": "SBIN", "display": "SBIN", "ticker": "SBIN.NS", "price": "₹852.40", "change": "-0.30%", "is_up": False, "is_index": False},
    {"sym": "TATAMOTORS", "display": "TATAMOTORS", "ticker": "TATAMOTORS.NS", "price": "₹978.30", "change": "+1.40%", "is_up": True, "is_index": False},
    {"sym": "TATASTEEL", "display": "TATASTEEL", "ticker": "TATASTEEL.NS", "price": "₹152.60", "change": "+0.75%", "is_up": True, "is_index": False},
]

_ticker_cache = {
    "last_updated": 0.0,
    "items": _DEFAULT_TICKER_ITEMS.copy(),
    "source": "baseline",
    "is_refreshing": False,
}


def _refresh_ticker_cache_worker():
    """Background worker to fetch latest prices from Yahoo Finance without blocking HTTP requests."""
    try:
        import time
        import yfinance as yf
        tickers = [item["ticker"] for item in _DEFAULT_TICKER_ITEMS]
        df = yf.download(tickers, period="5d", interval="1d", progress=False, timeout=8)
        if df is not None and not df.empty and "Close" in df:
            close_df = df["Close"]
            updated = []
            for item in _DEFAULT_TICKER_ITEMS:
                sym_ticker = item["ticker"]
                display = item["display"]
                is_index = item["is_index"]
                prefix = "" if is_index else "₹"
                try:
                    if sym_ticker in close_df:
                        series = close_df[sym_ticker].dropna()
                        if len(series) >= 1:
                            last_price = float(series.iloc[-1])
                            prev_close = float(series.iloc[-2]) if len(series) >= 2 else last_price
                            pct_change = ((last_price - prev_close) / prev_close * 100.0) if prev_close else 0.0
                            is_up = pct_change >= 0.0
                            sign = "+" if is_up else ""
                            price_str = f"{prefix}{last_price:,.2f}" if last_price >= 1000 else f"{prefix}{last_price:.2f}"
                            updated.append({
                                "sym": display,
                                "display": display,
                                "ticker": sym_ticker,
                                "price": price_str,
                                "change": f"{sign}{pct_change:.2f}%",
                                "is_up": is_up,
                                "is_index": is_index,
                            })
                            continue
                except Exception:
                    pass
                updated.append(item)

            if updated:
                _ticker_cache["items"] = updated
                _ticker_cache["last_updated"] = time.time()
                _ticker_cache["source"] = "live"
    except Exception:
        pass
    finally:
        _ticker_cache["is_refreshing"] = False


@app.get("/api/ticker-tape")
@app.get("/ticker-prices")
def get_live_ticker_tape():
    """Retrieve live quotes for top Indian market indices and equities to power the scrolling ticker tape on page load."""
    import time
    import threading
    now = time.time()

    # If cache is older than 90 seconds and not already refreshing in background, trigger refresh
    if (now - _ticker_cache["last_updated"] > 90.0) and not _ticker_cache["is_refreshing"]:
        _ticker_cache["is_refreshing"] = True
        threading.Thread(target=_refresh_ticker_cache_worker, daemon=True).start()

    return {
        "status": "success",
        "source": _ticker_cache.get("source", "baseline"),
        "items": _ticker_cache["items"],
    }


@app.post("/analyze")
async def analyze_stock(payload: AnalysisRequestPayload):
    """Execute end-to-end multi-agent stock analysis and risk intelligence pipeline."""
    try:
        blackboard_state = await _workflow.run(
            raw_request=payload.model_dump(),
            workflow_mode=payload.workflow_mode,
        )

        judge_eval = blackboard_state.judge_evaluation
        judge_is_available = judge_eval.status == "available"

        judge_in = (judge_eval.input_tokens or 0) if judge_is_available else 0
        judge_out = (judge_eval.output_tokens or 0) if judge_is_available else 0
        judge_tot = (judge_eval.total_tokens or (judge_in + judge_out)) if judge_is_available else 0

        stub_usage = blackboard_state.token_usage or {}
        stub_in = stub_usage.get("input_tokens", 0)
        stub_out = stub_usage.get("output_tokens", 0)
        stub_tot = stub_usage.get("total_tokens", stub_in + stub_out)

        total_tokens_dict = {
            "input_tokens": stub_in + judge_in,
            "output_tokens": stub_out + judge_out,
            "total_tokens": stub_tot + judge_tot,
        }

        if judge_is_available:
            if judge_eval.estimated_cost_usd is None:
                total_cost_usd = None
                cost_status_overall = "unavailable"
            else:
                total_cost_usd = round(blackboard_state.cost_estimation_usd + judge_eval.estimated_cost_usd, 6)
                cost_status_overall = "actual" if judge_eval.cost_status == "actual" else "estimated"
        else:
            total_cost_usd = blackboard_state.cost_estimation_usd
            cost_status_overall = "zero_cost_stub"

        # Safely extract optional model and scenario outputs to ensure strict type safety in IDEs
        best_m = blackboard_state.forecasting.best_model
        best_model_name = best_m.model_name if best_m else None
        forecasts_list = [
            {
                "step": p.step,
                "target_date": p.target_date,
                "predicted_price": p.predicted_price,
                "pct_change": p.pct_change,
                "conf_lower": p.conf_lower,
                "conf_upper": p.conf_upper,
            }
            for p in (best_m.forecasts if best_m else [])
        ]

        worst_case = blackboard_state.scenario_simulation.worst_case_scenario
        worst_case_dict = None
        if worst_case and worst_case.simulated:
            worst_case_dict = {
                "name": worst_case.scenario_name,
                "risk_score": worst_case.simulated.scenario_risk_score,
                "recommendation": worst_case.simulated.scenario_recommendation,
            }

        best_case = blackboard_state.scenario_simulation.best_case_scenario
        best_case_dict = None
        if best_case and best_case.simulated:
            best_case_dict = {
                "name": best_case.scenario_name,
                "risk_score": best_case.simulated.scenario_risk_score,
                "recommendation": best_case.simulated.scenario_recommendation,
            }

        response_payload = {
            "run_id": blackboard_state.run_id,
            "trace_id": blackboard_state.trace_id,
            "workflow_status": blackboard_state.workflow_status.value,
            "ticker": blackboard_state.ticker,
            "time_horizon": blackboard_state.time_horizon,
            "forecast_horizon": blackboard_state.forecast_horizon,
            "market_data": {
                "status": blackboard_state.market_data.status.value,
                "source": blackboard_state.market_data.source,
                "bar_count": blackboard_state.market_data.bar_count,
                "data_quality": blackboard_state.market_data.data_quality_status,
                "is_stale": blackboard_state.market_data.is_stale,
                "freshness_age_days": blackboard_state.market_data.freshness_age_days,
                "bars": [
                    {
                        "timestamp": b.timestamp,
                        "close": b.close,
                        "open": b.open,
                        "high": b.high,
                        "low": b.low,
                        "volume": b.volume,
                    }
                    for b in blackboard_state.market_data.bars
                ],
            },
            "technical_findings": {
                "status": blackboard_state.technical_findings.status.value,
                "signal": blackboard_state.technical_findings.signal,
                "confidence": blackboard_state.technical_findings.signal_confidence,
                "indicators": blackboard_state.technical_findings.indicators.model_dump(),
                "summary": blackboard_state.technical_findings.summary,
            },
            "risk_findings": {
                "status": blackboard_state.risk_findings.status.value,
                "risk_level": blackboard_state.risk_findings.overall_risk_level,
                "composite_score": blackboard_state.risk_findings.composite_risk_score,
                "recommendation": blackboard_state.risk_findings.recommendation,
                "warnings": blackboard_state.risk_findings.warnings,
                "reasons": blackboard_state.risk_findings.reasons,
                "checks": [
                    {
                        "name": c.name,
                        "passed": c.passed,
                        "score": c.score,
                        "message": c.message,
                    }
                    for c in blackboard_state.risk_findings.checks
                ],
            },
            "news_and_sentiment": {
                "status": blackboard_state.news_sentiment.status.value,
                "source": blackboard_state.news_sentiment.source,
                "overall_sentiment": blackboard_state.news_sentiment.overall_sentiment,
                "sentiment_score": blackboard_state.news_sentiment.sentiment_score,
                "article_counts": {
                    "total": blackboard_state.news_sentiment.total_articles,
                    "positive": blackboard_state.news_sentiment.positive_count,
                    "neutral": blackboard_state.news_sentiment.neutral_count,
                    "negative": blackboard_state.news_sentiment.negative_count,
                },
                "positive_events": blackboard_state.news_sentiment.positive_events,
                "negative_events": blackboard_state.news_sentiment.negative_events,
                "risk_observations": blackboard_state.news_sentiment.risk_observations,
                "articles_sample": [
                    {
                        "title": a.article.title,
                        "source": a.article.source,
                        "published_date": a.article.published_date,
                        "url": a.article.url,
                        "sentiment": a.sentiment,
                        "confidence": a.confidence,
                        "topic": a.financial_event_topic,
                    }
                    for a in blackboard_state.news_sentiment.articles[:5]
                ],
            },
            "forecasting": {
                "status": blackboard_state.forecasting.status.value,
                "is_stale_data": blackboard_state.forecasting.is_stale_data,
                "forecast_label": blackboard_state.forecasting.forecast_label,
                "best_model": best_model_name,
                "model_divergence_pct": blackboard_state.forecasting.model_divergence_pct,
                "directional_consensus": blackboard_state.forecasting.directional_consensus,
                "models_evaluated": [
                    {
                        "model_name": m.model_name,
                        "status": m.status,
                        "rmse": getattr(m.validation_metrics, "rmse", None),
                        "mae": getattr(m.validation_metrics, "mae", None),
                        "directional_accuracy": getattr(m.validation_metrics, "directional_accuracy", None),
                    }
                    for m in blackboard_state.forecasting.models
                ],
                "forecasts": forecasts_list,
            },
            "scenario_simulation": {
                "status": blackboard_state.scenario_simulation.status.value,
                "total_scenarios": blackboard_state.scenario_simulation.total_scenarios_evaluated,
                "baseline_metrics": {
                    "stock_price": blackboard_state.scenario_simulation.baseline_price,
                    "volatility_pct": blackboard_state.scenario_simulation.baseline_volatility_pct,
                    "sentiment_score": blackboard_state.scenario_simulation.baseline_sentiment_score,
                    "risk_score": blackboard_state.scenario_simulation.baseline_risk_score,
                    "risk_level": blackboard_state.scenario_simulation.baseline_risk_level,
                    "recommendation": blackboard_state.scenario_simulation.baseline_recommendation,
                },
                "worst_case_scenario": worst_case_dict,
                "best_case_scenario": best_case_dict,
                "scenarios_flipping_recommendation": blackboard_state.scenario_simulation.scenarios_changing_recommendation,
                "scenarios_material_risk_increase": blackboard_state.scenario_simulation.scenarios_material_risk_increase,
                "scenarios": [
                    {
                        "name": s.scenario_name,
                        "category": s.category.value if hasattr(s.category, "value") else str(s.category),
                        "description": s.description,
                        "percentage_price_change": s.simulated.percentage_price_change if s.simulated else None,
                        "hypothetical_price": s.simulated.hypothetical_price if s.simulated else None,
                        "absolute_price_change": s.simulated.absolute_price_change if s.simulated else None,
                        "portfolio_value_impact": s.simulated.portfolio_value_impact if s.simulated else None,
                        "adjusted_volatility_pct": s.simulated.hypothetical_volatility_pct if s.simulated else None,
                        "scenario_risk_score": s.simulated.scenario_risk_score if s.simulated else None,
                        "scenario_risk_level": s.simulated.scenario_risk_level if s.simulated else None,
                        "scenario_recommendation": s.simulated.scenario_recommendation if s.simulated else None,
                        "risk_score_delta": s.comparison.risk_score_delta if s.comparison else None,
                        "recommendation_changed": s.comparison.recommendation_changed if s.comparison else False,
                        "assumptions": s.assumptions,
                    }
                    for s in blackboard_state.scenario_simulation.scenarios
                ],
                "monte_carlo": blackboard_state.scenario_simulation.monte_carlo_result.model_dump() if blackboard_state.scenario_simulation.monte_carlo_result else None,
                "warnings": blackboard_state.scenario_simulation.warnings,
            },
            "final_report": {
                "executive_summary": blackboard_state.final_report.executive_summary,
                "markdown_report": blackboard_state.final_report.markdown_content,
            },
            "judge_evaluation": {
                "status": blackboard_state.judge_evaluation.status,
                "model_name": blackboard_state.judge_evaluation.model_name,
                "configured_model": blackboard_state.judge_evaluation.configured_model,
                "actual_model": blackboard_state.judge_evaluation.actual_model,
                "fallback_triggered": blackboard_state.judge_evaluation.fallback_triggered,
                "has_sufficient_evidence": blackboard_state.judge_evaluation.has_sufficient_evidence,
                "overall_score": blackboard_state.judge_evaluation.overall_score,
                "verdict": blackboard_state.judge_evaluation.verdict,
                "critical_findings": blackboard_state.judge_evaluation.critical_findings,
                "warnings": blackboard_state.judge_evaluation.warnings,
                "strengths": blackboard_state.judge_evaluation.strengths,
                "limitations": blackboard_state.judge_evaluation.limitations,
                "evaluation_summary": blackboard_state.judge_evaluation.evaluation_summary,
                "dimensions": {
                    k: {
                        "dimension": getattr(getattr(v, "dimension", None), "value", getattr(v, "dimension", k)),
                        "score": getattr(v, "score", None),
                        "explanation": getattr(v, "explanation", ""),
                        "evidence_references": getattr(v, "evidence_references", []),
                        "identified_issues": getattr(v, "identified_issues", []),
                    }
                    for k, v in blackboard_state.judge_evaluation.dimensions.items()
                },
                "latency_ms": blackboard_state.judge_evaluation.latency_ms,
                "input_tokens": blackboard_state.judge_evaluation.input_tokens,
                "output_tokens": blackboard_state.judge_evaluation.output_tokens,
                "total_tokens": blackboard_state.judge_evaluation.total_tokens,
                "estimated_cost_usd": blackboard_state.judge_evaluation.estimated_cost_usd,
                "cost_status": blackboard_state.judge_evaluation.cost_status,
                "attempt_history": blackboard_state.judge_evaluation.attempt_history,
                "error_message": blackboard_state.judge_evaluation.error_message,
            },
            "audit_and_provenance": {
                "agent_statuses": blackboard_state.agent_statuses,
                "provenance_records_count": len(blackboard_state.provenance_trail),
                "execution_events_count": len(blackboard_state.execution_events),
                "execution_events": blackboard_state.execution_events,
                "validation_errors": blackboard_state.validation_errors,
            },
            "cost_and_tokens": {
                "tokens": total_tokens_dict,
                "estimated_cost_usd": total_cost_usd,
                "cost_status": cost_status_overall,
            },
        }
        _workflow.storage.attach_final_response(blackboard_state.run_id, response_payload)
        return JSONResponse(content=response_payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal pipeline error: {str(e)}")


@app.post("/simulate")
async def simulate_scenarios(payload: SimulationRequestPayload):
    """Execute scenario simulation, stress testing, and sensitivity analysis."""
    try:
        req_dict = payload.model_dump()
        blackboard_state = await _workflow.run(
            raw_request=req_dict,
            workflow_mode=payload.workflow_mode,
        )

        sim = blackboard_state.scenario_simulation
        worst_sim = sim.worst_case_scenario
        worst_sim_dict = (
            {
                "name": worst_sim.scenario_name,
                "category": getattr(worst_sim.category, "value", str(worst_sim.category)),
                "hypothetical_price": getattr(worst_sim.simulated, "hypothetical_price", None),
                "risk_score": getattr(worst_sim.simulated, "scenario_risk_score", None),
                "risk_level": getattr(worst_sim.simulated, "scenario_risk_level", None),
                "recommendation": getattr(worst_sim.simulated, "scenario_recommendation", None),
                "risk_score_delta": getattr(worst_sim.comparison, "risk_score_delta", None),
                "explanation": getattr(worst_sim.comparison, "explanation", ""),
            }
            if worst_sim and worst_sim.simulated and worst_sim.comparison
            else None
        )

        best_sim = sim.best_case_scenario
        best_sim_dict = (
            {
                "name": best_sim.scenario_name,
                "risk_score": getattr(best_sim.simulated, "scenario_risk_score", None),
                "recommendation": getattr(best_sim.simulated, "scenario_recommendation", None),
            }
            if best_sim and best_sim.simulated
            else None
        )

        sim_payload = {
            "run_id": blackboard_state.run_id,
            "trace_id": blackboard_state.trace_id,
            "ticker": blackboard_state.ticker,
            "workflow_status": blackboard_state.workflow_status.value,
            "status": sim.status.value,
            "baseline_metrics": {
                "stock_price": sim.baseline_price,
                "volatility_pct": sim.baseline_volatility_pct,
                "sentiment_score": sim.baseline_sentiment_score,
                "risk_score": sim.baseline_risk_score,
                "risk_level": sim.baseline_risk_level,
                "recommendation": sim.baseline_recommendation,
            },
            "total_scenarios_evaluated": sim.total_scenarios_evaluated,
            "worst_case_scenario": worst_sim_dict,
            "best_case_scenario": best_sim_dict,
            "scenarios_changing_recommendation": sim.scenarios_changing_recommendation,
            "scenarios_material_risk_increase": sim.scenarios_material_risk_increase,
            "scenarios": [
                {
                    "scenario_name": s.scenario_name,
                    "category": s.category.value,
                    "description": s.description,
                    "price_shock_pct": s.simulated.percentage_price_change,
                    "hypothetical_price": s.simulated.hypothetical_price,
                    "absolute_price_change": s.simulated.absolute_price_change,
                    "portfolio_value_impact": s.simulated.portfolio_value_impact,
                    "adjusted_volatility_pct": s.simulated.hypothetical_volatility_pct,
                    "volatility_change_pct": s.simulated.volatility_change_pct,
                    "hypothetical_sentiment_score": s.simulated.hypothetical_sentiment_score,
                    "hypothetical_sentiment_label": s.simulated.hypothetical_sentiment_label,
                    "scenario_risk_score": s.simulated.scenario_risk_score,
                    "scenario_risk_level": s.simulated.scenario_risk_level,
                    "scenario_recommendation": s.simulated.scenario_recommendation,
                    "risk_score_delta": s.comparison.risk_score_delta,
                    "recommendation_changed": s.comparison.recommendation_changed,
                    "recommendation_flip_direction": s.comparison.recommendation_flip_direction,
                    "material_risk_increase": s.comparison.material_risk_increase,
                    "assumptions": s.assumptions,
                }
                for s in sim.scenarios
            ],
            "monte_carlo": sim.monte_carlo_result.model_dump() if sim.monte_carlo_result else None,
            "warnings": sim.warnings,
        }
        _workflow.storage.attach_final_response(blackboard_state.run_id, sim_payload)
        return JSONResponse(content=sim_payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scenario simulation error: {str(e)}")


# ---------------------------------------------------------------------------
# Evaluation & Benchmark Endpoints
# ---------------------------------------------------------------------------
@app.get("/evaluations/runs")
async def list_evaluation_runs(
    ticker: Optional[str] = None,
    status: Optional[str] = None,
    experiment_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List runs with filtering by ticker, status, and experiment_id."""
    runs = _workflow.storage.list_runs(
        ticker=ticker,
        status=status,
        experiment_id=experiment_id,
        limit=limit,
        offset=offset,
    )
    return {"runs": runs, "count": len(runs), "limit": limit, "offset": offset}


@app.get("/evaluations/runs/{run_id}")
async def get_evaluation_run(run_id: str):
    """Retrieve complete run record including all constituent stages."""
    run = _workflow.storage.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return run


@app.get("/evaluations/summary")
async def get_evaluations_summary(experiment_id: Optional[str] = None):
    """Aggregate statistical summary across stored evaluation runs."""
    summary = _workflow.storage.get_experiment_summary(experiment_id=experiment_id)
    return summary


@app.get("/evaluations/export/csv")
async def export_evaluations_csv(experiment_id: Optional[str] = None):
    """Trigger CSV export and return absolute file paths for all 4 academic CSV files."""
    exported_files = _workflow.storage.export_csv(experiment_id=experiment_id)
    return {
        "status": "success",
        "experiment_id": experiment_id or "all_experiments",
        "exported_files": {k: str(v) for k, v in exported_files.items()},
    }


@app.get("/evaluations/snapshots/{run_id}")
async def get_evaluation_snapshot(run_id: str):
    """Retrieve the complete raw JSON snapshot for a run."""
    snap_path = _workflow.storage.export_snapshot(run_id)
    if not snap_path or not snap_path.exists():
        run_data = _workflow.storage.get_run(run_id)
        if run_data and run_data.get("snapshot_json"):
            return json.loads(run_data["snapshot_json"])
        raise HTTPException(status_code=404, detail=f"Snapshot for run '{run_id}' not found.")
    return json.loads(snap_path.read_text(encoding="utf-8"))
