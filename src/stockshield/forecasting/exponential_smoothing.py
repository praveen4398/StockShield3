"""Holt-Winters Exponential Smoothing model implementation for StockShield 2.0.

Provides robust adaptive smoothing with damped trend estimation and residual-based
uncertainty confidence intervals.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

logger = logging.getLogger(__name__)


class ExponentialSmoothingForecaster:
    """Institutional Exponential Smoothing time-series forecaster."""

    def __init__(self):
        self.fitted_model: Optional[Any] = None
        self.residual_std: float = 0.0

    def fit_best_model(self, series: pd.Series) -> Tuple[Optional[Any], str, List[str]]:
        """Fit Exponential Smoothing with damped trend, falling back to simple smoothing if necessary."""
        warnings: List[str] = []
        clean_vals = series.dropna().astype(float).values
        if len(clean_vals) < 15:
            return None, "none", ["Insufficient data for Exponential Smoothing (minimum 15 required)."]

        # Strategy 1: Additive Damped Trend
        try:
            model = ExponentialSmoothing(clean_vals, trend="add", damped_trend=True, initialization_method="estimated")
            fit_res = model.fit(optimized=True)
            residuals = clean_vals - fit_res.fittedvalues
            self.residual_std = float(np.std(residuals)) if len(residuals) > 0 else 0.0
            self.fitted_model = fit_res
            return fit_res, "Holt-Winters (Damped Trend)", warnings
        except Exception as e:
            logger.debug(f"Damped trend Exponential Smoothing fitting failed: {e}")

        # Strategy 2: Additive Linear Trend (Undamped)
        try:
            model = ExponentialSmoothing(clean_vals, trend="add", damped_trend=False, initialization_method="estimated")
            fit_res = model.fit(optimized=True)
            residuals = clean_vals - fit_res.fittedvalues
            self.residual_std = float(np.std(residuals)) if len(residuals) > 0 else 0.0
            self.fitted_model = fit_res
            return fit_res, "Holt's Linear Trend", warnings
        except Exception as e:
            logger.debug(f"Linear trend Exponential Smoothing fitting failed: {e}")

        # Strategy 3: Simple Exponential Smoothing fallback
        try:
            model = SimpleExpSmoothing(clean_vals, initialization_method="estimated")
            fit_res = model.fit(optimized=True)
            residuals = clean_vals - fit_res.fittedvalues
            self.residual_std = float(np.std(residuals)) if len(residuals) > 0 else 0.0
            self.fitted_model = fit_res
            warnings.append("Trend models failed to converge; fell back to Simple Exponential Smoothing.")
            return fit_res, "Simple Exponential Smoothing", warnings
        except Exception as e:
            warnings.append(f"All Exponential Smoothing configurations failed: {str(e)}")
            return None, "failed", warnings

    def forecast_horizons(
        self,
        series: pd.Series,
        steps: int = 10,
        target_steps: Optional[List[int]] = None,
    ) -> Tuple[Optional[Dict[int, Dict[str, float]]], List[str]]:
        """Fit on provided series and forecast target session horizons with prediction intervals."""
        warnings: List[str] = []
        fit_res, model_type, fit_warns = self.fit_best_model(series)
        warnings.extend(fit_warns)

        if fit_res is None:
            return None, warnings

        horizons = target_steps or ([1, 5, 10] if steps <= 10 else [1, 5, 10, steps])
        max_step = max(steps, max(horizons))

        try:
            preds = fit_res.forecast(steps=max_step)
            results: Dict[int, Dict[str, float]] = {}

            for h in horizons:
                if h <= len(preds):
                    val = float(preds[h - 1])
                    # Uncertainty scales with sqrt(horizon)
                    se_h = self.residual_std * math.sqrt(h)
                    lower = max(0.01, val - (1.96 * se_h))
                    upper = max(lower, val + (1.96 * se_h))
                    val = max(0.01, val)

                    results[h] = {
                        "predicted_close": round(val, 4),
                        "lower_bound_95": round(lower, 4),
                        "upper_bound_95": round(upper, 4),
                    }
            return results, warnings
        except Exception as e:
            warnings.append(f"Exponential Smoothing forecast error: {str(e)}")
            return None, warnings
