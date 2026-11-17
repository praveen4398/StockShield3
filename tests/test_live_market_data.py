"""Integration and verification test suite for dynamic Indian stock analysis via Yahoo Finance."""

import pytest
from fastapi.testclient import TestClient

from stockshield.api.main import app
from stockshield.blackboard.models import FindingStatus, WorkflowStatus
from stockshield.guardrails.guardrails import GuardrailsEngine
from stockshield.mcp.provider import MarketDataProvider, MarketDataRequest
from stockshield.orchestration.workflow import StockShieldWorkflow


@pytest.fixture
def provider():
    return MarketDataProvider()


@pytest.fixture
def guardrails():
    return GuardrailsEngine()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Provider Modes Verification
# ---------------------------------------------------------------------------
def test_provider_mode_fixture(provider):
    """Fixture mode loads only from local disk fixtures and never accesses the network."""
    req_valid = MarketDataRequest(ticker="TCS.NS", lookback_days=200, provider_mode="fixture")
    res_valid = provider.get_market_data(req_valid)
    assert res_valid.source == "fixture"
    assert res_valid.bar_count == 200
    assert res_valid.data_quality_status == "valid"

    # Non-fixture ticker in fixture mode returns unavailable
    req_missing = MarketDataRequest(ticker="HDFCBANK.NS", lookback_days=200, provider_mode="fixture")
    res_missing = provider.get_market_data(req_missing)
    assert res_missing.source == "fixture"
    assert res_missing.data_quality_status == "unavailable"
    assert res_missing.bar_count == 0


def test_provider_mode_live(provider):
    """Live mode retrieves real-time/historical data from Yahoo Finance."""
    req = MarketDataRequest(ticker="HDFCBANK.NS", lookback_days=150, provider_mode="live")
    res = provider.get_market_data(req)
    assert res.source == "yahoo_finance"
    assert res.bar_count == 150
    assert res.data_quality_status in {"valid", "incomplete"}
    assert res.bars[0]["close"] > 0
    assert res.bars[-1]["high"] >= res.bars[-1]["low"]


def test_provider_mode_auto(provider):
    """Auto mode retrieves fresh live data or falls back to stale fixture if offline."""
    # TCS has local fixture (which is ~1 year old); in auto mode, provider attempts Yahoo Finance for fresh data
    res_tcs = provider.get_market_data(MarketDataRequest(ticker="TCS.NS", lookback_days=100, provider_mode="auto"))
    assert res_tcs.source in {"fixture", "yahoo_finance"}
    assert res_tcs.bar_count == 100
    if res_tcs.source == "fixture":
        assert res_tcs.is_stale is True
        assert res_tcs.data_quality_status == "stale"
    else:
        assert res_tcs.is_stale is False

    # WIPRO does not have local fixture -> retrieves from Yahoo Finance
    res_wipro = provider.get_market_data(MarketDataRequest(ticker="WIPRO.NS", lookback_days=100, provider_mode="auto"))
    assert res_wipro.source == "yahoo_finance"
    assert res_wipro.bar_count == 100


def test_in_memory_cache(provider):
    """Second identical query within TTL must be served from cache."""
    req = MarketDataRequest(ticker="ICICIBANK.NS", lookback_days=60, provider_mode="live")
    res1 = provider.get_market_data(req)
    assert res1.source == "yahoo_finance"
    assert res1.cached is False

    res2 = provider.get_market_data(req)
    assert res2.source == "yahoo_finance"
    assert res2.cached is True
    assert res2.bar_count == res1.bar_count


# ---------------------------------------------------------------------------
# 2. Multi-Stock Live Retrieval Verification (5 NSE Stocks)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ticker", ["HDFCBANK.NS", "WIPRO.NS", "ICICIBANK.NS", "SBIN.NS", "ITC.NS"])
def test_live_retrieval_five_nse_stocks(provider, ticker):
    """Verify market data retrieval and normalization for 5 major NSE equities."""
    req = MarketDataRequest(ticker=ticker, lookback_days=100, provider_mode="live")
    res = provider.get_market_data(req)

    assert res.source == "yahoo_finance"
    assert res.bar_count == 100
    assert len(res.bars) == 100
    assert res.data_quality_status in {"valid", "incomplete"}

    # Validate schema of returned bars
    first_bar = res.bars[0]
    last_bar = res.bars[-1]
    for bar in [first_bar, last_bar]:
        assert "timestamp" in bar
        assert "open" in bar and bar["open"] > 0
        assert "high" in bar and bar["high"] >= bar["low"]
        assert "low" in bar and bar["low"] > 0
        assert "close" in bar and bar["close"] > 0
        assert "volume" in bar and isinstance(bar["volume"], int)


# ---------------------------------------------------------------------------
# 3. Fundamental Metrics Extraction
# ---------------------------------------------------------------------------
def test_fundamental_metrics_wipro(provider):
    """Corporate equity (WIPRO) reports debt-to-equity, margins, and ROE."""
    fund = provider.get_fundamental_data("WIPRO.NS")
    assert fund["status"] == "available"
    assert fund["source"] == "yahoo_finance"
    ratios = fund["ratios"]
    assert "debt_to_equity" in ratios
    assert "operating_margin" in ratios
    assert "net_margin" in ratios
    # D/E should be a decimal ratio (< 1.0 for Wipro), not raw percentage
    assert ratios["debt_to_equity"] < 1.0


def test_fundamental_metrics_hdfc_bank(provider):
    """Banking equity (HDFCBANK) does not report industrial D/E or current ratio; no dummy values."""
    fund = provider.get_fundamental_data("HDFCBANK.NS")
    assert fund["status"] == "available"
    # D/E should be noted as missing, not fabricated
    assert "debt_to_equity" in fund["missing_metrics"]
    assert "current_ratio" in fund["missing_metrics"]
    # Operating margin or ROE should still be captured
    assert "operating_margin" in fund["ratios"] or "roe" in fund["ratios"]


