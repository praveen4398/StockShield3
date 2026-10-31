"""Regression tests for CrewAI execution, Blackboard event logging, and status handling."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from stockshield.api.main import app
from stockshield.blackboard.models import WorkflowStatus
from stockshield.orchestration.workflow import StockShieldWorkflow


@pytest.mark.asyncio
async def test_crewai_kickoff_records_blackboard_event_and_agent_status():
    """Verify that a successful CrewAI kickoff records an execution event and updates agent status."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "TCS.NS",
        "user_prompt": "Verify CrewAI execution event and agent status on Blackboard.",
        "lookback_days": 200,
        "workflow_mode": "sequential",
    }
    state = await workflow.run(raw_request=req, workflow_mode="sequential")

    # Workflow must be completed
    assert state.workflow_status == WorkflowStatus.COMPLETED

    # 1. Check agent status
    assert "crewai_orchestrator" in state.agent_statuses
    assert state.agent_statuses["crewai_orchestrator"] == "completed"

    # 2. Check execution events
    crew_events = [
        e for e in state.execution_events
        if e.get("component") == "crewai_orchestrator" and e.get("event_type") == "crew_kickoff"
    ]
    assert len(crew_events) == 1
    event = crew_events[0]
    assert event["status"] == "completed"
    assert "duration_ms" in event["details"]
    assert event["details"]["duration_ms"] > 0.0

    # Total events: ADK start/complete + Risk start/complete + CrewAI kickoff = 5
    assert len(state.execution_events) == 5


@pytest.mark.asyncio
async def test_crewai_kickoff_failure_honest_handling():
    """Verify that if Crew.kickoff fails, it is honestly marked as failed and never as completed."""
    workflow = StockShieldWorkflow()
    req = {
        "ticker": "INFY.NS",
        "user_prompt": "Test error handling when Crew.kickoff raises an exception.",
        "lookback_days": 200,
        "workflow_mode": "sequential",
    }

    # Simulate kickoff failure
    with patch("crewai.Crew.kickoff", side_effect=RuntimeError("Simulated CrewAI timeout")):
        state = await workflow.run(raw_request=req, workflow_mode="sequential")

    # Check agent status is failed, never completed
    assert "crewai_orchestrator" in state.agent_statuses
    assert state.agent_statuses["crewai_orchestrator"] == "failed"
    assert state.agent_statuses["crewai_orchestrator"] != "completed"

    # Check execution events reflect the failure
    failed_events = [
        e for e in state.execution_events
        if e.get("component") == "crewai_orchestrator" and e.get("event_type") == "crew_kickoff"
    ]
    assert len(failed_events) == 1
    assert failed_events[0]["status"] == "failed"
    assert "Simulated CrewAI timeout" in failed_events[0]["details"]["error"]


def test_api_analyze_returns_crewai_event_and_status():
    """Verify that POST /analyze returns crewai_orchestrator in agent_statuses and execution_events."""
    client = TestClient(app)
    payload = {
        "ticker": "RELIANCE.NS",
        "user_prompt": "Test API serialization of CrewAI execution.",
        "lookback_days": 200,
        "workflow_mode": "sequential",
    }
    res = client.post("/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()

    audit = data["audit_and_provenance"]
    assert "crewai_orchestrator" in audit["agent_statuses"]
    assert audit["agent_statuses"]["crewai_orchestrator"] == "completed"
    assert audit["execution_events_count"] == 5

    crew_events = [
        e for e in audit["execution_events"]
        if e.get("component") == "crewai_orchestrator" and e.get("event_type") == "crew_kickoff"
    ]
    assert len(crew_events) == 1
    assert crew_events[0]["status"] == "completed"
    assert crew_events[0]["details"]["duration_ms"] > 0
