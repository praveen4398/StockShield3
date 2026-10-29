"""Unit tests for Blackboard architecture, provenance, and concurrent updates."""

import asyncio

import pytest

from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus, WorkflowStatus


@pytest.mark.asyncio
async def test_blackboard_initialization():
    bb = BlackboardManager(
        run_id="run_test_01",
        trace_id="trace_test_01",
        ticker="TCS.NS",
        user_prompt="Analyze TCS for risk.",
    )
    state = bb.state
    assert state.run_id == "run_test_01"
    assert state.ticker == "TCS.NS"
    assert state.workflow_status == WorkflowStatus.RUNNING
    assert state.market_data.status == FindingStatus.PENDING
    assert state.technical_findings.status == FindingStatus.PENDING
    assert state.risk_findings.status == FindingStatus.PENDING


@pytest.mark.asyncio
async def test_blackboard_provenance_tracking():
    bb = BlackboardManager("run_prov", "trace_prov", "INFY.NS", "Prompt")

    # Update market data
    await bb.update_market_data(
        producer="mcp_test_producer",
        source="fixture",
        bars=[
            {
                "timestamp": "2025-01-01",
                "open": 1600,
                "high": 1620,
                "low": 1590,
                "close": 1610,
                "adjusted_close": 1610,
                "volume": 100000,
            }
        ],
        notes="Loaded 1 bar",
    )

    state = bb.state
    assert state.market_data.status == FindingStatus.AVAILABLE
    assert len(state.provenance_trail) == 1
    prov = state.provenance_trail[0]
    assert prov.producer == "mcp_test_producer"
    assert prov.field_name == "market_data"
    assert prov.previous_status == FindingStatus.PENDING
    assert prov.new_status == FindingStatus.AVAILABLE


@pytest.mark.asyncio
async def test_blackboard_concurrent_updates_safety():
    """Verify that multiple coroutines updating different fields in parallel do not corrupt state."""
    bb = BlackboardManager("run_concurrent", "trace_concurrent", "RELIANCE.NS", "Concurrent test")

    async def update_tech():
        for i in range(10):
            await bb.update_technical_findings(
                producer="adk_tech_agent",
                indicators={"sma_20": 2800.0 + i},
                signal="BULLISH",
                signal_confidence=0.75,
                summary=f"Iteration {i}",
                lookback_periods_used=200,
            )
            await asyncio.sleep(0.001)

    async def update_risk():
        for i in range(10):
            await bb.update_risk_findings(
                producer="risk_engine",
                overall_risk_level="LOW",
                composite_risk_score=0.2,
                recommendation="APPROVED",
                checks=[{"name": "check1", "passed": True, "score": 0.1, "message": "OK"}],
            )
            await asyncio.sleep(0.001)

    await asyncio.gather(update_tech(), update_risk())

    state = bb.state
    assert state.technical_findings.status == FindingStatus.AVAILABLE
    assert state.risk_findings.status == FindingStatus.AVAILABLE
    assert len(state.provenance_trail) == 20
