"""LightGBM gradient boosted decision tree forecaster for StockShield 2.0.

Implements recursive multi-step forecasting with strictly backwards-looking lag and rolling
technical features, avoiding lookahead bias and random shuffle leakage.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from stockshield.forecasting.data_preparation import build_lightgbm_features

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_5",
    "lag_10",
    "return_1d_lag1",
    "return_5d_lag1",
    "rolling_mean_5",
    "rolling_mean_10",
    "rolling_mean_20",
    "rolling_std_5",
    "rolling_std_20",
    "momentum_20",
]


class LightGBMForecaster:
    """Institutional LightGBM time-series regression forecaster."""

    def __init__(self):
        self.model = None
        self.residual_std: float = 0.0
        self.avail_feature_names: List[str] = []

    def fit_model(self, feature_df: pd.DataFrame) -> Tuple[Optional[Any], List[str]]:
        """Fit LGBMRegressor on engineered feature DataFrame."""
        warnings: List[str] = []
        try:
            from lightgbm import LGBMRegressor
        except ImportError:
            return None, ["LightGBM library is not installed or importable."]

        if len(feature_df) < 25:
            return None, ["Insufficient rows for LightGBM training (minimum 25 required after lag buffering)."]

        avail_cols = [c for c in FEATURE_COLS if c in feature_df.columns]
        self.avail_feature_names = avail_cols
        X = feature_df[avail_cols]
        y = feature_df["target_close"]

        try:
            regressor = LGBMRegressor(
                n_estimators=100,
                learning_rate=0.03,
                max_depth=4,
                num_leaves=15,
                min_child_samples=5,
                random_state=42,
                verbosity=-1,
            )
            regressor.fit(X, y)
            preds = regressor.predict(X)
            residuals = y - preds
            self.residual_std = float(np.std(residuals)) if len(residuals) > 0 else 0.0
            self.model = regressor
            return regressor, warnings
        except Exception as e:
            warnings.append(f"LightGBM model fitting failure: {str(e)}")
            return None, warnings

    def forecast_horizons(
        self,
        df: pd.DataFrame,
        steps: int = 10,
        target_steps: Optional[List[int]] = None,
    ) -> Tuple[Optional[Dict[int, Dict[str, float]]], List[str]]:
        """Perform recursive multi-step forecasting for specified horizons or default [1, 5, 10].

        Strategy:
        At each forward step h in [1..max_step], dynamically append the predicted price from step h-1,
        recompute lag and rolling feature vectors using only verified past and previous recursive predictions,
        and predict the subsequent price step.
        """
        warnings: List[str] = []
        feature_df = build_lightgbm_features(df)
        if len(feature_df) < 25:
            return None, ["Insufficient historical bars for LightGBM feature window."]

        model, fit_warns = self.fit_model(feature_df)
        warnings.extend(fit_warns)
        if model is None:
            return None, warnings

        avail_cols = [c for c in FEATURE_COLS if c in feature_df.columns]
        current_prices = list(df["target_close"].astype(float).values)

        horizons = target_steps or ([1, 5, 10] if steps <= 10 else [1, 5, 10, steps])
        max_step = max(steps, max(horizons))

        recursive_preds: List[float] = []

        try:
            for step in range(1, max_step + 1):
                # Construct feature vector for current step from current_prices
                arr = np.array(current_prices)
                p_now = arr[-1]

                lag_1 = p_now
                lag_2 = arr[-2] if len(arr) >= 2 else p_now
                lag_3 = arr[-3] if len(arr) >= 3 else lag_2
                lag_5 = arr[-5] if len(arr) >= 5 else lag_3
                lag_6 = arr[-6] if len(arr) >= 6 else lag_5
                lag_10 = arr[-10] if len(arr) >= 10 else lag_5

                # Consecutive return between latest available price (lag_1) and previous price (lag_2)
                ret_1d = (lag_1 - lag_2) / lag_2 if lag_2 > 0 else 0.0
                ret_5d = (lag_1 - lag_6) / lag_6 if lag_6 > 0 else 0.0

                w5 = arr[-5:]
                w10 = arr[-10:]
                w20 = arr[-20:]

                rm_5 = float(np.mean(w5))
                rm_10 = float(np.mean(w10))
                rm_20 = float(np.mean(w20))

                std_5 = float(np.std(w5))
                std_20 = float(np.std(w20))
                mom_20 = (lag_1 - rm_20) / (rm_20 + 1e-6)

                feat_dict = {
                    "lag_1": lag_1,
                    "lag_2": lag_2,
                    "lag_3": lag_3,
                    "lag_5": lag_5,
                    "lag_10": lag_10,
                    "return_1d_lag1": ret_1d,
                    "return_5d_lag1": ret_5d,
                    "rolling_mean_5": rm_5,
                    "rolling_mean_10": rm_10,
                    "rolling_mean_20": rm_20,
                    "rolling_std_5": std_5,
                    "rolling_std_20": std_20,
                    "momentum_20": mom_20,
                }

                x_step = np.array([[feat_dict[c] for c in avail_cols]])
                pred_val = float(model.predict(x_step)[0])
                pred_val = max(0.01, pred_val)
                recursive_preds.append(pred_val)

                # Append recursive prediction for subsequent horizon features
                current_prices.append(pred_val)

            results: Dict[int, Dict[str, float]] = {}
            for h in horizons:
                if h <= len(recursive_preds):
                    val = recursive_preds[h - 1]
                    se_h = self.residual_std * math.sqrt(h)
                    lower = max(0.01, val - (1.96 * se_h))
                    upper = max(lower, val + (1.96 * se_h))

                    results[h] = {
                        "predicted_close": round(val, 4),
                        "lower_bound_95": round(lower, 4),
                        "upper_bound_95": round(upper, 4),
                    }

            return results, warnings

        except Exception as e:
            warnings.append(f"LightGBM recursive forecasting exception: {str(e)}")
            return None, warnings
