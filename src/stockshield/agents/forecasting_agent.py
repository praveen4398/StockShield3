"""Forecasting Agent for StockShield 2.0.

Consumes verified historical OHLCV data from the Blackboard, coordinates
chronological multi-model evaluation (ARIMA, Exponential Smoothing, LightGBM),
selects the optimal predictive model on validation data, and commits structured
forecasts and uncertainty bounds to the Blackboard.
"""

import time
from typing import Any, Dict

from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus
from stockshield.forecasting.data_preparation import prepare_timeseries_dataframe
from stockshield.forecasting.evaluation import ForecastingEvaluator


class ForecastingAgent:
    """Quantitative agent orchestrating multi-model time-series forecasting."""

    def __init__(self, name: str = "ForecastingAgent", val_sessions: int = 10):
        self.name = name
        self.evaluator = ForecastingEvaluator(validation_window_sessions=val_sessions)

    async def execute(self, blackboard: BlackboardManager) -> Dict[str, Any]:
        """Execute the end-to-end forecasting pipeline lifecycle."""
        start_time = time.perf_counter()

        await blackboard.log_event(
            component=self.name,
            event_type="agent_start",
            status="running",
            details={"models": ["ARIMA", "ExponentialSmoothing", "LightGBM"]},
        )

        state = await blackboard.get_state_snapshot()
        ticker = state.ticker
        market_data = state.market_data

        if market_data.status != FindingStatus.AVAILABLE or not market_data.bars:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = (
                f"Cannot execute ForecastingAgent: market_data status is {market_data.status.value} with "
                f"{len(market_data.bars)} bars."
            )
            await blackboard.update_forecasting(
                producer=self.name,
                latest_observed_close=0.0,
                latest_observed_date=None,
                selected_model_name="NONE",
                selection_reason=err_msg,
                selected_forecasts=[],
                model_results={},
                data_sufficiency_status="unavailable",
                historical_bars_used=0,
                warnings=[err_msg],
                status=FindingStatus.UNAVAILABLE,
                notes=err_msg,
            )
            await blackboard.log_event(
                component=self.name,
                event_type="agent_complete",
                status="unavailable",
                details={"duration_ms": duration_ms, "reason": err_msg},
            )
            return {"status": "unavailable", "duration_ms": duration_ms, "reason": err_msg}

        # Prepare and clean DataFrame
        raw_bars = [b.model_dump() for b in market_data.bars]
        df, prep_warnings = prepare_timeseries_dataframe(raw_bars, min_required_bars=25)

        if df is None:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = "Historical price data is insufficient for statistical forecasting."
            all_warnings = prep_warnings or [err_msg]
            await blackboard.update_forecasting(
                producer=self.name,
                latest_observed_close=0.0,
                latest_observed_date=None,
                selected_model_name="NONE",
                selection_reason=err_msg,
                selected_forecasts=[],
                model_results={},
                data_sufficiency_status="insufficient",
                historical_bars_used=len(raw_bars),
                warnings=all_warnings,
                status=FindingStatus.UNAVAILABLE,
                notes=err_msg,
            )
            await blackboard.log_event(
                component=self.name,
                event_type="agent_complete",
                status="unavailable",
                details={"duration_ms": duration_ms, "reason": err_msg},
            )
            return {"status": "unavailable", "duration_ms": duration_ms, "reason": err_msg}

        latest_close = float(df["target_close"].iloc[-1])
        latest_date = str(df["parsed_date"].iloc[-1].strftime("%Y-%m-%d"))

        is_stale_data = getattr(market_data, "is_stale", False)
        forecast_label = "historical_stale_backtest" if is_stale_data else "current_forward_looking"
        forecast_horizon = getattr(state, "forecast_horizon", "1_month")

        # Run multi-model evaluation and forward forecast
        model_results, best_model_name, selection_reason, selected_pts, eval_warns = (
            self.evaluator.evaluate_and_forecast_all(df, ticker, forecast_horizon=forecast_horizon)
        )
        all_warnings = prep_warnings + eval_warns
        if is_stale_data:
            all_warnings.append(
                f"⚠️ STALE DATA NOTICE: Historical price series ends on {latest_date} (>7 days old). "
                f"Forward dates and projections represent historical backtest benchmarks ({forecast_label}), "
                f"not current forward-looking forecasts."
            )

        status_finding = (
            FindingStatus.AVAILABLE if best_model_name != "NONE" else FindingStatus.FAILED
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        await blackboard.update_forecasting(
            producer=self.name,
            latest_observed_close=latest_close,
            latest_observed_date=latest_date,
            selected_model_name=best_model_name,
            selection_reason=selection_reason,
            selected_forecasts=selected_pts,
            model_results=model_results,
            data_sufficiency_status="valid",
            is_stale_data=is_stale_data,
            forecast_label=forecast_label,
            historical_bars_used=len(df),
            warnings=all_warnings,
            status=status_finding,
            notes=f"Forecasting complete ({forecast_label}). Best: {best_model_name} across {len(selected_pts)} horizons.",
        )

        await blackboard.log_event(
            component=self.name,
            event_type="agent_complete",
            status="completed" if status_finding == FindingStatus.AVAILABLE else "failed",
            details={
                "duration_ms": duration_ms,
                "selected_model": best_model_name,
                "horizons": [p.horizon_trading_days for p in selected_pts],
                "latest_close": latest_close,
            },
        )

        return {
            "status": "completed" if status_finding == FindingStatus.AVAILABLE else "failed",
            "duration_ms": duration_ms,
            "best_model": best_model_name,
            "selected_model": best_model_name,
            "forecast_count": len(selected_pts),
            "forecast_points": len(selected_pts),
            "latest_observed_close": latest_close,
        }
