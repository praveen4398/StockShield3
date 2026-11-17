"""Monte Carlo Price-Path Simulation Engine for StockShield 2.0.

Provides stochastic forward price trajectory simulations using Geometric Brownian Motion (GBM)
with configurable simulation count, time horizon, and random seed for reproducible research.
"""

import math
from typing import List, Optional

import numpy as np

from stockshield.simulation.models import MonteCarloResult


class MonteCarloSimulator:
    """Stochastic price path simulator using log-normal Geometric Brownian Motion."""

    def __init__(
        self,
        num_simulations: int = 1000,
        horizon_days: int = 20,
        random_seed: Optional[int] = 42,
    ):
        self.num_simulations = num_simulations
        self.horizon_days = horizon_days
        self.random_seed = random_seed

    def simulate(
        self,
        historical_closes: List[float],
        annual_trading_days: int = 252,
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation based on historical log-return drift and volatility.

        Parameters:
            historical_closes: Array of historical closing prices (minimum 10 observations required).
            annual_trading_days: Annualization factor (default 252).

        Returns:
            MonteCarloResult with terminal price quantiles, loss probabilities, and explicit disclosures.
        """
        if len(historical_closes) < 10:
            # Fallback for sparse history
            initial_price = historical_closes[-1] if historical_closes else 100.0
            daily_mu = 0.0002
            daily_sigma = 0.015
        else:
            closes = np.asarray(historical_closes, dtype=float)
            log_returns = np.diff(np.log(closes))
            daily_mu = float(np.mean(log_returns))
            daily_sigma = float(np.std(log_returns))
            initial_price = float(closes[-1])

        # Guard against zero or negative volatility
        daily_sigma = max(0.001, daily_sigma)
        expected_ann_vol = round(daily_sigma * math.sqrt(annual_trading_days) * 100.0, 2)

        # Set reproducible random seed
        if self.random_seed is not None:
            rng = np.random.default_rng(self.random_seed)
        else:
            rng = np.random.default_rng()

        # Simulate Geometric Brownian Motion terminal prices
        # S_T = S_0 * exp( (mu - 0.5 * sigma^2)*T + sigma * sqrt(T) * Z )
        t = self.horizon_days
        drift = (daily_mu - 0.5 * (daily_sigma**2)) * t
        diffusion = daily_sigma * math.sqrt(t)

        z = rng.standard_normal(self.num_simulations)
        terminal_prices = initial_price * np.exp(drift + diffusion * z)

        # Calculate Percentiles
        p5 = float(np.percentile(terminal_prices, 5))
        p25 = float(np.percentile(terminal_prices, 25))
        median_price = float(np.median(terminal_prices))
        mean_price = float(np.mean(terminal_prices))
        p75 = float(np.percentile(terminal_prices, 75))
        p95 = float(np.percentile(terminal_prices, 95))

        # Calculate loss probabilities
        prob_loss = float(np.mean(terminal_prices < initial_price) * 100.0)
        prob_severe_loss = float(np.mean(terminal_prices < (initial_price * 0.90)) * 100.0)

        disclosures = [
            f"Simulation generated {self.num_simulations:,} stochastic paths over {self.horizon_days} trading days.",
            f"Underlying model: Geometric Brownian Motion (GBM) assuming constant daily drift ({daily_mu * 100:+.3f}%) and daily volatility ({daily_sigma * 100:.2f}%).",
            "Assumes continuous log-normal price dispersion without jump processes, liquidity dry-ups, or structural macro regime shifts.",
            "Disclaimer: Monte Carlo outputs represent hypothetical exploratory paths, NOT guaranteed future prices or calibrated loss probabilities.",
        ]

        return MonteCarloResult(
            num_simulations=self.num_simulations,
            horizon_days=self.horizon_days,
            random_seed=self.random_seed,
            initial_price=round(initial_price, 2),
            mean_terminal_price=round(mean_price, 2),
            median_terminal_price=round(median_price, 2),
            percentile_5_price=round(p5, 2),
            percentile_25_price=round(p25, 2),
            percentile_75_price=round(p75, 2),
            percentile_95_price=round(p95, 2),
            probability_loss_pct=round(prob_loss, 2),
            probability_severe_loss_pct=round(prob_severe_loss, 2),
            expected_annualized_volatility=expected_ann_vol,
            assumptions_and_disclosures=disclosures,
        )

