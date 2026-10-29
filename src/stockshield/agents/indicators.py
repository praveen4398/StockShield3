"""Deterministic technical indicator calculations for StockShield 2.0.

Formulas implemented:
- SMA: 20, 50, 200 periods
- EMA: 12, 26 periods
- MACD: 12/26 EMA with 9-period signal and histogram
- RSI: 14-period with Wilder's exponential smoothing
- Bollinger Bands: 20-period SMA +/- 2 population standard deviations
- ATR: 14-period True Range with Wilder smoothing

Guarantees:
- Pure deterministic math (no stochastic elements).
- Strict bounds: no NaN or Infinity emitted.
- Explicit None for insufficient lookbacks with diagnostic warnings.
"""

import math
from typing import Any, Dict, List, Optional, Tuple


def calculate_sma(prices: List[float], period: int) -> Optional[float]:
    """Calculate Simple Moving Average over `period` bars."""
    if len(prices) < period:
        return None
    window = prices[-period:]
    return round(sum(window) / period, 4)


def calculate_ema_series(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average series using standard initial SMA seed."""
    if len(prices) < period:
        return []

    multiplier = 2.0 / (period + 1.0)
    # Seed with SMA
    seed_sma = sum(prices[:period]) / period
    ema_values = [seed_sma]

    for p in prices[period:]:
        new_ema = (p - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(new_ema)

    return ema_values


def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """Calculate the latest Exponential Moving Average."""
    series = calculate_ema_series(prices, period)
    return round(series[-1], 4) if series else None


def calculate_macd(
    prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Calculate MACD Line, Signal Line, and Histogram."""
    if len(prices) < (slow + signal):
        return None, None, None

    fast_emas = calculate_ema_series(prices, fast)
    slow_emas = calculate_ema_series(prices, slow)

    # Align series: fast_emas starts at index `fast-1`, slow_emas at `slow-1`
    offset = slow - fast
    aligned_fast = fast_emas[offset:]
    macd_line_series = [f - s for f, s in zip(aligned_fast, slow_emas)]

    if len(macd_line_series) < signal:
        return None, None, None

    signal_line_series = calculate_ema_series(macd_line_series, signal)
    if not signal_line_series:
        return None, None, None

    latest_macd = macd_line_series[-1]
    latest_signal = signal_line_series[-1]
    latest_hist = latest_macd - latest_signal

    return round(latest_macd, 4), round(latest_signal, 4), round(latest_hist, 4)


def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """Calculate Relative Strength Index (RSI) with Wilder's exponential smoothing."""
    if len(prices) < period + 1:
        return None

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    # Initial average gain/loss
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder smoothing for subsequent periods
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 4)


def calculate_bollinger_bands(
    prices: List[float], period: int = 20, num_std: float = 2.0
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Calculate Bollinger Bands (Upper, Middle, Lower, Bandwidth%)."""
    if len(prices) < period:
        return None, None, None, None

    window = prices[-period:]
    mean = sum(window) / period
    variance = sum((x - mean) ** 2 for x in window) / period
    std_dev = math.sqrt(variance)

    upper = mean + (num_std * std_dev)
    lower = mean - (num_std * std_dev)
    bandwidth = ((upper - lower) / mean * 100.0) if mean != 0.0 else 0.0

    return round(upper, 4), round(mean, 4), round(lower, 4), round(bandwidth, 4)


def calculate_atr(bars: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
    """Calculate Average True Range (ATR) with Wilder smoothing."""
    if len(bars) < period + 1:
        return None

    true_ranges = []
    for i in range(1, len(bars)):
        high = bars[i]["high"]
        low = bars[i]["low"]
        prev_close = bars[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    # Initial ATR seed
    atr = sum(true_ranges[:period]) / period
    # Wilder smoothing
    for i in range(period, len(true_ranges)):
        atr = (atr * (period - 1) + true_ranges[i]) / period

    return round(atr, 4)


def compute_all_indicators(bars: List[Dict[str, Any]]) -> Tuple[Dict[str, Optional[float]], str, float, List[str]]:
    """Compute all mandatory technical indicators and derive deterministic signal."""
    warnings: List[str] = []
    if not bars:
        return {}, "NEUTRAL", 0.0, ["Empty price bars provided."]

    closes = [b.get("adjusted_close", b.get("close", 0.0)) for b in bars]
    n_bars = len(closes)

    # 1. SMAs
    sma_20 = calculate_sma(closes, 20)
    sma_50 = calculate_sma(closes, 50)
    sma_200 = calculate_sma(closes, 200)
    if sma_200 is None:
        warnings.append(f"Insufficient history for SMA-200 (have {n_bars} bars, need 200).")

    # 2. EMAs
    ema_12 = calculate_ema(closes, 12)
    ema_26 = calculate_ema(closes, 26)

    # 3. MACD
    macd_line, macd_signal, macd_hist = calculate_macd(closes, 12, 26, 9)

    # 4. RSI
    rsi_14 = calculate_rsi(closes, 14)

    # 5. Bollinger Bands
    bb_upper, bb_mid, bb_lower, bb_bw = calculate_bollinger_bands(closes, 20, 2.0)

    # 6. ATR
    atr_14 = calculate_atr(bars, 14)

    # Deterministic signal generation
    latest_close = closes[-1]
    bullish_signals = 0
    bearish_signals = 0
    total_evals = 0

    # Trend filter: Close vs SMA 50
    if sma_50 is not None:
        total_evals += 1
        if latest_close > sma_50:
            bullish_signals += 1
        else:
            bearish_signals += 1

    # Trend filter: SMA 50 vs SMA 200 (Golden / Death Cross)
    if sma_50 is not None and sma_200 is not None:
        total_evals += 1
        if sma_50 > sma_200:
            bullish_signals += 1
        else:
            bearish_signals += 1

    # Momentum filter: RSI
    if rsi_14 is not None:
        total_evals += 1
        if 40 <= rsi_14 <= 65:
            bullish_signals += 1
        elif rsi_14 < 30:
            bullish_signals += 1  # oversold bounce candidate
        elif rsi_14 > 70:
            bearish_signals += 1  # overbought

    # MACD Histogram momentum
    if macd_hist is not None:
        total_evals += 1
        if macd_hist > 0:
            bullish_signals += 1
        else:
            bearish_signals += 1

    confidence = round(bullish_signals / total_evals, 2) if total_evals > 0 else 0.5
    if bullish_signals > bearish_signals and confidence >= 0.6:
        overall_signal = "BULLISH"
    elif bearish_signals > bullish_signals and (1 - confidence) >= 0.6:
        overall_signal = "BEARISH"
    else:
        overall_signal = "NEUTRAL"

    indicators = {
        "sma_20": sma_20,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "ema_12": ema_12,
        "ema_26": ema_26,
        "macd_line": macd_line,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "rsi_14": rsi_14,
        "bb_upper": bb_upper,
        "bb_middle": bb_mid,
        "bb_lower": bb_lower,
        "bb_bandwidth": bb_bw,
        "atr_14": atr_14,
    }

    return indicators, overall_signal, confidence, warnings
