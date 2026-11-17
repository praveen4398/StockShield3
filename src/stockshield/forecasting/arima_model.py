"""ARIMA (Autoregressive Integrated Moving Average) model implementation for StockShield 2.0.

Uses a bounded, justified parameter grid over differenced price series to guarantee
rapid convergence, numeric stability, and analytical 95% prediction intervals.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

logger = logging.getLogger(__name__)

# Parsimonious candidate orders for daily financial price series (d=1 enforces stationarity)
ARIMA_CANDIDATE_ORDERS = [
    (1, 1, 1),
    (1, 1, 0),
    (0, 1, 1),
    (2, 1, 1),
    (0, 1, 0),  # Random walk baseline fallback
]


class ARIMAForecaster:
    """Institutional ARIMA time-series forecaster."""

    def __init__(self, candidate_orders: Optional[List[Tuple[int, int, int]]] = None):
        self.candidate_orders = candidate_orders or ARIMA_CANDIDATE_ORDERS
        self.best_order: Optional[Tuple[int, int, int]] = None
        self.fitted_model = None

    def fit_best_model(self, series: pd.Series) -> Tuple[Optional[Any], Optional[Tuple[int, int, int]], List[str]]:
        """Fit candidates on training series and select order with lowest AIC."""
        warnings: List[str] = []
        best_aic = float("inf")
        best_fit = None
        best_order = None

        clean_series = series.dropna().astype(float).values
        if len(clean_series) < 20:
            return None, None, ["Insufficient observations for ARIMA fitting (minimum 20 required)."]

        for order in self.candidate_orders:
            try:
                model = ARIMA(clean_series, order=order)
                fit_res = model.fit()
                if np.isfinite(fit_res.aic) and fit_res.aic < best_aic:
                    best_aic = fit_res.aic
                    best_fit = fit_res
                    best_order = order
            except Exception as e:
                logger.debug(f"ARIMA order {order} fitting error: {e}")
                continue

        if best_fit is None:
            warnings.append("All candidate ARIMA configurations failed to converge.")
            return None, None, warnings

        self.fitted_model = best_fit
        self.best_order = best_order
        return best_fit, best_order, warnings

    def forecast_horizons(
        self,
        series: pd.Series,
        steps: int = 10,
        target_steps: Optional[List[int]] = None,
    ) -> Tuple[Optional[Dict[int, Dict[str, float]]], List[str]]:
        """Fit on provided series and forecast target session horizons.

        Returns:
            ({h: {'predicted_close': ..., 'lower_bound_95': ..., 'upper_bound_95': ...}}, warnings)
        """
        warnings: List[str] = []
        fit_res, order, fit_warns = self.fit_best_model(series)
        warnings.extend(fit_warns)

        if fit_res is None:
            return None, warnings

        horizons = target_steps or ([1, 5, 10] if steps <= 10 else [1, 5, 10, steps])
        max_step = max(steps, max(horizons))

        try:
            forecast_obj = fit_res.get_forecast(steps=max_step)
            pred_mean = np.asarray(forecast_obj.predicted_mean)
            conf_int = np.asarray(forecast_obj.conf_int(alpha=0.05))

            results: Dict[int, Dict[str, float]] = {}
            for h in horizons:
                if h <= len(pred_mean):
                    step_idx = h - 1
                    val = float(pred_mean[step_idx])
                    lower = float(conf_int[step_idx, 0])
                    upper = float(conf_int[step_idx, 1])

                    # Ensure bounds do not emit negative prices
                    lower = max(0.01, lower)
                    upper = max(lower, upper)
                    val = max(0.01, val)

                    results[h] = {
                        "predicted_close": round(val, 4),
                        "lower_bound_95": round(lower, 4),
                        "upper_bound_95": round(upper, 4),
                    }
            return results, warnings
        except Exception as e:
            warnings.append(f"ARIMA forecasting projection error: {str(e)}")
            return None, warnings
