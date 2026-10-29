"""CrewAI A2A Client for inter-agent communication with Google ADK Technical Agent."""

import time
import uuid
from typing import Any, Dict, Optional
import httpx
from stockshield.a2a.models import A2AAgentCard, A2ATaskRequest, A2ATaskResponse
from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus


class CrewAIA2AClient:
    """Inter-agent communication client representing the CrewAI Orchestrator.
    
    Conducts genuine protocol exchanges:
    1. Discovers AgentCard from the Google ADK server.
    2. Validates capability requirements.
    3. Dispatches task request payload.
    4. Validates structured response with Pydantic.
    5. Writes findings to the Blackboard with A2A protocol provenance.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000", client_name: str = "CrewAI_Orchestrator"):
        self.base_url = base_url.rstrip("/")
        self.client_name = client_name

    async def discover_agent(self, client: Optional[httpx.AsyncClient] = None) -> A2AAgentCard:
        """Step 1: Protocol Discovery of AgentCard."""
        url = f"{self.base_url}/.well-known/agent.json"
        if client:
            res = await client.get(url, timeout=5.0)
            res.raise_for_status()
            return A2AAgentCard.model_validate(res.json())

        async with httpx.AsyncClient() as c:
            res = await c.get(url, timeout=5.0)
            res.raise_for_status()
            return A2AAgentCard.model_validate(res.json())

    async def execute_task(
        self,
        blackboard: BlackboardManager,
        custom_client: Optional[httpx.AsyncClient] = None,
        timeout_seconds: float = 10.0,
    ) -> Dict[str, Any]:
        """Execute task over A2A protocol with Pydantic validation and Blackboard update."""
        start_time = time.perf_counter()
        task_id = f"a2a_task_{uuid.uuid4().hex[:10]}"

        # Snapshot market data from Blackboard
        state = await blackboard.get_state_snapshot()
        if state.market_data.status != FindingStatus.AVAILABLE or not state.market_data.bars:
            err = "Cannot dispatch A2A task: Market data unavailable on Blackboard."
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {"status": "failed", "error": err, "duration_ms": duration_ms}

        raw_bars = [b.model_dump() for b in state.market_data.bars]

        # 1. Discover AgentCard
        try:
            agent_card = await self.discover_agent(client=custom_client)
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {"status": "failed", "error": f"A2A AgentCard discovery failed: {str(e)}", "duration_ms": duration_ms}

        # 2. Verify Capabilities
        required_caps = {"sma_20_50_200", "rsi_14_wilder"}
        if not required_caps.issubset(set(agent_card.capabilities)):
            err = f"Agent '{agent_card.name}' lacks required capabilities: {required_caps - set(agent_card.capabilities)}"
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {"status": "failed", "error": err, "duration_ms": duration_ms}

        # 3. Construct Task Request
        task_req = A2ATaskRequest(
            task_id=task_id,
            sender_agent_id=self.client_name,
            recipient_agent_id=agent_card.name,
            action="compute_technical_analysis",
            payload={"ticker": state.ticker, "bars": raw_bars},
            timeout_seconds=timeout_seconds,
        )

        # 4. Transmit Task Request over Protocol
        tasks_url = f"{self.base_url}{agent_card.endpoints.tasks}"
        try:
            if custom_client:
                http_res = await custom_client.post(tasks_url, json=task_req.model_dump(), timeout=timeout_seconds)
            else:
                async with httpx.AsyncClient() as c:
                    http_res = await c.post(tasks_url, json=task_req.model_dump(), timeout=timeout_seconds)

            http_res.raise_for_status()
            task_response = A2ATaskResponse.model_validate(http_res.json())
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {"status": "failed", "error": f"A2A protocol exchange failed: {str(e)}", "duration_ms": duration_ms}

        # 5. Validate Findings and Commit to Blackboard
        if task_response.status != "completed" or not task_response.findings:
            err = task_response.error or "A2A task did not complete successfully"
            await blackboard.update_technical_findings(
                producer=f"{agent_card.name} (via A2A)",
                indicators={},
                signal="NEUTRAL",
                signal_confidence=0.0,
                summary=err,
                lookback_periods_used=0,
                status=FindingStatus.FAILED,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {"status": "failed", "error": err, "duration_ms": duration_ms}

        findings = task_response.findings
        indicators = findings.get("indicators", {})
        signal = findings.get("signal", "NEUTRAL")
        confidence = findings.get("confidence", 0.0)
        warnings = findings.get("warnings", [])

        summary = (
            f"[A2A Protocol Exchange from {self.client_name} -> {agent_card.name}] "
            f"Indicators computed: Signal={signal} ({int(confidence * 100)}% conf). "
            f"Protocol: {task_response.protocol_version}, TaskID: {task_id}."
        )

        await blackboard.update_technical_findings(
            producer=f"{agent_card.name} (via A2A)",
            indicators=indicators,
            signal=signal,
            signal_confidence=confidence,
            summary=summary,
            lookback_periods_used=len(raw_bars),
            warnings=warnings,
            status=FindingStatus.AVAILABLE,
            notes=f"Validated via A2A protocol from {agent_card.name} on {tasks_url}",
        )

        duration_ms = (time.perf_counter() - start_time) * 1000
        return {
            "status": "completed",
            "task_id": task_id,
            "duration_ms": duration_ms,
            "agent_card": agent_card.model_dump(),
            "findings": findings,
        }
