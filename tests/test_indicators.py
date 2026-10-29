"""Unit tests for deterministic technical indicator calculations."""

from stockshield.agents.indicators import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    compute_all_indicators,
)


def test_sma_calculation():
    prices = [10.0, 20.0, 30.0, 40.0, 50.0]
    # SMA 3 of last 3 prices: (30 + 40 + 50) / 3 = 40.0
    sma = calculate_sma(prices, 3)
    assert sma == 40.0

    # Insufficient prices
    assert calculate_sma(prices, 10) is None


def test_ema_calculation():
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    ema = calculate_ema(prices, 3)
    assert ema is not None
    assert isinstance(ema, float)


def test_macd_calculation():
    # Generate 40 synthetic linear prices
    prices = [100.0 + i for i in range(40)]
    macd_line, signal_line, hist = calculate_macd(prices, 12, 26, 9)
    assert macd_line is not None
    assert signal_line is not None
    assert hist is not None
    # For steadily rising series, MACD should be positive
    assert macd_line > 0


def test_rsi_wilder_bounds():
    # Strictly increasing prices -> RSI should approach 100
    up_prices = [100.0 + i * 2.0 for i in range(30)]
    rsi_up = calculate_rsi(up_prices, 14)
    assert rsi_up is not None
    assert rsi_up > 80.0
    assert rsi_up <= 100.0

    # Strictly decreasing prices -> RSI should approach 0
    down_prices = [200.0 - i * 2.0 for i in range(30)]
    rsi_down = calculate_rsi(down_prices, 14)
    assert rsi_down is not None
    assert rsi_down < 20.0
    assert rsi_down >= 0.0


def test_bollinger_bands():
    prices = [100.0] * 20  # Constant price: std_dev is 0
    upper, mid, lower, bw = calculate_bollinger_bands(prices, 20, 2.0)
    assert mid == 100.0
    assert upper == 100.0
    assert lower == 100.0
    assert bw == 0.0


def test_atr_calculation():
    bars = [
        {"high": 105.0, "low": 95.0, "close": 100.0},
        {"high": 110.0, "low": 98.0, "close": 108.0},
        {"high": 112.0, "low": 102.0, "close": 105.0},
    ] * 6  # 18 bars
    atr = calculate_atr(bars, 14)
    assert atr is not None
    assert atr > 0.0


def test_compute_all_indicators_boundary():
    # Test boundary with exactly 200 bars
    bars = [
        {"close": 3500.0 + (i % 20), "high": 3530.0, "low": 3490.0, "adjusted_close": 3500.0 + (i % 20)}
        for i in range(205)
    ]
    indicators, signal, confidence, warnings = compute_all_indicators(bars)

    assert indicators["sma_20"] is not None
    assert indicators["sma_50"] is not None
    assert indicators["sma_200"] is not None
    assert signal in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert 0.0 <= confidence <= 1.0
    assert len(warnings) == 0
