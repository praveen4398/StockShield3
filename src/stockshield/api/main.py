"""FastAPI application for StockShield 2.0."""

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from stockshield import __version__
from stockshield.a2a.server import a2a_router
from stockshield.orchestration.workflow import StockShieldWorkflow

app = FastAPI(
    title="StockShield 2.0 — Agentic Stock Analysis & Risk Intelligence API",
    description="Institutional multi-agent stock analysis system built with Google ADK, CrewAI, MCP, and Blackboard Architecture.",
    version=__version__,
)

app.include_router(a2a_router)

# Enable CORS for institutional dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_workflow = StockShieldWorkflow()


class AnalysisRequestPayload(BaseModel):
    ticker: str = Field(
        ...,
        description="Indian NSE equity ticker, e.g., TCS.NS, INFY.NS, RELIANCE.NS, HDFCBANK.NS, WIPRO.NS",
    )
    user_prompt: str = Field(
        default="Conduct institutional technical momentum and deterministic risk intelligence review.",
        description="User analysis directive or query",
    )
    lookback_days: int = Field(default=200, ge=1, le=500, description="Trading days lookback")
    workflow_mode: str = Field(
        default="sequential",
        description="Execution topology: sequential, parallel, or hierarchical",
    )
    risk_profile: str = Field(default="moderate", description="conservative, moderate, aggressive")
    provider_mode: str = Field(
        default="auto",
        description="Market data provider mode: 'auto' (fixture if available, else Yahoo Finance), 'fixture' (offline), or 'live' (Yahoo Finance)",
    )


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp_utc: str
    mcp_tools: list[str]
    allowed_tickers: list[str]
    supported_provider_modes: list[str] = Field(default_factory=lambda: ["auto", "fixture", "live"])
    environment: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness and health readiness probe."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        mcp_tools=["get_historical_market_data", "compute_financial_ratios", "search_financial_document"],
        allowed_tickers=["TCS.NS", "INFY.NS", "RELIANCE.NS"],
        supported_provider_modes=["auto", "fixture", "live"],
        environment="production" if False else "development",
    )


@app.get("/.well-known/agent.json")
async def get_adk_agent_card():
    """A2A protocol AgentCard discovery endpoint for Google ADK Technical Agent."""
    return _workflow.technical_agent.get_agent_card()


@app.post("/analyze")
async def analyze_stock(payload: AnalysisRequestPayload):
    """Execute end-to-end multi-agent stock analysis and risk intelligence pipeline."""
    try:
        blackboard_state = await _workflow.run(
            raw_request=payload.model_dump(),
            workflow_mode=payload.workflow_mode,
        )

        return JSONResponse(
            content={
                "run_id": blackboard_state.run_id,
                "trace_id": blackboard_state.trace_id,
                "workflow_status": blackboard_state.workflow_status.value,
                "ticker": blackboard_state.ticker,
                "market_data": {
                    "status": blackboard_state.market_data.status.value,
                    "source": blackboard_state.market_data.source,
                    "bar_count": blackboard_state.market_data.bar_count,
                    "data_quality": blackboard_state.market_data.data_quality_status,
                },
                "technical_findings": {
                    "status": blackboard_state.technical_findings.status.value,
                    "signal": blackboard_state.technical_findings.signal,
                    "confidence": blackboard_state.technical_findings.signal_confidence,
                    "indicators": blackboard_state.technical_findings.indicators.model_dump(),
                    "summary": blackboard_state.technical_findings.summary,
                },
                "risk_findings": {
                    "status": blackboard_state.risk_findings.status.value,
                    "risk_level": blackboard_state.risk_findings.overall_risk_level,
                    "composite_score": blackboard_state.risk_findings.composite_risk_score,
                    "recommendation": blackboard_state.risk_findings.recommendation,
                    "warnings": blackboard_state.risk_findings.warnings,
                    "reasons": blackboard_state.risk_findings.reasons,
                },
                "final_report": {
                    "executive_summary": blackboard_state.final_report.executive_summary,
                    "markdown_report": blackboard_state.final_report.markdown_content,
                },
                "audit_and_provenance": {
                    "agent_statuses": blackboard_state.agent_statuses,
                    "provenance_records_count": len(blackboard_state.provenance_trail),
                    "execution_events_count": len(blackboard_state.execution_events),
                    "execution_events": blackboard_state.execution_events,
                    "validation_errors": blackboard_state.validation_errors,
                },
                "cost_and_tokens": {
                    "tokens": blackboard_state.token_usage,
                    "estimated_cost_usd": blackboard_state.cost_estimation_usd,
                },
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal pipeline error: {str(e)}")
