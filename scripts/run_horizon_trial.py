"""Trial execution script evaluating StockShield 2.0 multi-agent intelligence across Short-Term, Mid-Term, and Long-Term seasons.

Ensures all three horizons evaluate the EXACT SAME market-data snapshot (same source, same latest price, same end date)
by slicing the historical lookback (100, 200, 500 bars) from the master snapshot.
Evaluates both TCS.NS and INFY.NS and saves structured comparative output to evaluation_results/horizon_analysis_trial.json.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stockshield.mcp.provider import MarketDataRequest  # noqa: E402
from stockshield.orchestration.workflow import StockShieldWorkflow  # noqa: E402

HORIZON_CONFIGS = [
    {
        "horizon": "short_term",
        "forecast_horizon": "1_month",
        "lookback_days": 100,
        "label": "Short-Term Tactical Momentum (1–30 Days)",
        "description": "Tactical trading season focusing on fast RSI momentum, ATR breakout, and 1-month predictive price paths."
    },
    {
        "horizon": "mid_term",
        "forecast_horizon": "3_months",
        "lookback_days": 200,
        "label": "Mid-Term Positional Trend (1–6 Months)",
        "description": "Positional swing/quarterly trend season focusing on SMA 20/50 alignment, MACD cycle, and quarterly earnings trajectory."
    },
    {
        "horizon": "long_term",
        "forecast_horizon": "1_year",
        "lookback_days": 500,
        "label": "Long-Term Strategic Fundamental (1–2+ Years)",
        "description": "Strategic asset holding season anchored to 200-day moving average regime, macro stress survival, and 1-year annual horizons."
    }
]


def get_bar_close(bar) -> float:
    return float(bar.close if hasattr(bar, "close") else bar["close"])


async def run_ticker_horizons(workflow: StockShieldWorkflow, ticker: str, provider_mode: str = "auto") -> dict:
    """Execute multi-horizon trial for a single ticker using a unified market snapshot."""
    print("\n========================================================")
    print(f"Acquiring Master Snapshot for {ticker} (lookback=500, mode={provider_mode})...")
    print("========================================================")

    # 1. Fetch master snapshot first
    master_req = MarketDataRequest(ticker=ticker, lookback_days=500, provider_mode=provider_mode)
    master_snap = workflow.market_provider.get_market_data(master_req)

    is_live = master_snap.source == "yahoo_finance" and not master_snap.is_stale
    latest_close = get_bar_close(master_snap.bars[-1]) if master_snap.bars else None
    end_date = master_snap.end_date

    print(f"Master Snapshot acquired: Source={master_snap.source}, Bars={master_snap.bar_count}, "
          f"Latest Close={latest_close}, End Date={end_date}, Live Comparable={is_live}")

    ticker_results = {
        "ticker": ticker,
        "snapshot_metadata": {
            "source": master_snap.source,
            "data_quality_status": master_snap.data_quality_status,
            "is_stale": master_snap.is_stale,
            "freshness_age_days": master_snap.freshness_age_days,
            "latest_close": latest_close,
            "master_bar_count": master_snap.bar_count,
            "start_date": master_snap.start_date,
            "end_date": end_date,
            "comparable_live": is_live,
            "stale_notice": None if is_live else "Trial executed with offline fixture data; do not treat as comparable live session."
        },
        "horizon_runs": {},
        "comparative_matrix": []
    }

    for config in HORIZON_CONFIGS:
        h = config["horizon"]
        fc_h = config["forecast_horizon"]
        lb = config["lookback_days"]
        print(f"\n--- Executing Horizon: {config['label']} ({lb} bars, {fc_h}) ---")

        raw_request = {
            "ticker": ticker,
            "user_prompt": f"Conduct institutional {h.replace('_', ' ')} analysis and risk review for {ticker}.",
            "lookback_days": lb,
            "workflow_mode": "sequential",
            "time_horizon": h,
            "forecast_horizon": fc_h,
            "risk_profile": "moderate",
            "provider_mode": provider_mode,
            "enable_judge": False  # Zero external token cost
        }

        blackboard_state = await workflow.run(raw_request=raw_request, workflow_mode="sequential")

        tech = blackboard_state.technical_findings
        risk = blackboard_state.risk_findings
        mkt = blackboard_state.market_data
        news = blackboard_state.news_sentiment
        fc = blackboard_state.forecasting
        sim = blackboard_state.scenario_simulation
        rep = blackboard_state.final_report

        # Verify unified snapshot invariants
        assert mkt.source == master_snap.source, f"Source mismatch: {mkt.source} vs {master_snap.source}"
        if mkt.bars and master_snap.bars:
            mkt_close = get_bar_close(mkt.bars[-1])
            snap_close = get_bar_close(master_snap.bars[-1])
            assert mkt_close == snap_close, f"Close mismatch: {mkt_close} vs {snap_close}"
            assert mkt.end_date == master_snap.end_date, f"End date mismatch: {mkt.end_date} vs {master_snap.end_date}"

        # Extract structured forecasts
        fc_list = []
        if fc.best_model and fc.best_model.forecasts:
            for p in fc.best_model.forecasts:
                fc_list.append({
                    "horizon_trading_days": p.step,
                    "target_date": p.target_date,
                    "predicted_price": p.predicted_price,
                    "predicted_change_pct": p.pct_change,
                    "confidence_interval_95": [p.conf_lower, p.conf_upper]
                })

        # Extract Monte Carlo info
        mc_info = None
        if sim.monte_carlo_result:
            mc = sim.monte_carlo_result
            mc_info = {
                "horizon_days": mc.horizon_days,
                "num_simulations": mc.num_simulations,
                "initial_price": mc.initial_price,
                "mean_terminal_price": mc.mean_terminal_price,
                "median_terminal_price": mc.median_terminal_price,
                "quantiles": {
                    "p5": mc.percentile_5_price,
                    "p25": mc.percentile_25_price,
                    "p75": mc.percentile_75_price,
                    "p95": mc.percentile_95_price,
                },
                "probability_loss_pct": mc.probability_loss_pct,
                "probability_severe_loss_pct": mc.probability_severe_loss_pct,
                "expected_annualized_volatility": mc.expected_annualized_volatility,
            }

        curr_close = get_bar_close(mkt.bars[-1]) if mkt.bars else None
        run_output = {
            "configuration": config,
            "run_id": blackboard_state.run_id,
            "trace_id": blackboard_state.trace_id,
            "workflow_status": blackboard_state.workflow_status.value,
            "market_data_courier": {
                "source": mkt.source,
                "bar_count": mkt.bar_count,
                "start_date": mkt.start_date,
                "end_date": mkt.end_date,
                "latest_close": curr_close,
                "data_quality": mkt.data_quality_status,
                "is_stale": mkt.is_stale,
                "freshness_age_days": mkt.freshness_age_days
            },
            "technical_agent": {
                "signal": tech.signal,
                "confidence": tech.signal_confidence,
                "indicators": tech.indicators.model_dump(),
                "summary": tech.summary
            },
            "news_sentiment_agent": {
                "overall_sentiment": news.overall_sentiment,
                "sentiment_score": news.sentiment_score,
                "total_articles": news.total_articles,
                "positive_count": news.positive_count,
                "negative_count": news.negative_count,
                "risk_observations": news.risk_observations
            },
            "forecasting_agent": {
                "status": fc.status.value,
                "best_model": fc.best_model.model_name if fc.best_model else "NONE",
                "model_divergence_pct": fc.model_divergence_pct,
                "directional_consensus": fc.directional_consensus,
                "validation_rmse": fc.best_model.validation_metrics.rmse if fc.best_model else None,
                "validation_directional_accuracy": fc.best_model.validation_metrics.directional_accuracy if fc.best_model else None,
                "forecast_window": fc_h,
                "projections": fc_list
            },
            "risk_engine": {
                "overall_risk_level": risk.overall_risk_level,
                "composite_risk_score": risk.composite_risk_score,
                "recommendation": risk.recommendation,
                "warnings": risk.warnings,
                "reasons": risk.reasons
            },
            "scenario_simulation_agent": {
                "total_scenarios": sim.total_scenarios_evaluated,
                "worst_case_scenario": sim.worst_case_scenario.scenario_name if sim.worst_case_scenario else None,
                "worst_case_risk_score": sim.worst_case_scenario.simulated.scenario_risk_score if sim.worst_case_scenario else None,
                "monte_carlo": mc_info
            },
            "orchestrator_summary": rep.executive_summary
        }

        ticker_results["horizon_runs"][h] = run_output

        ticker_results["comparative_matrix"].append({
            "horizon": h,
            "forecast_window": fc_h,
            "lookback_bars": lb,
            "latest_close": curr_close,
            "technical_signal": f"{tech.signal} ({int(tech.signal_confidence * 100)}%)",
            "best_forecaster": fc.best_model.model_name if fc.best_model else "N/A",
            "terminal_forecast_change": f"{fc_list[-1]['predicted_change_pct']:+.2f}%" if fc_list else "N/A",
            "risk_score": risk.composite_risk_score,
            "recommendation": risk.recommendation,
            "mc_horizon_days": mc_info["horizon_days"] if mc_info else "N/A",
            "mc_loss_prob": f"{mc_info['probability_loss_pct']:.1f}%" if mc_info else "N/A"
        })

    return ticker_results


async def main():
    workflow = StockShieldWorkflow()
    executed_at = datetime.now(timezone.utc).isoformat()

    print("\n=================================================================")
    print("StockShield 2.0: Starting Multi-Horizon Comparable Evaluation")
    print("=================================================================")

    # 1. Primary Ticker: TCS.NS
    tcs_results = await run_ticker_horizons(workflow, ticker="TCS.NS", provider_mode="auto")

    # 2. Secondary Ticker: INFY.NS
    infy_results = await run_ticker_horizons(workflow, ticker="INFY.NS", provider_mode="auto")

    final_payload = {
        "trial_metadata": {
            "title": "StockShield 2.0 Multi-Horizon Agentic Season Analysis Trial",
            "primary_ticker": "TCS.NS",
            "secondary_ticker": "INFY.NS",
            "executed_at_utc": executed_at,
            "tested_horizons": [h["horizon"] for h in HORIZON_CONFIGS],
            "tested_forecast_windows": [h["forecast_horizon"] for h in HORIZON_CONFIGS],
            "snapshot_comparability": "verified_unified_snapshot_per_ticker"
        },
        "tcs_ns": tcs_results,
        "infy_ns": infy_results,
        # Backwards compatibility top-level keys mapping to TCS.NS
        "horizon_runs": tcs_results["horizon_runs"],
        "comparative_matrix": tcs_results["comparative_matrix"]
    }

    out_dir = PROJECT_ROOT / "evaluation_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "horizon_analysis_trial.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, default=str)

    print("\n=================================================================")
    print("Trial Completed Successfully! Comparable output written to:")
    print(f"  {out_file}")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(main())
