"""Thread-safe, Pydantic-validated Blackboard implementation for StockShield 2.0."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from stockshield.blackboard.models import (
    ArticleSentiment,
    DocumentSnippet,
    FinalReportState,
    FindingStatus,
    ForecastingState,
    ForecastModelResult,
    ForecastPoint,
    FundamentalFindingsState,
    MarketDataState,
    MonteCarloResult,
    NewsSentimentState,
    OHLCVBar,
    ProvenanceRecord,
    RiskCheck,
    RiskFindingsState,
    ScenarioResult,
    ScenarioSimulationState,
    StockShieldBlackboard,
    TechnicalFindingsState,
    TechnicalIndicators,
    WorkflowStatus,
)
from stockshield.judge.models import JudgeEvaluationState


class BlackboardManager:
    """Manages concurrency, validation, and provenance for StockShieldBlackboard."""

    def __init__(
        self,
        run_id: str,
        trace_id: str,
        ticker: str,
        user_prompt: str,
        workflow_mode: str = "sequential",
        time_horizon: str = "short_term",
        forecast_horizon: str = "1_month",
        experiment_id: Optional[str] = None,
    ):
        self._lock = asyncio.Lock()
        self._state = StockShieldBlackboard(
            run_id=run_id,
            trace_id=trace_id,
            ticker=ticker.upper(),
            user_prompt=user_prompt,
            workflow_mode=workflow_mode,
            time_horizon=time_horizon,
            forecast_horizon=forecast_horizon,
            experiment_id=experiment_id,
            workflow_status=WorkflowStatus.RUNNING,
        )

    @property
    def state(self) -> StockShieldBlackboard:
        """Returns a snapshot of the current blackboard state."""
        return self._state.model_copy(deep=True)

    async def get_state_snapshot(self) -> StockShieldBlackboard:
        """Concurrency-safe snapshot of state."""
        async with self._lock:
            return self._state.model_copy(deep=True)

    async def log_event(self, component: str, event_type: str, status: str, details: Optional[Dict[str, Any]] = None):
        """Append an execution event to the blackboard audit trail."""
        async with self._lock:
            event = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "component": component,
                "event_type": event_type,
                "status": status,
                "details": details or {},
            }
            self._state.execution_events.append(event)

    async def update_agent_status(self, agent_name: str, status: str):
        """Update operational status for an orchestrator or agent component."""
        async with self._lock:
            self._state.agent_statuses[agent_name] = status

    async def update_market_data(
        self,
        producer: str,
        source: str,
        bars: List[Dict[str, Any]],
        data_quality_status: str = "valid",
        is_stale: bool = False,
        freshness_age_days: Optional[int] = None,
        currency: str = "INR",
        exchange: str = "NSE",
        status: FindingStatus = FindingStatus.AVAILABLE,
        notes: Optional[str] = None,
    ):
        """Record market data onto the blackboard with full provenance."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            prev_status = self._state.market_data.status

            parsed_bars = [OHLCVBar(**b) for b in bars]
            start_date = parsed_bars[0].timestamp if parsed_bars else None
            end_date = parsed_bars[-1].timestamp if parsed_bars else None

            self._state.market_data = MarketDataState(
                status=status,
                producer=producer,
                timestamp_utc=now_iso,
                source=source,
                ticker=self._state.ticker,
                currency=currency,
                exchange=exchange,
                data_quality_status=data_quality_status,
                is_stale=is_stale,
                freshness_age_days=freshness_age_days,
                bar_count=len(parsed_bars),
                start_date=start_date,
                end_date=end_date,
                bars=parsed_bars,
            )

            # Record provenance
            self._state.provenance_trail.append(
                ProvenanceRecord(
                    producer=producer,
                    source=source,
                    field_name="market_data",
                    previous_status=prev_status,
                    new_status=status,
                    notes=notes or f"Loaded {len(parsed_bars)} bars from {source}",
                )
            )

            # Update agent & tool statuses
            self._state.agent_statuses[producer] = status.value
            self._state.tool_statuses[f"{producer}_tool"] = status.value

    async def update_technical_findings(
        self,
        producer: str,
        indicators: Dict[str, Optional[float]],
        signal: str,
        signal_confidence: float,
        summary: str,
        lookback_periods_used: int,
        warnings: Optional[List[str]] = None,
        status: FindingStatus = FindingStatus.AVAILABLE,
        notes: Optional[str] = None,
    ):
        """Update technical findings on blackboard."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            prev_status = self._state.technical_findings.status

            self._state.technical_findings = TechnicalFindingsState(
                status=status,
                producer=producer,
                timestamp_utc=now_iso,
                source="adk_technical_agent",
                indicators=TechnicalIndicators(**indicators),
                signal=signal,
                signal_confidence=signal_confidence,
                summary=summary,
                lookback_periods_used=lookback_periods_used,
                warnings=warnings or [],
            )

            self._state.provenance_trail.append(
                ProvenanceRecord(
                    producer=producer,
                    source="google_adk_technical_agent",
                    field_name="technical_findings",
                    previous_status=prev_status,
                    new_status=status,
                    notes=notes or f"Technical indicators computed with signal={signal}",
                )
            )
            self._state.agent_statuses[producer] = status.value

    async def update_risk_findings(
        self,
        producer: str,
        overall_risk_level: str,
        composite_risk_score: float,
        recommendation: str,
        checks: List[Dict[str, Any]],
        warnings: Optional[List[str]] = None,
        reasons: Optional[List[str]] = None,
        status: FindingStatus = FindingStatus.AVAILABLE,
        notes: Optional[str] = None,
    ):
        """Update deterministic risk review findings on blackboard."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            prev_status = self._state.risk_findings.status

            parsed_checks = [RiskCheck(**c) for c in checks]
            self._state.risk_findings = RiskFindingsState(
                status=status,
                producer=producer,
                timestamp_utc=now_iso,
                source="deterministic_risk_engine",
                overall_risk_level=overall_risk_level,
                composite_risk_score=composite_risk_score,
                recommendation=recommendation,
                checks=parsed_checks,
                warnings=warnings or [],
                reasons=reasons or [],
            )

            self._state.provenance_trail.append(
                ProvenanceRecord(
                    producer=producer,
                    source="deterministic_risk_engine",
                    field_name="risk_findings",
                    previous_status=prev_status,
                    new_status=status,
                    notes=notes or f"Risk evaluated: {overall_risk_level} ({recommendation})",
                )
            )
            self._state.agent_statuses[producer] = status.value

    async def update_fundamental_findings(
        self,
        producer: str,
        ratios: Dict[str, float],
        snippets: Optional[List[Dict[str, Any]]] = None,
        warnings: Optional[List[str]] = None,
        status: FindingStatus = FindingStatus.AVAILABLE,
        notes: Optional[str] = None,
    ):
        """Update fundamental and document evidence findings."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            prev_status = self._state.fundamental_findings.status

            parsed_snippets = [DocumentSnippet(**s) for s in (snippets or [])]
            self._state.fundamental_findings = FundamentalFindingsState(
                status=status,
                producer=producer,
                timestamp_utc=now_iso,
                source="mcp_financial_evidence",
                ratios=ratios,
                snippets=parsed_snippets,
                warnings=warnings or [],
            )

            self._state.provenance_trail.append(
                ProvenanceRecord(
                    producer=producer,
                    source="mcp_financial_evidence",
                    field_name="fundamental_findings",
                    previous_status=prev_status,
                    new_status=status,
                    notes=notes or "Financial ratios and evidence recorded",
                )
            )
            self._state.agent_statuses[producer] = status.value

    async def update_news_sentiment(
        self,
        producer: str,
        total_articles: int,
        positive_count: int,
        negative_count: int,
        neutral_count: int,
        overall_sentiment: str,
        sentiment_score: float,
        articles: Optional[List[ArticleSentiment]] = None,
        positive_events: Optional[List[str]] = None,
        negative_events: Optional[List[str]] = None,
        risk_observations: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        source: str = "google_news_rss",
        status: FindingStatus = FindingStatus.AVAILABLE,
        notes: Optional[str] = None,
    ):
        """Update news and sentiment findings on the blackboard."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            prev_status = self._state.news_sentiment.status

            self._state.news_sentiment = NewsSentimentState(
                status=status,
                producer=producer,
                timestamp_utc=now_iso,
                source=source,
                ticker=self._state.ticker,
                total_articles=total_articles,
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=neutral_count,
                overall_sentiment=overall_sentiment,
                sentiment_score=round(sentiment_score, 3),
                articles=articles or [],
                positive_events=positive_events or [],
                negative_events=negative_events or [],
                risk_observations=risk_observations or [],
                warnings=warnings or [],
            )

            self._state.provenance_trail.append(
                ProvenanceRecord(
                    producer=producer,
                    source=source,
                    field_name="news_sentiment",
                    previous_status=prev_status,
                    new_status=status,
                    notes=notes or f"News analyzed: {total_articles} articles ({overall_sentiment}, score={sentiment_score:.2f})",
                )
            )
            self._state.agent_statuses[producer] = status.value

    async def update_forecasting(
        self,
        producer: str,
        latest_observed_close: float,
        latest_observed_date: Optional[str],
        selected_model_name: str,
        selection_reason: str,
        selected_forecasts: List[ForecastPoint],
        model_results: Dict[str, ForecastModelResult],
        data_sufficiency_status: str = "valid",
        is_stale_data: bool = False,
        forecast_label: str = "current_forward_looking",
        historical_bars_used: int = 0,
        warnings: Optional[List[str]] = None,
        status: FindingStatus = FindingStatus.AVAILABLE,
        notes: Optional[str] = None,
    ):
        """Update forecasting findings on the blackboard with thread safety and provenance."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            prev_status = self._state.forecasting.status

            self._state.forecasting = ForecastingState(
                status=status,
                producer=producer,
                timestamp_utc=now_iso,
                ticker=self._state.ticker,
                latest_observed_close=latest_observed_close,
                latest_observed_date=latest_observed_date,
                selected_model_name=selected_model_name,
                selection_reason=selection_reason,
                selected_forecasts=selected_forecasts,
                model_results=model_results,
                data_sufficiency_status=data_sufficiency_status,
                is_stale_data=is_stale_data,
                forecast_label=forecast_label,
                historical_bars_used=historical_bars_used,
                warnings=warnings or [],
            )

            self._state.provenance_trail.append(
                ProvenanceRecord(
                    producer=producer,
                    source="time_series_forecasting_models",
                    field_name="forecasting",
                    previous_status=prev_status,
                    new_status=status,
                    notes=notes or f"Forecasting completed: best model={selected_model_name} ({len(selected_forecasts)} horizons)",
                )
            )
            self._state.agent_statuses[producer] = status.value

    async def update_scenario_simulation(
        self,
        producer: str,
        baseline_price: float = 0.0,
        baseline_volatility_pct: float = 0.0,
        baseline_sentiment_score: float = 0.0,
        baseline_risk_score: float = 0.0,
        baseline_risk_level: str = "PENDING",
        baseline_recommendation: str = "PENDING",
        scenarios: Optional[List[ScenarioResult]] = None,
        worst_case_scenario: Optional[ScenarioResult] = None,
        best_case_scenario: Optional[ScenarioResult] = None,
        scenarios_changing_recommendation: Optional[List[str]] = None,
        scenarios_material_risk_increase: Optional[List[str]] = None,
        monte_carlo_result: Optional[MonteCarloResult] = None,
        warnings: Optional[List[str]] = None,
        status: FindingStatus = FindingStatus.AVAILABLE,
        notes: Optional[str] = None,
    ):
        """Update scenario simulation and stress testing findings on the blackboard with thread safety and provenance."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            prev_status = self._state.scenario_simulation.status
            scen_list = scenarios or []

            self._state.scenario_simulation = ScenarioSimulationState(
                status=status,
                producer=producer,
                timestamp_utc=now_iso,
                ticker=self._state.ticker,
                baseline_price=baseline_price,
                baseline_volatility_pct=baseline_volatility_pct,
                baseline_sentiment_score=baseline_sentiment_score,
                baseline_risk_score=baseline_risk_score,
                baseline_risk_level=baseline_risk_level,
                baseline_recommendation=baseline_recommendation,
                total_scenarios_evaluated=len(scen_list),
                scenarios=scen_list,
                worst_case_scenario=worst_case_scenario,
                best_case_scenario=best_case_scenario,
                scenarios_changing_recommendation=scenarios_changing_recommendation or [],
                scenarios_material_risk_increase=scenarios_material_risk_increase or [],
                monte_carlo_result=monte_carlo_result,
                warnings=warnings or [],
            )

            self._state.provenance_trail.append(
                ProvenanceRecord(
                    producer=producer,
                    source="deterministic_scenario_simulation",
                    field_name="scenario_simulation",
                    previous_status=prev_status,
                    new_status=status,
                    notes=notes or f"Scenario simulation completed: {len(scen_list)} scenarios evaluated",
                )
            )
            self._state.agent_statuses[producer] = status.value

    async def update_judge_evaluation(
        self,
        producer: str = "gemini_llm_judge",
        status: FindingStatus = FindingStatus.AVAILABLE,
        model_name: Optional[str] = None,
        configured_model: Optional[str] = None,
        actual_model: Optional[str] = None,
        fallback_triggered: bool = False,
        prompt_version: str = "v1.0",
        has_sufficient_evidence: bool = True,
        overall_score: Optional[float] = None,
        verdict: Optional[str] = None,
        dimensions: Optional[Dict[str, Any]] = None,
        critical_findings: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        strengths: Optional[List[str]] = None,
        limitations: Optional[List[str]] = None,
        evaluation_summary: str = "",
        latency_ms: Optional[float] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        estimated_cost_usd: Optional[float] = None,
        cost_status: str = "unavailable",
        attempt_history: Optional[List[Dict[str, Any]]] = None,
        error_message: Optional[str] = None,
        notes: Optional[str] = None,
    ):
        """Update Gemini LLM-as-a-Judge evaluation findings on the blackboard with thread safety and provenance."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            prev_status_str = self._state.judge_evaluation.status
            try:
                prev_status = FindingStatus(prev_status_str)
            except ValueError:
                prev_status = FindingStatus.PENDING

            def _clean_str(val: Any) -> Optional[str]:
                if val is None:
                    return None
                if isinstance(val, str):
                    return val
                return str(val)

            effective_actual = _clean_str(actual_model or model_name)
            effective_configured = _clean_str(configured_model or model_name)

            self._state.judge_evaluation = JudgeEvaluationState(
                status=status.value if hasattr(status, "value") else str(status),
                producer=str(producer),
                timestamp_utc=now_iso,
                model_name=effective_actual or effective_configured,
                configured_model=effective_configured,
                actual_model=effective_actual,
                fallback_triggered=bool(fallback_triggered),
                prompt_version=str(prompt_version),
                has_sufficient_evidence=bool(has_sufficient_evidence),
                overall_score=overall_score,
                verdict=_clean_str(verdict),
                dimensions=dimensions or {},
                critical_findings=critical_findings or [],
                warnings=warnings or [],
                strengths=strengths or [],
                limitations=limitations or [],
                evaluation_summary=str(evaluation_summary) if evaluation_summary else "",
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost_usd,
                cost_status=str(cost_status),
                attempt_history=attempt_history or [],
                error_message=_clean_str(error_message),
            )

            self._state.provenance_trail.append(
                ProvenanceRecord(
                    producer=producer,
                    source="gemini_llm_judge",
                    field_name="judge_evaluation",
                    previous_status=prev_status,
                    new_status=status,
                    notes=notes or f"Judge evaluation status: {status.value if hasattr(status, 'value') else status}",
                )
            )
            self._state.agent_statuses[producer] = status.value if hasattr(status, "value") else str(status)

    async def complete_run(
        self,
        executive_summary: str,
        markdown_content: str,
        structured_json: Dict[str, Any],
        token_usage: Optional[Dict[str, int]] = None,
        cost_usd: float = 0.0,
    ):
        """Mark workflow completed and finalize executive report."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            self._state.final_report = FinalReportState(
                status=FindingStatus.AVAILABLE,
                producer="stockshield_orchestrator",
                timestamp_utc=now_iso,
                executive_summary=executive_summary,
                markdown_content=markdown_content,
                structured_json=structured_json,
            )
            self._state.workflow_status = WorkflowStatus.COMPLETED
            self._state.completed_at_utc = now_iso
            if token_usage:
                self._state.token_usage = token_usage
            self._state.cost_estimation_usd = cost_usd

    async def fail_run(self, error_message: str):
        """Mark workflow as failed with error trace."""
        async with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            self._state.workflow_status = WorkflowStatus.FAILED
            self._state.completed_at_utc = now_iso
            self._state.validation_errors.append(error_message)
            self._state.final_report.status = FindingStatus.FAILED
