"""Unit tests for MCP Tools (Market Data and Financial Evidence Calculator)."""

import pytest

from stockshield.mcp.client import MCPToolClient
from stockshield.mcp.financial_calculator import (
    FinancialEvidenceCalculator,
    RatioCalculationRequest,
)
from stockshield.mcp.provider import MarketDataProvider, MarketDataRequest


def test_mcp_market_data_provider_fixture():
    provider = MarketDataProvider()
    req = MarketDataRequest(ticker="TCS.NS", lookback_days=200, provider_mode="fixture")
    res = provider.get_market_data(req)

    assert res.ticker == "TCS.NS"
    assert "fixture" in res.source
    assert res.bar_count == 200
    assert "valid" in res.data_quality_status.lower() or "fixture" in res.data_quality_status.lower()
    assert len(res.bars) == 200
    assert res.bars[0]["close"] > 0


def test_mcp_market_data_unavailable_ticker():
    provider = MarketDataProvider()
    req = MarketDataRequest(ticker="UNKNOWN_TICKER.NS", lookback_days=100)
    res = provider.get_market_data(req)
    assert res.data_quality_status == "unavailable"
    assert res.bar_count == 0


def test_mcp_financial_ratio_calculator():
    calc = FinancialEvidenceCalculator()
    req = RatioCalculationRequest(
        ticker="TCS.NS",
        total_debt=8140.0,
        total_equity=90534.0,
        current_assets=54200.0,
        current_liabilities=25600.0,
        operating_income=59150.0,
        revenue=240893.0,
        net_income=46099.0,
    )
    res = calc.calculate_ratios(req)
    assert res.quality_status == "valid"
    # Debt to equity: 8140 / 90534 = ~0.0899
    assert "debt_to_equity" in res.calculated_ratios
    assert round(res.calculated_ratios["debt_to_equity"], 2) == 0.09
    # Current ratio: 54200 / 25600 = ~2.117
    assert "current_ratio" in res.calculated_ratios
    assert round(res.calculated_ratios["current_ratio"], 2) == 2.12


def test_mcp_document_evidence_search():
    calc = FinancialEvidenceCalculator()
    from stockshield.mcp.financial_calculator import DocumentEvidenceRequest

    req = DocumentEvidenceRequest(
        ticker="TCS.NS",
        document_name="TCS_Annual_Report_FY24.txt",
        query="Debt-to-equity",
        max_snippets=2,
    )
    res = calc.extract_bounded_evidence(req)
    assert len(res.snippets) > 0
    assert res.snippets[0]["page_number"] == 2
    assert "Debt-to-equity" in res.snippets[0]["text_snippet"]


@pytest.mark.asyncio
async def test_mcp_client_tool_call():
    client = MCPToolClient()
    res = await client.call_tool(
        "get_historical_market_data",
        {"ticker": "INFY.NS", "lookback_days": 100},
    )
    assert res["status"] == "success"
    assert res["duration_ms"] >= 0.0
    assert res["result"]["bar_count"] == 100


@pytest.mark.asyncio
async def test_mcp_real_stdio_client_session():
    """Verify tool execution through a real subprocess MCP ClientSession over stdio."""
    client = MCPToolClient()
    res = await client.call_tool_stdio(
        "get_historical_market_data",
        {"ticker": "TCS.NS", "lookback_days": 20},
    )
    assert res["status"] == "success"
    assert res["transport"] == "mcp_stdio_session"
    assert res["result"]["ticker"] == "TCS.NS"
    assert res["result"]["bar_count"] == 20
