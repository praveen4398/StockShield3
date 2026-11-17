"""Data validation, cleaning, and feature engineering for time-series forecasting in StockShield 2.0.

Strictly preserves chronological integrity, eliminates future leakage, and generates
proper business-day trading session horizons.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def prepare_timeseries_dataframe(
    raw_bars: List[Dict[str, Any]],
    min_required_bars: int = 30,
) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """Clean, sort, deduplicate, and validate historical OHLCV price series.

    Returns:
        (df, warnings) where df has columns ['timestamp', 'close', 'open', 'high', 'low', 'volume']
        indexed chronologically. Returns (None, warnings) if data is insufficient or invalid.
    """
    warnings: List[str] = []
    if not raw_bars:
        return None, ["Empty historical bar list provided."]

    # Convert to DataFrame
    df = pd.DataFrame(raw_bars)
    required_cols = {"timestamp", "close"}
    if not required_cols.issubset(df.columns):
        return None, [f"Missing required columns in market data bars: {required_cols - set(df.columns)}"]

    # Select and rename close if adjusted_close is present
    if "adjusted_close" in df.columns:
        # Use adjusted_close if valid, fallback to close
        df["target_close"] = np.where(df["adjusted_close"] > 0, df["adjusted_close"], df["close"])
    else:
        df["target_close"] = df["close"]

    # Validate price values
    df["target_close"] = pd.to_numeric(df["target_close"], errors="coerce")
    invalid_mask = df["target_close"].isna() | (df["target_close"] <= 0)
    if invalid_mask.any():
        num_invalid = int(invalid_mask.sum())
        warnings.append(f"Dropped {num_invalid} non-positive or NaN price observations.")
        df = df[~invalid_mask].copy()

    # Parse and validate dates
    df["parsed_date"] = pd.to_datetime(df["timestamp"], errors="coerce")
    bad_dates = df["parsed_date"].isna()
    if bad_dates.any():
        warnings.append(f"Dropped {int(bad_dates.sum())} bars with unparseable timestamps.")
        df = df[~bad_dates].copy()

    if len(df) == 0:
        return None, ["Zero valid price bars remaining after filtering invalid quotes."]

    # Sort strictly chronologically
    df = df.sort_values("parsed_date").reset_index(drop=True)

    # Deduplicate dates (keep last observation for identical session dates)
    dup_mask = df["parsed_date"].duplicated(keep="last")
    if dup_mask.any():
        num_dups = int(dup_mask.sum())
        warnings.append(f"Removed {num_dups} duplicate timestamp records, keeping latest.")
        df = df[~dup_mask].reset_index(drop=True)

    if len(df) < min_required_bars:
        warnings.append(
            f"Insufficient historical data: {len(df)} bars available (minimum {min_required_bars} required)."
        )
        return None, warnings

    return df, warnings


def build_lightgbm_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer strictly backwards-looking lag and rolling features for LightGBM regression.

    All features use historical information only (lags >= 1) to eliminate lookahead bias / data leakage.
    """
    data = df.copy()
    close_series = data["target_close"]

    # 1. Price lags
    for lag in [1, 2, 3, 5, 10]:
        data[f"lag_{lag}"] = close_series.shift(lag)

    # 2. Daily returns (lagged by 1 to prevent leakage of current session close)
    ret_1d = close_series.pct_change(1)
    data["return_1d_lag1"] = ret_1d.shift(1)
    data["return_5d_lag1"] = close_series.pct_change(5).shift(1)

    # 3. Rolling moving averages on past data (shift 1 then rolling window)
    past_close = close_series.shift(1)
    data["rolling_mean_5"] = past_close.rolling(window=5, min_periods=3).mean()
    data["rolling_mean_10"] = past_close.rolling(window=10, min_periods=5).mean()
    data["rolling_mean_20"] = past_close.rolling(window=20, min_periods=10).mean()

    # 4. Rolling volatility
    data["rolling_std_5"] = past_close.rolling(window=5, min_periods=3).std().fillna(0.0)
    data["rolling_std_20"] = past_close.rolling(window=20, min_periods=10).std().fillna(0.0)

    # 5. Momentum ratio (distance from 20-day mean)
    data["momentum_20"] = (past_close - data["rolling_mean_20"]) / (data["rolling_mean_20"] + 1e-6)

    # 6. Volume features if present
    if "volume" in data.columns:
        past_vol = pd.to_numeric(data["volume"], errors="coerce").fillna(0).shift(1)
        mean_vol_10 = past_vol.rolling(10, min_periods=5).mean()
        data["volume_ratio_10"] = (past_vol / (mean_vol_10 + 1e-6)).fillna(1.0)

    # Drop early rows containing NaNs from longest lag (lag 10)
    clean_data = data.dropna(subset=["lag_10", "rolling_mean_20"]).reset_index(drop=True)
    return clean_data


