"""Thread-safe, Pydantic-validated Blackboard implementation for StockShield 2.0."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from stockshield.blackboard.models import (
    DocumentSnippet,
    FinalReportState,
    FindingStatus,
    FundamentalFindingsState,
    MarketDataState,
    OHLCVBar,
    ProvenanceRecord,
    RiskCheck,
    RiskFindingsState,
    StockShieldBlackboard,
    TechnicalFindingsState,
    TechnicalIndicators,
    WorkflowStatus,
)


class BlackboardManager:
    """Manages concurrency, validation, and provenance for StockShieldBlackboard."""

    def __init__(self, run_id: str, trace_id: str, ticker: str, user_prompt: str, workflow_mode: str = "sequential"):
        self._lock = asyncio.Lock()
        self._state = StockShieldBlackboard(
            run_id=run_id,
            trace_id=trace_id,
            ticker=ticker.upper(),
            user_prompt=user_prompt,
            workflow_mode=workflow_mode,
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

    async def update_market_data(
        self,
        producer: str,
        source: str,
        bars: List[Dict[str, Any]],
        data_quality_status: str = "valid",
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
