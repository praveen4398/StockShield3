"""Market data provider adapter supporting deterministic offline fixtures and live fallback."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MarketDataRequest(BaseModel):
    ticker: str
    lookback_days: int = Field(default=200, ge=1, le=500)
    provider_mode: str = "fixture"  # fixture or live


class MarketDataResponse(BaseModel):
    ticker: str
    source: str  # fixture or live
    retrieval_timestamp_utc: str
    data_quality_status: str  # valid, incomplete, stale, error
    currency: str = "INR"
    exchange: str = "NSE"
    bar_count: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bars: List[Dict[str, Any]]
    cached: bool = False
    warning: Optional[str] = None


class MarketDataProvider:
    def __init__(self, fixtures_dir: Optional[Path] = None):
        self.fixtures_dir = fixtures_dir or Path("data/fixtures")

    def get_market_data(self, request: MarketDataRequest) -> MarketDataResponse:
        now_iso = datetime.now(timezone.utc).isoformat()
        ticker = request.ticker.strip().upper()

        # Offline fixture mode (default and guaranteed)
        fixture_path = self.fixtures_dir / f"{ticker}.json"
        if not fixture_path.exists():
            # If ticker doesn't have direct fixture, return explicit unavailable
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
            # Slice requested lookback
            selected_bars = all_bars[-request.lookback_days :] if len(all_bars) >= request.lookback_days else all_bars

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
