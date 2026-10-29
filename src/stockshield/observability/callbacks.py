"""Callbacks and observability framework for StockShield 2.0.

Provides lifecycle hooks, audit logging, and JSONL persistence for runs, agents,
MCP tools, A2A exchanges, validation checks, and errors.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExecutionEvent(BaseModel):
    run_id: str
    trace_id: str
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    component: str  # e.g., 'mcp_market_data', 'google_adk_technical', 'risk_engine'
    event_type: str  # 'run_start', 'agent_start', 'tool_call', 'state_update', 'guardrail_trigger', 'error'
    status: str  # 'started', 'completed', 'failed', 'blocked', 'warning'
    duration_ms: Optional[float] = None
    error_category: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ObservabilityCallbackManager:
    """Central callback manager logging to in-memory buffers and persistent JSONL."""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path("evaluation_results/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.events: List[ExecutionEvent] = []
        self._enabled = True

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def record_event(
        self,
        run_id: str,
        trace_id: str,
        component: str,
        event_type: str,
        status: str,
        duration_ms: Optional[float] = None,
        error_category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionEvent:
        if not self._enabled:
            # When callbacks are disabled (for ablation experiments), we do not log
            return None

        event = ExecutionEvent(
            run_id=run_id,
            trace_id=trace_id,
            component=component,
            event_type=event_type,
            status=status,
            duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            error_category=error_category,
            metadata=metadata or {},
        )
        self.events.append(event)

        # Append to JSONL audit log file
        log_file = self.log_dir / f"audit_{run_id}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")

        return event

    def get_events_for_run(self, run_id: str) -> List[ExecutionEvent]:
        return [e for e in self.events if e.run_id == run_id]
