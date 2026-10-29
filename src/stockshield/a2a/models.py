"""Pydantic schemas for the Agent-to-Agent (A2A) Protocol (v1.0)."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class A2AEndpoints(BaseModel):
    card: str = "/.well-known/agent.json"
    tasks: str = "/a2a/tasks"


class A2AAgentCard(BaseModel):
    name: str
    version: str = "2.0.0"
    framework: str  # e.g., 'Google ADK (google-adk 2.13.0)'
    role: str
    capabilities: List[str]
    input_schema: Dict[str, Any]
    output_schema: str
    protocol: str = "A2A/1.0"
    endpoints: A2AEndpoints = Field(default_factory=A2AEndpoints)


class A2ATaskRequest(BaseModel):
    task_id: str
    sender_agent_id: str  # e.g., 'CrewAI_Orchestrator'
    recipient_agent_id: str  # e.g., 'GoogleADK_TechnicalAgent'
    action: str  # e.g., 'compute_technical_analysis'
    payload: Dict[str, Any]
    timeout_seconds: float = 10.0


class A2ATaskResponse(BaseModel):
    task_id: str
    responder_agent_id: str
    status: str  # 'completed', 'failed', 'timeout'
    findings: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    protocol_version: str = "A2A/1.0"
