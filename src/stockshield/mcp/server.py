"""Model Context Protocol (MCP) Server for StockShield 2.0.

Exposes two genuine tools:
1. get_historical_market_data
2. compute_financial_ratios (and search_financial_document)
"""

from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from stockshield.mcp.financial_calculator import (
    DocumentEvidenceRequest,
    FinancialEvidenceCalculator,
    RatioCalculationRequest,
)
from stockshield.mcp.provider import MarketDataProvider, MarketDataRequest

# Initialize FastMCP Server
mcp_server = FastMCP(name="StockShield-MCP-Server")
_provider = MarketDataProvider()
_calculator = FinancialEvidenceCalculator()


@mcp_server.tool()
def get_historical_market_data(
    ticker: str,
    lookback_days: int = 200,
    provider_mode: str = "fixture",
) -> Dict[str, Any]:
    """Retrieve validated historical OHLCV market data for a given ticker."""
    req = MarketDataRequest(
        ticker=ticker,
        lookback_days=lookback_days,
        provider_mode=provider_mode,
    )
    res = _provider.get_market_data(req)
    return res.model_dump()


@mcp_server.tool()
def compute_financial_ratios(
    ticker: str,
    total_debt: Optional[float] = None,
    total_equity: Optional[float] = None,
    current_assets: Optional[float] = None,
    current_liabilities: Optional[float] = None,
    operating_income: Optional[float] = None,
    revenue: Optional[float] = None,
    net_income: Optional[float] = None,
    reporting_period: str = "FY2024",
) -> Dict[str, Any]:
    """Calculate financial ratios from balance sheet and income statement metrics."""
    req = RatioCalculationRequest(
        ticker=ticker,
        total_debt=total_debt,
        total_equity=total_equity,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
        operating_income=operating_income,
        revenue=revenue,
        net_income=net_income,
        reporting_period=reporting_period,
    )
    res = _calculator.calculate_ratios(req)
    return res.model_dump()


@mcp_server.tool()
def search_financial_document(
    ticker: str,
    document_name: str,
    query: str,
    max_snippets: int = 3,
) -> Dict[str, Any]:
    """Extract bounded evidence snippets from verified filing documents with page references."""
    req = DocumentEvidenceRequest(
        ticker=ticker,
        document_name=document_name,
        query=query,
        max_snippets=max_snippets,
    )
    res = _calculator.extract_bounded_evidence(req)
    return res.model_dump()


def run_mcp_standalone():
    """CLI entrypoint to run standalone MCP server over stdio."""
    mcp_server.run()


if __name__ == "__main__":
    run_mcp_standalone()
