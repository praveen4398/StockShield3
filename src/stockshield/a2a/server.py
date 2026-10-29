"""A2A Server implementation using official a2a-sdk specifications."""

from a2a.types import AgentCard
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from google.protobuf.json_format import MessageToDict

from stockshield.a2a.models import A2ATaskRequest, A2ATaskResponse
from stockshield.agents.indicators import compute_all_indicators
from stockshield.agents.technical_agent import GoogleADKTechnicalAgent

_adk_agent = GoogleADKTechnicalAgent()


def build_official_agent_card() -> AgentCard:
    """Build spec-compliant Protobuf AgentCard according to A2A Protocol Specification v1.0."""
    card = AgentCard(
        name=_adk_agent.name,
        description="Institutional quantitative technical analysis and momentum scoring agent powered by Google ADK.",
        version="2.0.0",
    )
    card.default_input_modes.append("text")
    card.default_output_modes.append("text")

    # Advertise interface binding
    interface = card.supported_interfaces.add()
    interface.protocol_binding = "JSON_RPC"
    interface.url = "/a2a/tasks"
    interface.protocol_version = "1.0"

    # Declare skills with tags
    skills_data = [
        ("sma_20_50_200", "Simple Moving Averages (20, 50, 200 periods)", ["technical", "trend"]),
        ("rsi_14_wilder", "Relative Strength Index (14 periods, Wilder smoothing)", ["momentum", "oscillator"]),
        ("macd_12_26_9", "Moving Average Convergence Divergence", ["momentum", "trend"]),
        ("bollinger_bands_20_2", "Bollinger Bands (20 periods, 2 std dev)", ["volatility", "bands"]),
        ("atr_14_wilder", "Average True Range (14 periods, Wilder smoothing)", ["volatility", "risk"]),
    ]

    for s_name, s_desc, s_tags in skills_data:
        skill = card.skills.add()
        skill.id = s_name
        skill.name = s_name
        skill.description = s_desc
        for tag in s_tags:
            skill.tags.append(tag)

    return card


# Generate official Protobuf AgentCard
OFFICIAL_AGENT_CARD = build_official_agent_card()

a2a_router = APIRouter(prefix="", tags=["A2A Protocol"])


@a2a_router.get("/.well-known/agent-card.json")
async def get_official_agent_card_json():
    """Official A2A protocol endpoint (RFC/Spec compliant)."""
    return JSONResponse(content=MessageToDict(OFFICIAL_AGENT_CARD))


@a2a_router.get("/.well-known/agent.json")
async def get_legacy_agent_card_json():
    """Backwards-compatible discovery endpoint."""
    return JSONResponse(content=MessageToDict(OFFICIAL_AGENT_CARD))


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
