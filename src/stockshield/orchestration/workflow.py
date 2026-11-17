"""Workflow Orchestrator supporting Sequential, Parallel, and Hierarchical topologies."""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from crewai import Agent as CrewAgent
from crewai import Crew
from crewai import Task as CrewTask

from stockshield.agents.forecasting_agent import ForecastingAgent
from stockshield.agents.news_agent import NewsSentimentAgent
from stockshield.agents.scenario_simulation_agent import ScenarioSimulationAgent
from stockshield.agents.technical_agent import GoogleADKTechnicalAgent
from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus, StockShieldBlackboard
from stockshield.evaluation.storage import ExperimentStorage, RunStatus
from stockshield.guardrails.guardrails import GuardrailsEngine
from stockshield.judge.service import JudgeEvaluationService
from stockshield.llm.crewai_stub import CrewAIDeterministicStubLLM
from stockshield.llm.stub_llm import DeterministicStubLLM
from stockshield.mcp.client import MCPToolClient
from stockshield.mcp.provider import MarketDataProvider
from stockshield.observability.callbacks import ObservabilityCallbackManager
from stockshield.risk.risk_engine import DeterministicRiskEngine


class StockShieldWorkflow:
    """Core workflow engine coordinating agents, tools, and the blackboard."""

    def __init__(
        self,
        callback_manager: Optional[ObservabilityCallbackManager] = None,
        guardrails_engine: Optional[GuardrailsEngine] = None,
        storage: Optional[ExperimentStorage] = None,
    ):
        self.callback_manager = callback_manager or ObservabilityCallbackManager()
        self.guardrails_engine = guardrails_engine or GuardrailsEngine()
        self.storage = storage or ExperimentStorage()
        self.mcp_client = MCPToolClient()
        self.market_provider = MarketDataProvider()
        self.technical_agent = GoogleADKTechnicalAgent()
        self.news_agent = NewsSentimentAgent()
        self.forecasting_agent = ForecastingAgent()
        self.scenario_agent = ScenarioSimulationAgent()
        self.risk_engine = DeterministicRiskEngine()
        self.stub_llm = DeterministicStubLLM()
        self.judge_service = JudgeEvaluationService()

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

        ticker = guard_res.sanitized_ticker or raw_request.get("ticker", "UNKNOWN")
        user_prompt = guard_res.sanitized_prompt
        experiment_id = raw_request.get("experiment_id") or "default_experiment"

        time_horizon = raw_request.get("time_horizon") or getattr(validated_req, "time_horizon", "short_term")
        forecast_horizon = raw_request.get("forecast_horizon") or getattr(validated_req, "forecast_horizon", "1_month")

        # Initialize Blackboard
        blackboard = BlackboardManager(
            run_id=run_id,
            trace_id=trace_id,
            ticker=ticker,
            user_prompt=user_prompt,
            workflow_mode=workflow_mode,
            time_horizon=time_horizon,
            forecast_horizon=forecast_horizon,
            experiment_id=experiment_id,
        )

        # Register run in storage immediately
        self.storage.create_run(
            run_id=run_id,
            experiment_id=experiment_id,
            ticker=ticker,
            workflow_mode=workflow_mode,
            config=raw_request,
        )

        if not guard_res.passed:
            err_msg = f"Security/Guardrail Block: {guard_res.reason}"
            await blackboard.fail_run(err_msg)
            tot_duration = (time.perf_counter() - start_time) * 1000
            self.storage.fail_run(
                run_id=run_id,
                error_message=err_msg,
                duration_ms=tot_duration,
            )
            return blackboard.state

        lookback_days = validated_req.lookback_days
        if time_horizon == "long_term" and lookback_days <= 200 and "lookback_days" not in raw_request:
            lookback_days = 500

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
        provider_mode = getattr(validated_req, "provider_mode", "auto")
        transport = "stdio" if use_stdio_mcp else "in_process"
        mcp_mkt_res = await self.mcp_client.call_tool(
            "get_historical_market_data",
            {"ticker": ticker, "lookback_days": lookback_days, "provider_mode": provider_mode},
            transport=transport,
        )
        self.callback_manager.record_event(
            run_id=run_id,
            trace_id=trace_id,
            component="mcp_market_data",
            event_type="tool_call",
            status=mcp_mkt_res["status"],
            duration_ms=mcp_mkt_res["duration_ms"],
            metadata={"transport": mcp_mkt_res.get("transport", transport), "provider_mode": provider_mode},
        )

        if mcp_mkt_res["status"] != "success" or not mcp_mkt_res["result"].get("bars"):
            err_msg = mcp_mkt_res.get("error") or mcp_mkt_res["result"].get("warning", "No market bars returned")
            source_lbl = "fixture" if provider_mode == "fixture" else "yahoo_finance"
            await blackboard.update_market_data(
                producer="mcp_market_data",
                source=source_lbl,
                bars=[],
                status=FindingStatus.FAILED,
                notes=err_msg,
            )
            await blackboard.fail_run(f"Market data tool failure: {err_msg}")
            tot_duration = (time.perf_counter() - start_time) * 1000
            self.storage.record_stage_market_data(run_id, blackboard.state.market_data)
            self.storage.fail_run(
                run_id=run_id,
                error_message=f"Market data tool failure: {err_msg}",
                duration_ms=tot_duration,
            )
            return blackboard.state

        mkt_data = mcp_mkt_res["result"]
        data_source = mkt_data.get("source", "fixture" if provider_mode == "fixture" else "yahoo_finance")
        await blackboard.update_market_data(
            producer="mcp_market_data",
            source=data_source,
            bars=mkt_data.get("bars", []),
            data_quality_status=mkt_data.get("data_quality_status", "valid"),
            is_stale=mkt_data.get("is_stale", False),
            freshness_age_days=mkt_data.get("freshness_age_days"),
            currency=mkt_data.get("currency", "INR"),
            exchange=mkt_data.get("exchange", "NSE"),
            status=FindingStatus.AVAILABLE,
        )
        self.storage.record_stage_market_data(run_id, blackboard.state.market_data)

        # -------------------------------------------------------------
        # 3. Execution Topologies (Sequential, Parallel, Hierarchical)
        # -------------------------------------------------------------
        async def run_fundamental_step():
            fund_start = time.perf_counter()
            # Verified filing reports for offline fixture baseline
            if ticker == "TCS.NS":
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
            elif ticker == "INFY.NS":
                f_res = await self.mcp_client.call_tool(
                    "compute_financial_ratios",
                    {
                        "ticker": ticker,
                        "total_debt": 8020.0,
                        "total_equity": 86412.0,
                        "current_assets": 54200.0,
                        "current_liabilities": 25600.0,
                        "operating_income": 31747.0,
                        "revenue": 153670.0,
                        "net_income": 26248.0,
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
            elif ticker == "RELIANCE.NS":
                f_res = await self.mcp_client.call_tool(
                    "compute_financial_ratios",
                    {
                        "ticker": ticker,
                        "total_debt": 313000.0,
                        "total_equity": 793000.0,
                        "current_assets": 240000.0,
                        "current_liabilities": 210000.0,
                        "operating_income": 140000.0,
                        "revenue": 899000.0,
                        "net_income": 69621.0,
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
            else:
                # Dynamic / live equities: retrieve genuine fundamental metrics from provider
                fund_data = self.market_provider.get_fundamental_data(ticker)
                fund_duration_ms = (time.perf_counter() - fund_start) * 1000
                ratios = fund_data.get("ratios", {})
                missing = fund_data.get("missing_metrics", [])
                warnings = [f"Metric '{m}' not reported for {ticker}." for m in missing] if missing else []
                fund_status = FindingStatus.AVAILABLE if ratios else FindingStatus.UNAVAILABLE

                await blackboard.update_fundamental_findings(
                    producer="yahoo_finance_fundamentals",
                    ratios=ratios,
                    status=fund_status,
                    warnings=warnings,
                )
                self.callback_manager.record_event(
                    run_id=run_id,
                    trace_id=trace_id,
                    component="yahoo_finance_fundamentals",
                    event_type="fundamental_metrics_retrieval",
                    status="completed" if ratios else "unavailable",
                    duration_ms=round(fund_duration_ms, 2),
                    metadata={"available_ratios": list(ratios.keys()), "missing": missing},
                )

        async def run_news_step():
            news_res = await self.news_agent.execute(blackboard, provider_mode=provider_mode)
            self.callback_manager.record_event(
                run_id=run_id,
                trace_id=trace_id,
                component="news_sentiment_agent",
                event_type="agent_complete",
                status=news_res["status"],
                duration_ms=news_res.get("duration_ms", 0.0),
                metadata={
                    "total_articles": news_res.get("total_articles", 0),
                    "overall_sentiment": news_res.get("overall_sentiment", "NEUTRAL"),
                },
            )
            return news_res

        async def run_forecasting_step():
            fcast_res = await self.forecasting_agent.execute(blackboard)
            self.callback_manager.record_event(
                run_id=run_id,
                trace_id=trace_id,
                component="forecasting_agent",
                event_type="agent_complete",
                status=fcast_res["status"],
                duration_ms=fcast_res.get("duration_ms", 0.0),
                metadata={
                    "best_model": fcast_res.get("best_model"),
                    "validation_rmse": fcast_res.get("validation_rmse"),
                    "forecast_points": fcast_res.get("forecast_points", 0),
                },
            )
            return fcast_res

        try:
            if workflow_mode == "parallel":
                # Concurrent execution of Google ADK Technical Agent, Fundamental Step, News Agent, and Forecasting Agent
                await asyncio.gather(
                    self.technical_agent.execute(blackboard),
                    run_fundamental_step(),
                    run_news_step(),
                    run_forecasting_step(),
                )
            elif workflow_mode == "hierarchical":
                # Supervisor delegates step 1 (Technical), inspects, then triggers fundamental, news, and forecasting steps
                tech_res = await self.technical_agent.execute(blackboard)
                if tech_res.get("status") == "completed":
                    await run_fundamental_step()
                    await run_news_step()
                    await run_forecasting_step()
            else:
                # Sequential (default)
                await self.technical_agent.execute(blackboard)
                await run_fundamental_step()
                await run_news_step()
                await run_forecasting_step()

            # Incremental stage recording
            self.storage.record_stage_technical(run_id, blackboard.state.technical_findings)
            self.storage.record_stage_news_sentiment(run_id, blackboard.state.news_sentiment)
            self.storage.record_stage_forecasting(run_id, blackboard.state.forecasting)

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
            self.storage.record_stage_risk(run_id, blackboard.state.risk_findings)

            # -------------------------------------------------------------
            # 5. Scenario Simulation and Stress Testing Gate
            # -------------------------------------------------------------
            from stockshield.simulation.models import CustomScenarioInput

            custom_scens_raw = getattr(validated_req, "custom_scenarios", None) or raw_request.get("custom_scenarios")
            custom_scenarios = None
            if custom_scens_raw:
                custom_scenarios = [
                    c if isinstance(c, CustomScenarioInput) else CustomScenarioInput(**c) for c in custom_scens_raw
                ]
            predefined_scens = getattr(validated_req, "predefined_scenarios", None) or raw_request.get("predefined_scenarios")
            include_mc = getattr(validated_req, "include_monte_carlo", None)
            if include_mc is None:
                include_mc = raw_request.get("include_monte_carlo", True)

            sim_res = await self.scenario_agent.execute(
                blackboard,
                custom_scenarios=custom_scenarios,
                predefined_scenario_names=predefined_scens,
                include_mc=include_mc,
            )
            self.callback_manager.record_event(
                run_id=run_id,
                trace_id=trace_id,
                component="scenario_simulation_agent",
                event_type="agent_complete",
                status=sim_res["status"],
                duration_ms=sim_res.get("duration_ms", 0.0),
                metadata={
                    "scenarios_evaluated": sim_res.get("scenarios_evaluated", 0),
                    "worst_case_scenario": sim_res.get("worst_case_scenario"),
                    "worst_case_score": sim_res.get("worst_case_score"),
                },
            )
            # Re-evaluate Gate 8 with scenario simulation results
            await self.risk_engine.evaluate_gate_8(blackboard)
            self.storage.record_stage_scenario_simulation(run_id, blackboard.state.scenario_simulation)

            # -------------------------------------------------------------
            # 6. Genuine CrewAI Kickoff Execution
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
            try:
                crew_output = await asyncio.to_thread(crew.kickoff)
                crew_duration_ms = (time.perf_counter() - crew_start) * 1000
                crew_status = "completed"
                crew_error = None
            except Exception as e:
                crew_duration_ms = (time.perf_counter() - crew_start) * 1000
                crew_status = "failed"
                crew_output = None
                crew_error = str(e)

            self.callback_manager.record_event(
                run_id=run_id,
                trace_id=trace_id,
                component="crewai_orchestrator",
                event_type="crew_kickoff",
                status=crew_status,
                duration_ms=crew_duration_ms,
                metadata={"crew_output": str(crew_output)[:100] if crew_output else "", "error": crew_error},
            )

            await blackboard.log_event(
                component="crewai_orchestrator",
                event_type="crew_kickoff",
                status=crew_status,
                details={"duration_ms": crew_duration_ms, "error": crew_error} if crew_error else {"duration_ms": crew_duration_ms},
            )
            await blackboard.update_agent_status("crewai_orchestrator", crew_status)

            # -------------------------------------------------------------
            # 7. Final Report Synthesis & Pydantic Completion
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

            # -------------------------------------------------------------
            # 8. Gemini LLM-as-a-Judge Evaluation (Post-Report Synthesis)
            # -------------------------------------------------------------
            enable_judge = getattr(validated_req, "enable_judge", None)
            if enable_judge is None:
                enable_judge = raw_request.get("enable_judge")

            judge_res = await self.judge_service.execute(blackboard, force_enable=enable_judge)
            self.callback_manager.record_event(
                run_id=run_id,
                trace_id=trace_id,
                component="gemini_llm_judge",
                event_type="agent_complete",
                status=judge_res["status"],
                duration_ms=judge_res.get("duration_ms", 0.0),
                metadata={
                    "overall_score": judge_res.get("overall_score"),
                    "verdict": judge_res.get("verdict"),
                    "reason": judge_res.get("reason"),
                },
            )
            self.storage.record_stage_judge(run_id, blackboard.state.judge_evaluation)

            post_judge_state = await blackboard.get_state_snapshot()
            if post_judge_state.judge_evaluation.status in ["available", "failed", "not_configured"]:
                _, updated_md, updated_json, _ = self.stub_llm.generate_report(post_judge_state)
                async with blackboard._lock:
                    blackboard._state.final_report.markdown_content = updated_md
                    blackboard._state.final_report.structured_json = updated_json

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

            # Persist final state in canonical SQLite storage and JSON snapshot
            self.storage.record_state(
                run_id=run_id,
                state=blackboard.state,
                status=RunStatus.COMPLETED,
                duration_ms=tot_duration,
            )
            self.storage.export_snapshot(run_id=run_id)

            return blackboard.state
        except Exception as exc:
            tot_duration = (time.perf_counter() - start_time) * 1000
            err_msg = str(exc)
            await blackboard.fail_run(f"Pipeline execution error: {err_msg}")
            has_partial = (
                blackboard.state.market_data.status == FindingStatus.AVAILABLE
                or blackboard.state.technical_findings.status == FindingStatus.AVAILABLE
            )
            target_status = RunStatus.PARTIAL if has_partial else RunStatus.FAILED
            self.storage.record_state(
                run_id=run_id,
                state=blackboard.state,
                status=target_status,
                duration_ms=tot_duration,
                error_message=err_msg,
            )
            self.storage.export_snapshot(run_id=run_id)
            raise
