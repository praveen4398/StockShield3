"""Unit and integration tests for genuine A2A protocol communication."""

import httpx
import pytest
from stockshield.a2a.client import CrewAIA2AClient
from stockshield.api.main import app
from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus


@pytest.mark.asyncio
async def test_a2a_agent_card_discovery():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        a2a_client = CrewAIA2AClient(base_url="http://testserver")
        card = await a2a_client.discover_agent(client=client)

        assert card.name == "GoogleADKTechnicalAgent"
        assert "Google ADK" in card.framework
        assert "sma_20_50_200" in card.capabilities
        assert card.endpoints.tasks == "/a2a/tasks"


@pytest.mark.asyncio
async def test_a2a_task_execution_and_blackboard_update():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        a2a_client = CrewAIA2AClient(base_url="http://testserver")

        # Initialize Blackboard with market data
        bb = BlackboardManager("run_a2a_01", "trace_a2a_01", "TCS.NS", "A2A Protocol Test")
        sample_bars = [
            {"timestamp": f"2025-01-{i+1:02d}", "open": 3500.0, "high": 3550.0, "low": 3480.0, "close": 3520.0, "adjusted_close": 3520.0, "volume": 1000000}
            for i in range(25)
        ]
        await bb.update_market_data(
            producer="test_provider",
            source="fixture",
            bars=sample_bars,
            status=FindingStatus.AVAILABLE,
        )

        # Dispatch A2A task from CrewAI client to Google ADK server
        res = await a2a_client.execute_task(blackboard=bb, custom_client=client)

        assert res["status"] == "completed"
        assert res["duration_ms"] >= 0.0

        # Verify Blackboard update
        state = bb.state
        assert state.technical_findings.status == FindingStatus.AVAILABLE
        assert "GoogleADKTechnicalAgent (via A2A)" in state.technical_findings.producer
        assert state.technical_findings.indicators.sma_20 is not None

        # Verify provenance trail
        a2a_prov = [p for p in state.provenance_trail if "via A2A" in p.producer]
        assert len(a2a_prov) == 1
        assert a2a_prov[0].field_name == "technical_findings"


@pytest.mark.asyncio
async def test_a2a_missing_market_data_error_handling():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        a2a_client = CrewAIA2AClient(base_url="http://testserver")
        bb = BlackboardManager("run_a2a_err", "trace_a2a_err", "INFY.NS", "Error prompt")
        # Empty market data
        res = await a2a_client.execute_task(blackboard=bb, custom_client=client)
        assert res["status"] == "failed"
        assert "Market data unavailable" in res["error"]
