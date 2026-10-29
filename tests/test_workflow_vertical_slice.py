"""End-to-end integration tests for the vertical slice workflow."""

import pytest

from stockshield.blackboard.models import FindingStatus, WorkflowStatus
from stockshield.orchestration.workflow import StockShieldWorkflow


@pytest.mark.asyncio
async def test_vertical_slice_sequential():
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "TCS.NS",
        "user_prompt": "Conduct standard institutional analysis for TCS.",
        "lookback_days": 200,
    }
    state = await workflow.run(raw_request=req, workflow_mode="sequential")

    # 1. State completed
    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.ticker == "TCS.NS"

    # 2. Market Data populated via MCP
    assert state.market_data.status == FindingStatus.AVAILABLE
    assert state.market_data.source == "fixture"
    assert state.market_data.bar_count == 200

    # 3. Technical Findings populated via Google ADK
    assert state.technical_findings.status == FindingStatus.AVAILABLE
    assert state.technical_findings.indicators.sma_200 is not None
    assert state.technical_findings.signal in {"BULLISH", "BEARISH", "NEUTRAL"}

    # 4. Deterministic Risk Review populated
    assert state.risk_findings.status == FindingStatus.AVAILABLE
    assert state.risk_findings.overall_risk_level in {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert state.risk_findings.recommendation in {"APPROVED", "APPROVED_WITH_CAUTION", "REJECTED_HIGH_RISK"}
    assert len(state.risk_findings.checks) > 0

    # 5. Final Report generated with Pydantic validation
    assert state.final_report.status == FindingStatus.AVAILABLE
    assert "StockShield 2.0 Equity Analysis Report" in state.final_report.markdown_content
    assert state.final_report.structured_json["ticker"] == "TCS.NS"

    # 6. Provenance trail integrity
    assert len(state.provenance_trail) >= 4
    producers = [p.producer for p in state.provenance_trail]
    assert "mcp_market_data" in producers
    assert "GoogleADKTechnicalAgent" in producers
    assert "DeterministicRiskEngine" in producers


@pytest.mark.asyncio
async def test_vertical_slice_parallel():
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "INFY.NS",
        "user_prompt": "Run parallel execution test on INFY.",
        "lookback_days": 200,
    }
    state = await workflow.run(raw_request=req, workflow_mode="parallel")
    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.technical_findings.status == FindingStatus.AVAILABLE
    assert state.fundamental_findings.status == FindingStatus.AVAILABLE


@pytest.mark.asyncio
async def test_vertical_slice_hierarchical():
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "RELIANCE.NS",
        "user_prompt": "Run hierarchical supervisor workflow on Reliance.",
        "lookback_days": 200,
    }
    state = await workflow.run(raw_request=req, workflow_mode="hierarchical")
    assert state.workflow_status == WorkflowStatus.COMPLETED
    assert state.risk_findings.status == FindingStatus.AVAILABLE
