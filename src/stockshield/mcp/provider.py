"""Market data provider adapter supporting deterministic offline fixtures, live Yahoo Finance retrieval, and auto mode."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yfinance as yf
from pydantic import BaseModel, Field


class MarketDataRequest(BaseModel):
    ticker: str
    lookback_days: int = Field(default=200, ge=1, le=500)
    provider_mode: str = "auto"  # auto, fixture, or live


class MarketDataResponse(BaseModel):
    ticker: str
    source: str  # fixture or yahoo_finance
    retrieval_timestamp_utc: str
    data_quality_status: str  # valid, incomplete, stale, unavailable, error
    currency: str = "INR"
    exchange: str = "NSE"
    bar_count: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bars: List[Dict[str, Any]]
    cached: bool = False
    warning: Optional[str] = None


class MarketDataProvider:
    """Provides market data via offline deterministic fixtures, live Yahoo Finance, or hybrid auto mode."""

    def __init__(self, fixtures_dir: Optional[Path] = None, cache_ttl_seconds: int = 1800):
        self.fixtures_dir = fixtures_dir or Path("data/fixtures")
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, Tuple[float, MarketDataResponse]] = {}
        self._fundamentals_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def get_market_data(self, request: MarketDataRequest) -> MarketDataResponse:
        now_iso = datetime.now(timezone.utc).isoformat()
        ticker = request.ticker.strip().upper()
        mode = request.provider_mode.lower()
        lookback = request.lookback_days

        # Check in-memory cache for live/auto requests to prevent duplicate network calls
        cache_key = f"{ticker}:{lookback}:{mode}"
        current_time = time.time()
        if cache_key in self._cache:
            cached_time, cached_resp = self._cache[cache_key]
            if current_time - cached_time < self.cache_ttl_seconds:
                resp_copy = cached_resp.model_copy()
                resp_copy.cached = True
                return resp_copy

        # Mode routing
        if mode == "fixture":
            return self._load_fixture(ticker, lookback, now_iso)
        elif mode == "live":
            resp = self._fetch_yahoo_finance(ticker, lookback, now_iso)
            if resp.data_quality_status in {"valid", "incomplete"}:
                self._cache[cache_key] = (current_time, resp)
            return resp
        elif mode == "auto":
            fixture_path = self.fixtures_dir / f"{ticker}.json"
            if fixture_path.exists():
                return self._load_fixture(ticker, lookback, now_iso)
            else:
                resp = self._fetch_yahoo_finance(ticker, lookback, now_iso)
                if resp.data_quality_status in {"valid", "incomplete"}:
                    self._cache[cache_key] = (current_time, resp)
                return resp
        else:
            return MarketDataResponse(
                ticker=ticker,
                source="error",
                retrieval_timestamp_utc=now_iso,
                data_quality_status="error",
                bar_count=0,
                bars=[],
                cached=False,
                warning=f"Unknown provider mode '{request.provider_mode}'. Supported modes: fixture, live, auto.",
            )

    def _load_fixture(self, ticker: str, lookback_days: int, now_iso: str) -> MarketDataResponse:
        """Load deterministic market data from offline JSON fixture."""
        fixture_path = self.fixtures_dir / f"{ticker}.json"
        if not fixture_path.exists():
            return MarketDataResponse(
                ticker=ticker,
                source="fixture",
                retrieval_timestamp_utc=now_iso,
                data_quality_status="unavailable",
                bar_count=0,
                bars=[],
                cached=False,
                warning=f"No offline fixture found for ticker '{ticker}'. Available fixtures: TCS.NS, INFY.NS, RELIANCE.NS",
            )

        try:
            with open(fixture_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            all_bars = raw_data.get("bars", [])
            selected_bars = all_bars[-lookback_days:] if len(all_bars) >= lookback_days else all_bars

            data_quality = "valid"
            warning = None
            if len(selected_bars) < 200:
                data_quality = "incomplete"
                warning = (
                    f"Data contains only {len(selected_bars)} bars; minimum 200 required for full SMA-200 calculation."
                )

            return MarketDataResponse(
                ticker=ticker,
                source="fixture",
                retrieval_timestamp_utc=now_iso,
                data_quality_status=data_quality,
                currency=raw_data.get("metadata", {}).get("currency", "INR"),
                exchange=raw_data.get("metadata", {}).get("exchange", "NSE"),
                bar_count=len(selected_bars),
                start_date=selected_bars[0]["timestamp"] if selected_bars else None,
                end_date=selected_bars[-1]["timestamp"] if selected_bars else None,
                bars=selected_bars,
                cached=True,
                warning=warning,
            )
        except Exception as e:
            return MarketDataResponse(
                ticker=ticker,
                source="fixture",
                retrieval_timestamp_utc=now_iso,
                data_quality_status="error",
                bar_count=0,
                bars=[],
                cached=False,
                warning=f"Failed to load fixture data: {str(e)}",
            )

    def _fetch_yahoo_finance(self, ticker: str, lookback_days: int, now_iso: str) -> MarketDataResponse:
        """Fetch historical market data dynamically from Yahoo Finance via yfinance."""
        try:
            yf_ticker = yf.Ticker(ticker)
            df = yf_ticker.history(period="2y", auto_adjust=False)

            if df is None or df.empty:
                return MarketDataResponse(
                    ticker=ticker,
                    source="yahoo_finance",
                    retrieval_timestamp_utc=now_iso,
                    data_quality_status="unavailable",
                    bar_count=0,
                    bars=[],
                    cached=False,
                    warning=f"No market data returned by Yahoo Finance for ticker '{ticker}'.",
                )

            df = df.sort_index()
            bars: List[Dict[str, Any]] = []

            for ts, row in df.iterrows():
                try:
                    if hasattr(ts, "strftime"):
                        date_str = ts.strftime("%Y-%m-%d")
                    else:
                        date_str = str(ts)[:10]

                    open_val = float(row.get("Open", 0.0))
                    high_val = float(row.get("High", 0.0))
                    low_val = float(row.get("Low", 0.0))
                    close_val = float(row.get("Close", 0.0))
                    adj_close = float(row.get("Adj Close", close_val))
                    volume_val = int(row.get("Volume", 0))

                    # Discard invalid or non-positive quotes
                    if open_val <= 0 or high_val <= 0 or low_val <= 0 or close_val <= 0:
                        continue

                    # Maintain geometric validity bounds against exchange quirks
                    high_val = max(high_val, open_val, close_val)
                    low_val = min(low_val, open_val, close_val)

                    bars.append(
                        {
                            "timestamp": date_str,
                            "open": round(open_val, 2),
                            "high": round(high_val, 2),
                            "low": round(low_val, 2),
                            "close": round(close_val, 2),
                            "adjusted_close": round(adj_close, 2),
                            "volume": max(0, volume_val),
                        }
                    )
                except (ValueError, TypeError):
                    continue

            if not bars:
                return MarketDataResponse(
                    ticker=ticker,
                    source="yahoo_finance",
                    retrieval_timestamp_utc=now_iso,
                    data_quality_status="unavailable",
                    bar_count=0,
                    bars=[],
                    cached=False,
                    warning=f"All price bars returned for '{ticker}' failed numerical validation.",
                )

            selected_bars = bars[-lookback_days:] if len(bars) >= lookback_days else bars

            data_quality = "valid"
            warning = None
            if len(selected_bars) < 200:
                data_quality = "incomplete"
                warning = f"Data contains only {len(selected_bars)} bars; minimum 200 required for full SMA-200 calculation."

            exchange = "BSE" if ticker.endswith(".BO") else "NSE"

            return MarketDataResponse(
                ticker=ticker,
                source="yahoo_finance",
                retrieval_timestamp_utc=now_iso,
                data_quality_status=data_quality,
                currency="INR",
                exchange=exchange,
                bar_count=len(selected_bars),
                start_date=selected_bars[0]["timestamp"] if selected_bars else None,
                end_date=selected_bars[-1]["timestamp"] if selected_bars else None,
                bars=selected_bars,
                cached=False,
                warning=warning,
            )
        except Exception as e:
            return MarketDataResponse(
                ticker=ticker,
                source="yahoo_finance",
                retrieval_timestamp_utc=now_iso,
                data_quality_status="error",
                bar_count=0,
                bars=[],
                cached=False,
                warning=f"Yahoo Finance live retrieval exception: {str(e)}",
            )

    def get_fundamental_data(self, ticker: str) -> Dict[str, Any]:
        """Extract fundamental financial ratios from Yahoo Finance ticker info with caching."""
        ticker = ticker.strip().upper()
        now = time.time()
        if ticker in self._fundamentals_cache:
            cache_time, data = self._fundamentals_cache[ticker]
            if now - cache_time < self.cache_ttl_seconds:
                return data

        ratios: Dict[str, float] = {}
        missing_metrics: List[str] = []

        try:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info or {}

            # 1. Debt to Equity (Yahoo Finance reports percentage e.g. 27.75 for 27.75%)
            de = info.get("debtToEquity")
            if de is not None and isinstance(de, (int, float)):
                ratios["debt_to_equity"] = round(float(de) / 100.0, 4)
            else:
                missing_metrics.append("debt_to_equity")

            # 2. Current Ratio
            cr = info.get("currentRatio")
            if cr is not None and isinstance(cr, (int, float)):
                ratios["current_ratio"] = round(float(cr), 4)
            else:
                missing_metrics.append("current_ratio")

            # 3. Operating Margin
            om = info.get("operatingMargins")
            if om is not None and isinstance(om, (int, float)):
                ratios["operating_margin"] = round(float(om), 4)
            else:
                missing_metrics.append("operating_margin")

            # 4. Net Margin / Profit Margins
            nm = info.get("profitMargins")
            if nm is not None and isinstance(nm, (int, float)):
                ratios["net_margin"] = round(float(nm), 4)
            else:
                missing_metrics.append("net_margin")

            # 5. Return on Equity (ROE)
            roe = info.get("returnOnEquity")
            if roe is not None and isinstance(roe, (int, float)):
                ratios["roe"] = round(float(roe), 4)
            else:
                missing_metrics.append("roe")

            status = "available" if ratios else "unavailable"
            result = {
                "ticker": ticker,
                "status": status,
                "source": "yahoo_finance" if ratios else "unavailable",
                "ratios": ratios,
                "missing_metrics": missing_metrics,
            }
            self._fundamentals_cache[ticker] = (now, result)
            return result
        except Exception as e:
            return {
                "ticker": ticker,
                "status": "unavailable",
                "source": "unavailable",
                "ratios": {},
                "missing_metrics": ["debt_to_equity", "current_ratio", "operating_margin", "net_margin", "roe"],
                "error": str(e),
            }
