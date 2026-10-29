"""A2A Server implementation for Google ADK Technical Agent."""

from fastapi import APIRouter, HTTPException
from stockshield.a2a.models import A2AAgentCard, A2ATaskRequest, A2ATaskResponse
from stockshield.agents.indicators import compute_all_indicators
from stockshield.agents.technical_agent import GoogleADKTechnicalAgent

a2a_router = APIRouter(prefix="", tags=["A2A Protocol"])
_adk_agent = GoogleADKTechnicalAgent()


@a2a_router.get("/.well-known/agent.json", response_model=A2AAgentCard)
async def discover_agent_card() -> A2AAgentCard:
    """A2A Capability Discovery: Publishes AgentCard."""
    card_data = _adk_agent.get_agent_card()
    return A2AAgentCard(**card_data)


@a2a_router.post("/a2a/tasks", response_model=A2ATaskResponse)
async def handle_a2a_task(request: A2ATaskRequest) -> A2ATaskResponse:
    """Process incoming A2A task from client orchestrators (e.g., CrewAI)."""
    if request.action != "compute_technical_analysis":
        return A2ATaskResponse(
            task_id=request.task_id,
            responder_agent_id=_adk_agent.name,
            status="failed",
            error=f"Unsupported action: '{request.action}'. Supported actions: ['compute_technical_analysis']",
        )

    bars = request.payload.get("bars", [])
    if not bars:
        return A2ATaskResponse(
            task_id=request.task_id,
            responder_agent_id=_adk_agent.name,
            status="failed",
            error="Missing required 'bars' in task payload.",
        )

    try:
        indicators, signal, confidence, warnings = compute_all_indicators(bars)
        return A2ATaskResponse(
            task_id=request.task_id,
            responder_agent_id=_adk_agent.name,
            status="completed",
            findings={
                "indicators": indicators,
                "signal": signal,
                "confidence": confidence,
                "warnings": warnings,
                "bars_analyzed": len(bars),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"A2A execution error: {str(e)}")
