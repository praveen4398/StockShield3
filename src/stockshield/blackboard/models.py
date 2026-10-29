"""Pydantic-validated models for StockShield 2.0 Blackboard Architecture."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FindingStatus(str, Enum):
    PENDING = "pending"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProvenanceRecord(BaseModel):
    producer: str
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str  # e.g., 'fixture', 'live', 'mcp_market_data', 'adk_technical_agent'
    field_name: str
    previous_status: Optional[FindingStatus] = None
    new_status: FindingStatus
    notes: Optional[str] = None


class OHLCVBar(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: int


class MarketDataState(BaseModel):
    status: FindingStatus = FindingStatus.PENDING
    producer: Optional[str] = None
    timestamp_utc: Optional[str] = None
    source: str = "unknown"  # fixture or live
    ticker: Optional[str] = None
    currency: str = "INR"
    exchange: str = "NSE"
    data_quality_status: str = "pending"
    bar_count: int = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bars: List[OHLCVBar] = Field(default_factory=list)


class TechnicalIndicators(BaseModel):
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    rsi_14: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_bandwidth: Optional[float] = None
    atr_14: Optional[float] = None


class TechnicalFindingsState(BaseModel):
    status: FindingStatus = FindingStatus.PENDING
    producer: Optional[str] = None
    timestamp_utc: Optional[str] = None
    source: str = "google_adk_technical_agent"
    indicators: TechnicalIndicators = Field(default_factory=TechnicalIndicators)
    signal: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    signal_confidence: float = 0.0
    summary: str = ""
    lookback_periods_used: int = 0
    warnings: List[str] = Field(default_factory=list)


class RiskCheck(BaseModel):
    name: str
    passed: bool
    score: float  # 0.0 (safe) to 1.0 (severe risk)
    message: str


class RiskFindingsState(BaseModel):
    status: FindingStatus = FindingStatus.PENDING
    producer: Optional[str] = None
    timestamp_utc: Optional[str] = None
    source: str = "deterministic_risk_engine"
    overall_risk_level: str = "UNKNOWN"  # LOW, MODERATE, HIGH, CRITICAL
    composite_risk_score: float = 0.0  # 0.0 to 1.0
    recommendation: str = "PENDING"  # APPROVED, APPROVED_WITH_CAUTION, REJECTED_HIGH_RISK
    checks: List[RiskCheck] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class DocumentSnippet(BaseModel):
    document_name: str
    page_number: int
    text_snippet: str
    source_url: Optional[str] = None


class FundamentalFindingsState(BaseModel):
    status: FindingStatus = FindingStatus.PENDING
    producer: Optional[str] = None
    timestamp_utc: Optional[str] = None
    source: str = "mcp_financial_evidence"
    ratios: Dict[str, float] = Field(default_factory=dict)
    snippets: List[DocumentSnippet] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class FinalReportState(BaseModel):
    status: FindingStatus = FindingStatus.PENDING
    producer: Optional[str] = None
    timestamp_utc: Optional[str] = None
    executive_summary: str = ""
    markdown_content: str = ""
    structured_json: Dict[str, Any] = Field(default_factory=dict)


class StockShieldBlackboard(BaseModel):
    run_id: str
    trace_id: str
    ticker: str
    user_prompt: str
    workflow_mode: str = "sequential"  # sequential, parallel, hierarchical
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING
    created_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at_utc: Optional[str] = None

    # Typed domain states
    market_data: MarketDataState = Field(default_factory=MarketDataState)
    technical_findings: TechnicalFindingsState = Field(default_factory=TechnicalFindingsState)
    fundamental_findings: FundamentalFindingsState = Field(default_factory=FundamentalFindingsState)
    risk_findings: RiskFindingsState = Field(default_factory=RiskFindingsState)
    final_report: FinalReportState = Field(default_factory=FinalReportState)

    # Audit, Provenance & Execution tracking
    agent_statuses: Dict[str, str] = Field(default_factory=dict)
    tool_statuses: Dict[str, str] = Field(default_factory=dict)
    validation_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    provenance_trail: List[ProvenanceRecord] = Field(default_factory=list)
    execution_events: List[Dict[str, Any]] = Field(default_factory=list)

    # Cost & Token Estimation Metadata
    token_usage: Dict[str, int] = Field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    )
    cost_estimation_usd: float = 0.0