# Official NSE (National Stock Exchange of India) Trading Holidays (2024 - 2027)
NSE_TRADING_HOLIDAYS = {
    # 2024 Official NSE Holidays
    "2024-01-22",  # Special Holiday (Ayodhya Ram Mandir Pran Pratishtha)
    "2024-01-26",  # Republic Day
    "2024-03-08",  # Mahashivratri
    "2024-03-25",  # Holi
    "2024-03-29",  # Good Friday
    "2024-04-11",  # Id-Ul-Fitr (Ramzan Eid)
    "2024-04-17",  # Shri Ram Navami
    "2024-05-01",  # Maharashtra Day
    "2024-05-20",  # General Parliamentary Elections (Mumbai)
    "2024-06-17",  # Bakri Id / Eid ul-Adha
    "2024-07-17",  # Moharram
    "2024-08-15",  # Independence Day
    "2024-10-02",  # Mahatma Gandhi Jayanti
    "2024-11-01",  # Diwali Laxmi Pujan
    "2024-11-15",  # Gurunanak Jayanti
    "2024-11-20",  # Maharashtra Assembly Election
    "2024-12-25",  # Christmas

    # 2025 Official NSE Holidays
    "2025-02-26",  # Mahashivratri
    "2025-03-14",  # Holi
    "2025-03-31",  # Id-Ul-Fitr
    "2025-04-10",  # Shri Mahavir Jayanti
    "2025-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2025-04-18",  # Good Friday
    "2025-05-01",  # Maharashtra Day
    "2025-06-07",  # Bakri Id
    "2025-08-15",  # Independence Day
    "2025-08-27",  # Ganesh Chaturthi
    "2025-10-02",  # Mahatma Gandhi Jayanti / Dussehra
    "2025-10-21",  # Diwali Laxmi Pujan
    "2025-10-22",  # Diwali Balipratipada
    "2025-11-05",  # Prakash Gurpurb Sri Guru Nanak Dev
    "2025-12-25",  # Christmas

    # 2026 Projected / Official NSE Holidays
    "2026-01-26",  # Republic Day
    "2026-02-16",  # Mahashivratri
    "2026-03-03",  # Holi
    "2026-03-20",  # Id-Ul-Fitr
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-27",  # Bakri Id
    "2026-06-25",  # Muharram
    "2026-08-15",  # Independence Day
    "2026-09-14",  # Ganesh Chaturthi
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-09",  # Diwali Laxmi Pujan
    "2026-11-10",  # Diwali Balipratipada
    "2026-11-24",  # Gurunanak Jayanti
    "2026-12-25",  # Christmas

    # 2027 Key National Holidays
    "2027-01-26",  # Republic Day
    "2027-03-08",  # Mahashivratri
    "2027-03-22",  # Holi
    "2027-03-26",  # Good Friday
    "2027-05-01",  # Maharashtra Day
    "2027-08-15",  # Independence Day
    "2027-10-02",  # Mahatma Gandhi Jayanti
    "2027-10-29",  # Diwali
    "2027-12-25",  # Christmas
}


def is_nse_holiday(date_str: str) -> bool:
    """Check if a date string (YYYY-MM-DD) is an official NSE stock-market trading holiday."""
    return date_str[:10] in NSE_TRADING_HOLIDAYS


def generate_future_trading_dates(
    latest_date_str: str,
    num_sessions: int = 10,
    holidays: Optional[set[str]] = None,
) -> List[str]:
    """Generate calendar dates for future NSE business trading sessions.

    Skips Saturdays, Sundays, and applicable official NSE stock-market trading holidays.
    If calendar data is unavailable for a given future year, falls back to standard
    business weekdays and logs a notice.
    """
    try:
        start_dt = pd.to_datetime(latest_date_str)
    except Exception:
        start_dt = datetime.now()

    trading_holidays = holidays if holidays is not None else NSE_TRADING_HOLIDAYS

    trading_dates: List[str] = []
    current_dt = start_dt + timedelta(days=1)

    while len(trading_dates) < num_sessions:
        # Check weekend: 0=Monday..4=Friday, 5=Saturday, 6=Sunday
        if current_dt.weekday() < 5:
            d_str = current_dt.strftime("%Y-%m-%d")
            # Skip if date is an official NSE trading holiday
            if d_str not in trading_holidays:
                trading_dates.append(d_str)
        current_dt += timedelta(days=1)

    return trading_dates