def test_invalid_delisted_ticker_handling(provider):
    """Invalid or non-existent tickers return unavailable without crashing."""
    req = MarketDataRequest(ticker="INVALIDXYZ999.NS", lookback_days=50, provider_mode="live")
    res = provider.get_market_data(req)
    assert res.data_quality_status == "unavailable"
    assert res.bar_count == 0
    assert len(res.bars) == 0


# ---------------------------------------------------------------------------
# 4. Guardrails Dynamic Ticker Validation
# ---------------------------------------------------------------------------
def test_guardrails_permits_dynamic_nse_tickers(guardrails):
    """Valid NSE tickers must pass guardrails when provider_mode is auto or live."""
    for sym in ["HDFCBANK.NS", "WIPRO.NS", "SBIN.NS", "ITC.NS", "MARUTI.NS"]:
        res, req = guardrails.evaluate_request({"ticker": sym, "provider_mode": "auto"})
        assert res.passed is True
        assert res.action == "PASS"
        assert req.ticker == sym

    # Bare ticker symbol normalization: 'HDFCBANK' -> 'HDFCBANK.NS'
    res_bare, req_bare = guardrails.evaluate_request({"ticker": "HDFCBANK", "provider_mode": "auto"})
    assert res_bare.passed is True
    assert req_bare.ticker == "HDFCBANK.NS"


def test_guardrails_strictly_blocks_unsupported_in_fixture_mode(guardrails):
    """Fixture mode strictly enforces the offline 3-stock whitelist."""
    res, req = guardrails.evaluate_request({"ticker": "HDFCBANK.NS", "provider_mode": "fixture"})
    assert res.passed is False
    assert res.action == "BLOCK"
    assert res.security_flag == "UNSUPPORTED_TICKER"


def test_guardrails_blocks_malformed_and_injection_tickers(guardrails):
    """Malformed ticker syntax or injection attempts must be blocked."""
    res, req = guardrails.evaluate_request({"ticker": "HDFC$$$BANK.NS"})
    assert res.passed is False
    assert res.action == "BLOCK"
    assert res.security_flag == "SCHEMA_VIOLATION"


# ---------------------------------------------------------------------------
# 5. End-to-End Workflow Execution on Live Equities
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_live_stock_wipro():
    """End-to-end multi-agent workflow execution on dynamic equity WIPRO.NS."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "WIPRO.NS",
        "user_prompt": "Conduct full dynamic risk analysis for Wipro.",
        "lookback_days": 200,
        "provider_mode": "live",
    }
    state = await workflow.run(raw_request=req, workflow_mode="sequential")

    # 1. State completed
    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.ticker == "WIPRO.NS"

    # 2. Market Data populated from Yahoo Finance
    assert state.market_data.status == FindingStatus.AVAILABLE
    assert state.market_data.source == "yahoo_finance"
    assert state.market_data.bar_count == 200

    # 3. Google ADK Technical Agent executed genuine indicators
    assert state.technical_findings.status == FindingStatus.AVAILABLE
    assert state.technical_findings.indicators.sma_200 is not None
    assert state.technical_findings.indicators.rsi_14 is not None

    # 4. Fundamental Findings populated from Yahoo Finance
    assert state.fundamental_findings.status == FindingStatus.AVAILABLE
    assert "debt_to_equity" in state.fundamental_findings.ratios

    # 5. Risk Review completed
    assert state.risk_findings.status == FindingStatus.AVAILABLE
    assert state.risk_findings.overall_risk_level in {"LOW", "MODERATE", "HIGH", "CRITICAL"}

    # 6. CrewAI kickoff verified in execution events
    crew_events = [e for e in state.execution_events if e.get("component") == "crewai_orchestrator"]
    assert len(crew_events) > 0
    assert crew_events[0]["status"] == "completed"

    # 7. Final Report generated
    assert state.final_report.status == FindingStatus.AVAILABLE
    assert "WIPRO.NS" in state.final_report.markdown_content


@pytest.mark.asyncio
async def test_workflow_live_stock_hdfc_bank():
    """End-to-end multi-agent workflow execution on dynamic banking equity HDFCBANK.NS."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "HDFCBANK.NS",
        "user_prompt": "Analyze HDFC Bank technical momentum and solvency.",
        "lookback_days": 200,
        "provider_mode": "auto",
    }
    state = await workflow.run(raw_request=req, workflow_mode="sequential")

    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.ticker == "HDFCBANK.NS"
    assert state.market_data.source == "yahoo_finance"
    assert state.market_data.bar_count == 200
    assert state.technical_findings.status == FindingStatus.AVAILABLE
    assert state.risk_findings.status == FindingStatus.AVAILABLE


# ---------------------------------------------------------------------------
# 6. API Endpoint Verification with Live Stocks
# ---------------------------------------------------------------------------
def test_api_analyze_live_stock(client):
    """POST /analyze works dynamically for non-fixture stocks."""
    payload = {
        "ticker": "ITC.NS",
        "user_prompt": "Perform institutional risk review on ITC.",
        "lookback_days": 100,
        "workflow_mode": "sequential",
        "provider_mode": "live",
    }
    res = client.post("/analyze", json=payload)
    assert res.status_code == 200
    body = res.json()

    assert body["workflow_status"] == "completed"
    assert body["ticker"] == "ITC.NS"
    assert body["market_data"]["source"] == "yahoo_finance"
    assert body["market_data"]["bar_count"] == 100
    assert body["technical_findings"]["status"] == "available"
    assert body["risk_findings"]["status"] == "available"
    assert "markdown_report" in body["final_report"]

