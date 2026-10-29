"""CrewAI A2A Client implementing genuine A2A Protocol using a2a-sdk."""

import time
import uuid
from typing import Any, Dict, Optional

import httpx
from a2a.client.card_resolver import A2ACardResolver
from a2a.types import AgentCard

from stockshield.a2a.models import A2ATaskRequest, A2ATaskResponse
from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus


class CrewAIA2AClient:
    """Inter-agent communication client representing the CrewAI Orchestrator.

    Conducts genuine protocol exchanges using the official a2a-sdk:
    1. Discovers AgentCard from Google ADK server using A2ACardResolver.
    2. Validates declared skills and interface bindings.
    3. Dispatches task request payload.
    4. Validates structured response with Pydantic.
    5. Writes findings to the Blackboard with A2A protocol provenance.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000", client_name: str = "CrewAI_Orchestrator"):
        self.base_url = base_url.rstrip("/")
        self.client_name = client_name

    async def discover_agent(self, client: Optional[httpx.AsyncClient] = None) -> AgentCard:
        """Step 1: Protocol Discovery of AgentCard using a2a-sdk A2ACardResolver."""
        if client:
            resolver = A2ACardResolver(client, base_url=self.base_url)
            return await resolver.get_agent_card()

        async with httpx.AsyncClient() as c:
            resolver = A2ACardResolver(c, base_url=self.base_url)
            return await resolver.get_agent_card()

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

        # 1. Discover AgentCard via a2a-sdk resolver
        try:
            agent_card = await self.discover_agent(client=custom_client)
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "status": "failed",
                "error": f"A2A AgentCard resolution failed via a2a-sdk: {str(e)}",
                "duration_ms": duration_ms,
            }

        # 2. Verify Skills declared on AgentCard
        declared_skills = {s.name for s in agent_card.skills}
        required_skills = {"sma_20_50_200", "rsi_14_wilder"}
        if not required_skills.issubset(declared_skills):
            err = f"Agent '{agent_card.name}' lacks required skills: {required_skills - declared_skills}"
            duration_ms = (time.perf_counter() - start_time) * 1000
            return {"status": "failed", "error": err, "duration_ms": duration_ms}

        # 3. Determine task endpoint from supported_interfaces
        task_endpoint = "/a2a/tasks"
        if len(agent_card.supported_interfaces) > 0 and agent_card.supported_interfaces[0].url:
            raw_url = agent_card.supported_interfaces[0].url
            task_endpoint = raw_url if raw_url.startswith("/") else f"/{raw_url.lstrip('/')}"

        # 4. Construct Task Request
        task_req = A2ATaskRequest(
            task_id=task_id,
            sender_agent_id=self.client_name,
            recipient_agent_id=agent_card.name,
            action="compute_technical_analysis",
            payload={"ticker": state.ticker, "bars": raw_bars},
            timeout_seconds=timeout_seconds,
        )

        # 5. Transmit Task Request over Protocol
        tasks_url = f"{self.base_url}{task_endpoint}"
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

        # 6. Validate Findings and Commit to Blackboard
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
            f"[A2A Protocol Exchange via a2a-sdk: {self.client_name} -> {agent_card.name}] "
            f"Indicators computed: Signal={signal} ({int(confidence * 100)}% conf). "
            f"TaskID: {task_id}."
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
            "agent_card": {
                "name": agent_card.name,
                "version": agent_card.version,
                "skills": [s.name for s in agent_card.skills],
            },
            "findings": findings,
        }
