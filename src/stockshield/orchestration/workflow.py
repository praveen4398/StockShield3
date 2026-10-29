"""Workflow Orchestrator supporting Sequential, Parallel, and Hierarchical topologies."""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from crewai import Agent as CrewAgent
from crewai import Crew
from crewai import Task as CrewTask

from stockshield.agents.technical_agent import GoogleADKTechnicalAgent
from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus, StockShieldBlackboard
from stockshield.guardrails.guardrails import GuardrailsEngine
from stockshield.llm.crewai_stub import CrewAIDeterministicStubLLM
from stockshield.llm.stub_llm import DeterministicStubLLM
from stockshield.mcp.client import MCPToolClient
from stockshield.observability.callbacks import ObservabilityCallbackManager
from stockshield.risk.risk_engine import DeterministicRiskEngine


class StockShieldWorkflow:
    """Core workflow engine coordinating agents, tools, and the blackboard."""

    def __init__(
        self,
        callback_manager: Optional[ObservabilityCallbackManager] = None,
        guardrails_engine: Optional[GuardrailsEngine] = None,
    ):
        self.callback_manager = callback_manager or ObservabilityCallbackManager()
        self.guardrails_engine = guardrails_engine or GuardrailsEngine()
        self.mcp_client = MCPToolClient()
        self.technical_agent = GoogleADKTechnicalAgent()
        self.risk_engine = DeterministicRiskEngine()
        self.stub_llm = DeterministicStubLLM()

        # CrewAI Orchestrator with deterministic BaseLLM
        self.crew_llm = CrewAIDeterministicStubLLM(model="deterministic-stub")
        self.crew_orchestrator = CrewAgent(
            role="StockShield Institutional Lead Orchestrator",
            goal="Coordinate multi-agent equity analysis, verify technical momentum, and synthesize risk findings.",
            backstory="Institutional risk management and portfolio intelligence specialist.",
            llm=self.crew_llm,
            verbose=False,
        )

    async def run(
        self,
        raw_request: Dict[str, Any],
        workflow_mode: str = "sequential",
        enable_callbacks: bool = True,
        use_stdio_mcp: bool = False,
    ) -> StockShieldBlackboard:
        """Execute end-to-end stock analysis run with full framework lifecycles."""
        start_time = time.perf_counter()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        trace_id = f"trace_{uuid.uuid4().hex[:16]}"
        self.callback_manager.set_enabled(enable_callbacks)

        # -------------------------------------------------------------
        # 1. Guardrail Input Gate
        # -------------------------------------------------------------
        guard_res, validated_req = self.guardrails_engine.evaluate_request(raw_request)
        self.callback_manager.record_event(
            run_id=run_id,
            trace_id=trace_id,
            component="guardrails_engine",
            event_type="guardrail_trigger",
            status="completed" if guard_res.passed else "blocked",
            metadata={"action": guard_res.action, "security_flag": guard_res.security_flag},
        )

        ticker = guard_res.sanitized_ticker or "UNKNOWN"
        user_prompt = guard_res.sanitized_prompt

        # Initialize Blackboard
        blackboard = BlackboardManager(
            run_id=run_id,
            trace_id=trace_id,
            ticker=ticker,
            user_prompt=user_prompt,
            workflow_mode=workflow_mode,
        )

        if not guard_res.passed:
            await blackboard.fail_run(f"Security/Guardrail Block: {guard_res.reason}")
            return blackboard.state

        lookback_days = validated_req.lookback_days

        self.callback_manager.record_event(
            run_id=run_id,
            trace_id=trace_id,
            component="orchestrator",
            event_type="run_start",
            status="started",
            metadata={"ticker": ticker, "mode": workflow_mode},
        )

        # -------------------------------------------------------------
        # 2. Market Data Retrieval via MCP Tool
        # -------------------------------------------------------------
        transport = "stdio" if use_stdio_mcp else "in_process"
        mcp_mkt_res = await self.mcp_client.call_tool(
            "get_historical_market_data",
            {"ticker": ticker, "lookback_days": lookback_days, "provider_mode": "fixture"},
            transport=transport,
        )
        self.callback_manager.record_event(
            run_id=run_id,
            trace_id=trace_id,
            component="mcp_market_data",
            event_type="tool_call",
            status=mcp_mkt_res["status"],
            duration_ms=mcp_mkt_res["duration_ms"],
            metadata={"transport": mcp_mkt_res.get("transport", transport)},
        )

        if mcp_mkt_res["status"] != "success" or not mcp_mkt_res["result"].get("bars"):
            err_msg = mcp_mkt_res.get("error") or mcp_mkt_res["result"].get("warning", "No market bars returned")
            await blackboard.update_market_data(
                producer="mcp_market_data",
                source="synthetic_fixture",
                bars=[],
                status=FindingStatus.FAILED,
                notes=err_msg,
            )
            await blackboard.fail_run(f"Market data tool failure: {err_msg}")
            return blackboard.state

        mkt_data = mcp_mkt_res["result"]
        await blackboard.update_market_data(
            producer="mcp_market_data",
            source=mkt_data.get("source", "synthetic_fixture"),
            bars=mkt_data.get("bars", []),
            data_quality_status=mkt_data.get("data_quality_status", "SYNTHETIC_GENERATED_FIXTURE"),
            currency=mkt_data.get("currency", "INR"),
            exchange=mkt_data.get("exchange", "NSE"),
            status=FindingStatus.AVAILABLE,
        )

        # -------------------------------------------------------------
        # 3. Execution Topologies (Sequential, Parallel, Hierarchical)
        # -------------------------------------------------------------
        async def run_fundamental_step():
            # Call MCP Financial Calculator
            f_res = await self.mcp_client.call_tool(
                "compute_financial_ratios",
                {
                    "ticker": ticker,
                    "total_debt": 8140.0,
                    "total_equity": 90534.0,
                    "current_assets": 54200.0,
                    "current_liabilities": 25600.0,
                    "operating_income": 59150.0,
                    "revenue": 240893.0,
                    "net_income": 46099.0,
                },
                transport=transport,
            )
            self.callback_manager.record_event(
                run_id=run_id,
                trace_id=trace_id,
                component="mcp_financial_calculator",
                event_type="tool_call",
                status=f_res["status"],
                duration_ms=f_res["duration_ms"],
                metadata={"transport": f_res.get("transport", transport)},
            )
            if f_res["status"] == "success":
                ratios = f_res["result"].get("calculated_ratios", {})
                await blackboard.update_fundamental_findings(
                    producer="mcp_financial_calculator",
                    ratios=ratios,
                    status=FindingStatus.AVAILABLE,
                )

        if workflow_mode == "parallel":
            # Concurrent execution of Google ADK Technical Agent and Fundamental Tool
            await asyncio.gather(
                self.technical_agent.execute(blackboard),
                run_fundamental_step(),
            )
        elif workflow_mode == "hierarchical":
            # Supervisor delegates step 1 (Technical), inspects, then triggers fundamental
            tech_res = await self.technical_agent.execute(blackboard)
            if tech_res.get("status") == "completed":
                await run_fundamental_step()
        else:
            # Sequential (default)
            await self.technical_agent.execute(blackboard)
            await run_fundamental_step()

        # -------------------------------------------------------------
        # 4. Deterministic Risk Review Gate
        # -------------------------------------------------------------
        risk_res = await self.risk_engine.execute(blackboard)
        self.callback_manager.record_event(
            run_id=run_id,
            trace_id=trace_id,
            component="risk_engine",
            event_type="agent_complete",
            status=risk_res["status"],
            duration_ms=risk_res["duration_ms"],
        )

        # -------------------------------------------------------------
        # 5. Genuine CrewAI Kickoff Execution
        # -------------------------------------------------------------
        crew_task = CrewTask(
            description=(
                f"Review institutional risk assessment for equity ticker {ticker} with "
                f"technical signal and risk recommendation."
            ),
            expected_output="Final executive summary: StockShield Risk Assessment verified.",
            agent=self.crew_orchestrator,
        )
        crew = Crew(
            agents=[self.crew_orchestrator],
            tasks=[crew_task],
            verbose=False,
        )
        crew_start = time.perf_counter()
        crew_output = await asyncio.to_thread(crew.kickoff)
        crew_duration_ms = (time.perf_counter() - crew_start) * 1000

        self.callback_manager.record_event(
            run_id=run_id,
            trace_id=trace_id,
            component="crewai_orchestrator",
            event_type="crew_kickoff",
            status="completed",
            duration_ms=crew_duration_ms,
            metadata={"crew_output": str(crew_output)[:100]},
        )

        # -------------------------------------------------------------
        # 6. Final Report Synthesis & Pydantic Completion
        # -------------------------------------------------------------
        current_state = await blackboard.get_state_snapshot()
        exec_sum, md_rep, struct_json, cost_est = self.stub_llm.generate_report(current_state)

        await blackboard.complete_run(
            executive_summary=exec_sum,
            markdown_content=md_rep,
            structured_json=struct_json,
            token_usage={
                "input_tokens": cost_est.estimated_input_tokens,
                "output_tokens": cost_est.estimated_output_tokens,
                "total_tokens": cost_est.total_tokens,
            },
            cost_usd=cost_est.total_cost_usd,
        )

        tot_duration = (time.perf_counter() - start_time) * 1000
        self.callback_manager.record_event(
            run_id=run_id,
            trace_id=trace_id,
            component="orchestrator",
            event_type="run_complete",
            status="completed",
            duration_ms=tot_duration,
            metadata={
                "workflow_mode": workflow_mode,
                "cost_usd": cost_est.total_cost_usd,
                "adk_executed": True,
                "crewai_executed": True,
            },
        )

        return blackboard.state
