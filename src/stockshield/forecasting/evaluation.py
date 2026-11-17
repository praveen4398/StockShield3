"""Chronological model evaluation, holdout validation, and selection framework for StockShield 2.0.

Evaluates ARIMA, Exponential Smoothing, and LightGBM on strictly out-of-sample chronological holdout validation windows
without lookahead bias, computing MAE, RMSE, and Directional Accuracy.
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from stockshield.forecasting.arima_model import ARIMAForecaster
from stockshield.forecasting.data_preparation import generate_future_trading_dates
from stockshield.forecasting.exponential_smoothing import ExponentialSmoothingForecaster
from stockshield.forecasting.lightgbm_model import LightGBMForecaster
from stockshield.forecasting.models import (
    ForecastModelResult,
    ForecastPoint,
    ModelEvaluationMetrics,
)

FORECAST_HORIZONS: Dict[str, Tuple[int, List[int]]] = {
    "default": (10, [1, 5, 10]),
    "1_month": (21, [1, 5, 10, 21]),
    "3_months": (63, [5, 21, 42, 63]),
    "6_months": (126, [21, 42, 84, 126]),
    "1_year": (252, [21, 63, 126, 252]),
    "2_years": (504, [63, 126, 252, 504]),
}


def calculate_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    baseline_prev: float,
) -> Tuple[float, float, float]:
    """Calculate MAE, RMSE, and Directional Accuracy % against ground-truth validation closes."""
    if len(actual) == 0 or len(predicted) == 0:
        return 0.0, 0.0, 50.0

    k = min(len(actual), len(predicted))
    y = actual[:k]
    y_hat = predicted[:k]

    mae = float(np.mean(np.abs(y - y_hat)))
    rmse = float(math.sqrt(np.mean((y - y_hat) ** 2)))

    # Directional accuracy: check if predicted direction from previous close matches actual direction
    prev_vals = np.concatenate(([baseline_prev], y[:-1]))
    actual_dir = np.sign(y - prev_vals)
    pred_dir = np.sign(y_hat - prev_vals)
    matches = (actual_dir == pred_dir).sum()
    directional_accuracy = float((matches / k) * 100.0)

    return round(mae, 4), round(rmse, 4), round(directional_accuracy, 2)


class ForecastingEvaluator:
    """Evaluates time-series models on chronological splits and selects the best performer."""

    def __init__(self, validation_window_sessions: int = 10):
        self.val_sessions = validation_window_sessions
        self.arima = ARIMAForecaster()
        self.exp_smooth = ExponentialSmoothingForecaster()
        self.lgbm = LightGBMForecaster()

    def evaluate_and_forecast_all(
        self,
        df: pd.DataFrame,
        ticker: str,
        forecast_horizon: Optional[str] = None,
    ) -> Tuple[Dict[str, ForecastModelResult], str, str, List[ForecastPoint], List[str]]:
        """Run chronological validation, select the best model, and produce forward forecasts for target horizons.

        Returns:
            (model_results, selected_model_name, selection_reason, selected_forecasts, warnings)
        """
        warnings: List[str] = []
        n_obs = len(df)
        k_val = min(self.val_sessions, max(5, int(n_obs * 0.15)))

        train_df = df.iloc[:-k_val].copy()
        val_df = df.iloc[-k_val:].copy()

        train_series = train_df["target_close"]
        actual_val = val_df["target_close"].values
        prev_close = float(train_series.iloc[-1])

        if forecast_horizon is None:
            num_sessions, target_steps = FORECAST_HORIZONS["default"]
        else:
            num_sessions, target_steps = FORECAST_HORIZONS.get(forecast_horizon, FORECAST_HORIZONS["1_month"])

        latest_observed_close = float(df["target_close"].iloc[-1])
        latest_date_str = str(df["parsed_date"].iloc[-1].strftime("%Y-%m-%d"))
        future_dates = generate_future_trading_dates(latest_date_str, num_sessions=num_sessions)

        # -------------------------------------------------------------
        # 1. Chronological Validation (Evaluating on out-of-sample val_df)
        # -------------------------------------------------------------
        eval_metrics: Dict[str, ModelEvaluationMetrics] = {}

        # 1A. ARIMA validation
        arima_val_preds, arima_warns = self.arima.forecast_horizons(train_series, steps=k_val)
        warnings.extend(arima_warns)
        if arima_val_preds:
            # Predict step-by-step
            fit_res, _, _ = self.arima.fit_best_model(train_series)
            if fit_res:
                pred_arr = np.asarray(fit_res.get_forecast(steps=k_val).predicted_mean)
                mae, rmse, dir_acc = calculate_metrics(actual_val, pred_arr, prev_close)
                eval_metrics["ARIMA"] = ModelEvaluationMetrics(
                    model_name="ARIMA",
                    mae=mae,
                    rmse=rmse,
                    directional_accuracy_pct=dir_acc,
                    status="success",
                )
            else:
                eval_metrics["ARIMA"] = ModelEvaluationMetrics(
                    model_name="ARIMA", status="failed", error_message="ARIMA fitting failed on validation split"
                )
        else:
            eval_metrics["ARIMA"] = ModelEvaluationMetrics(
                model_name="ARIMA", status="failed", error_message="ARIMA validation failed"
            )

        # 1B. Exponential Smoothing validation
        es_fit, _, _ = self.exp_smooth.fit_best_model(train_series)
        if es_fit:
            es_preds = np.asarray(es_fit.forecast(steps=k_val))
            mae, rmse, dir_acc = calculate_metrics(actual_val, es_preds, prev_close)
            eval_metrics["ExponentialSmoothing"] = ModelEvaluationMetrics(
                model_name="ExponentialSmoothing",
                mae=mae,
                rmse=rmse,
                directional_accuracy_pct=dir_acc,
                status="success",
            )
        else:
            eval_metrics["ExponentialSmoothing"] = ModelEvaluationMetrics(
                model_name="ExponentialSmoothing",
                status="failed",
                error_message="Exponential Smoothing fitting failed on validation split",
            )

        # 1C. LightGBM validation
        lgbm_preds_dict, lgbm_warns = self.lgbm.forecast_horizons(train_df, steps=k_val)
        warnings.extend(lgbm_warns)
        if lgbm_preds_dict:
            # Multi-step validation prediction
            # Collect point predictions across k_val steps
            pred_list: List[float] = []
            curr_prices = list(train_df["target_close"].astype(float).values)
            avail_cols = self.lgbm.avail_feature_names if self.lgbm.model else []
            if self.lgbm.model and avail_cols:
                for _ in range(k_val):
                    arr = np.array(curr_prices)
                    lag_1 = arr[-1]
                    lag_2 = arr[-2] if len(arr) >= 2 else lag_1
                    lag_3 = arr[-3] if len(arr) >= 3 else lag_2
                    lag_5 = arr[-5] if len(arr) >= 5 else lag_3
                    lag_6 = arr[-6] if len(arr) >= 6 else lag_5
                    lag_10 = arr[-10] if len(arr) >= 10 else lag_5
                    rm_20 = float(np.mean(arr[-20:]))

                    feat_dict = {
                        "lag_1": lag_1,
                        "lag_2": lag_2,
                        "lag_3": lag_3,
                        "lag_5": lag_5,
                        "lag_10": lag_10,
                        "return_1d_lag1": (lag_1 - lag_2) / lag_2 if lag_2 > 0 else 0.0,
                        "return_5d_lag1": (lag_1 - lag_6) / lag_6 if lag_6 > 0 else 0.0,
                        "rolling_mean_5": float(np.mean(arr[-5:])),
                        "rolling_mean_10": float(np.mean(arr[-10:])),
                        "rolling_mean_20": rm_20,
                        "rolling_std_5": float(np.std(arr[-5:])),
                        "rolling_std_20": float(np.std(arr[-20:])),
                        "momentum_20": (lag_1 - rm_20) / (rm_20 + 1e-6),
                    }
                    x_step = np.array([[feat_dict[c] for c in avail_cols]])
                    p_next = float(self.lgbm.model.predict(x_step)[0])
                    pred_list.append(p_next)
                    curr_prices.append(p_next)

                mae, rmse, dir_acc = calculate_metrics(actual_val, np.array(pred_list), prev_close)
                eval_metrics["LightGBM"] = ModelEvaluationMetrics(
                    model_name="LightGBM",
                    mae=mae,
                    rmse=rmse,
                    directional_accuracy_pct=dir_acc,
                    status="success",
                )
            else:
                eval_metrics["LightGBM"] = ModelEvaluationMetrics(
                    model_name="LightGBM", status="failed", error_message="LightGBM model not trained"
                )
        else:
            eval_metrics["LightGBM"] = ModelEvaluationMetrics(
                model_name="LightGBM", status="failed", error_message="LightGBM validation failed"
            )

        # -------------------------------------------------------------
        # 2. Forward Projections on Full Dataset for Target Steps
        # -------------------------------------------------------------
        model_results: Dict[str, ForecastModelResult] = {}
        all_series = df["target_close"]

        # 2A. ARIMA Forward Forecast
        arima_forward, a_w = self.arima.forecast_horizons(all_series, steps=num_sessions, target_steps=target_steps)
        warnings.extend(a_w)
        arima_pts: List[ForecastPoint] = []
        if arima_forward:
            for h in target_steps:
                if h in arima_forward and len(future_dates) >= h:
                    p = arima_forward[h]
                    chg = ((p["predicted_close"] - latest_observed_close) / latest_observed_close) * 100.0
                    arima_pts.append(
                        ForecastPoint(
                            horizon_trading_days=h,
                            forecast_date=future_dates[h - 1],
                            predicted_close=p["predicted_close"],
                            predicted_change_pct=round(chg, 2),
                            lower_bound_95=p.get("lower_bound_95"),
                            upper_bound_95=p.get("upper_bound_95"),
                            model_name="ARIMA",
                        )
                    )
        model_results["ARIMA"] = ForecastModelResult(
            model_name="ARIMA",
            forecast_points=arima_pts,
            metrics=eval_metrics.get("ARIMA", ModelEvaluationMetrics(model_name="ARIMA", status="failed")),
        )

        # 2B. Exponential Smoothing Forward Forecast
        es_forward, es_w = self.exp_smooth.forecast_horizons(all_series, steps=num_sessions, target_steps=target_steps)
        warnings.extend(es_w)
        es_pts: List[ForecastPoint] = []
        if es_forward:
            for h in target_steps:
                if h in es_forward and len(future_dates) >= h:
                    p = es_forward[h]
                    chg = ((p["predicted_close"] - latest_observed_close) / latest_observed_close) * 100.0
                    es_pts.append(
                        ForecastPoint(
                            horizon_trading_days=h,
                            forecast_date=future_dates[h - 1],
                            predicted_close=p["predicted_close"],
                            predicted_change_pct=round(chg, 2),
                            lower_bound_95=p.get("lower_bound_95"),
                            upper_bound_95=p.get("upper_bound_95"),
                            model_name="ExponentialSmoothing",
                        )
                    )
        model_results["ExponentialSmoothing"] = ForecastModelResult(
            model_name="ExponentialSmoothing",
            forecast_points=es_pts,
            metrics=eval_metrics.get(
                "ExponentialSmoothing", ModelEvaluationMetrics(model_name="ExponentialSmoothing", status="failed")
            ),
        )

        # 2C. LightGBM Forward Forecast
        lgbm_forward, l_w = self.lgbm.forecast_horizons(df, steps=num_sessions, target_steps=target_steps)
        warnings.extend(l_w)
        lgbm_pts: List[ForecastPoint] = []
        if lgbm_forward:
            for h in target_steps:
                if h in lgbm_forward and len(future_dates) >= h:
                    p = lgbm_forward[h]
                    chg = ((p["predicted_close"] - latest_observed_close) / latest_observed_close) * 100.0
                    lgbm_pts.append(
                        ForecastPoint(
                            horizon_trading_days=h,
                            forecast_date=future_dates[h - 1],
                            predicted_close=p["predicted_close"],
                            predicted_change_pct=round(chg, 2),
                            lower_bound_95=p.get("lower_bound_95"),
                            upper_bound_95=p.get("upper_bound_95"),
                            model_name="LightGBM",
                        )
                    )
        model_results["LightGBM"] = ForecastModelResult(
            model_name="LightGBM",
            forecast_points=lgbm_pts,
            metrics=eval_metrics.get("LightGBM", ModelEvaluationMetrics(model_name="LightGBM", status="failed")),
        )

        # -------------------------------------------------------------
        # 3. Model Selection based on Chronological Validation RMSE
        # -------------------------------------------------------------
        candidates = [m for m in model_results.values() if m.metrics.status == "success" and len(m.forecast_points) > 0]
        if not candidates:
            return model_results, "NONE", "All forecasting models failed during fitting or evaluation.", [], warnings

        # Pick candidate with lowest validation RMSE
        best_candidate = min(candidates, key=lambda c: c.metrics.rmse)
        selected_name = best_candidate.model_name
        selected_points = best_candidate.forecast_points

        other_scores = ", ".join(f"{m.model_name} (RMSE {m.metrics.rmse:.2f})" for m in candidates)
        selection_reason = (
            f"Selected {selected_name} based on superior out-of-sample validation RMSE "
            f"({best_candidate.metrics.rmse:.2f}, DirAcc {best_candidate.metrics.directional_accuracy_pct:.1f}%). "
            f"Comparison: {other_scores}."
        )

        return model_results, selected_name, selection_reason, selected_points, warnings
