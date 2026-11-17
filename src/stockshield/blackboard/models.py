"""Pydantic-validated models for StockShield 2.0 Blackboard Architecture."""

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from stockshield.judge.models import JudgeEvaluationState


class FindingStatus(str, Enum):
    PENDING = "pending"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"
    SKIPPED = "skipped"


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
    is_stale: bool = False
    freshness_age_days: Optional[int] = None
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


class NewsArticle(BaseModel):
    """Represents a validated financial news article."""

    title: str = Field(..., min_length=1, max_length=500, description="Cleaned article headline")
    source: str = Field(default="Unknown Source", max_length=200, description="Publishing outlet or wire")
    published_date: Optional[str] = Field(default=None, description="Publication timestamp or date string")
    url: Optional[str] = Field(default=None, description="Direct web URL to source article")
    description: Optional[str] = Field(default="", max_length=1000, description="Summary or opening snippet")

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        cleaned = " ".join(v.split()).strip()
        if not cleaned:
            raise ValueError("Article title cannot be empty.")
        return cleaned

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v_str = str(v).strip()
        if not v_str:
            return None
        if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", v_str, re.IGNORECASE):
            if v_str.startswith("http://") or v_str.startswith("https://"):
                return v_str
            return None
        return v_str


class ArticleSentiment(BaseModel):
    """Structured sentiment classification and event categorization for an individual article."""

    article: NewsArticle
    sentiment: str = Field(..., description="Classification: POSITIVE, NEGATIVE, or NEUTRAL")
    explanation: str = Field(..., max_length=500, description="Concise rationale for sentiment determination")
    financial_event_topic: str = Field(
        default="Corporate & Market Update",
        max_length=150,
        description="Key corporate or financial event topic",
    )
    ticker: str = Field(..., description="Target stock ticker symbol")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment_category(cls, v: str) -> str:
        s = v.strip().upper()
        if s not in {"POSITIVE", "NEGATIVE", "NEUTRAL"}:
            raise ValueError(f"Invalid sentiment '{v}'. Must be POSITIVE, NEGATIVE, or NEUTRAL.")
        return s


class NewsSentimentResult(BaseModel):
    """Aggregated sentiment analysis and risk observation payload."""

    ticker: str
    total_articles: int = Field(default=0, ge=0)
    positive_count: int = Field(default=0, ge=0)
    negative_count: int = Field(default=0, ge=0)
    neutral_count: int = Field(default=0, ge=0)
    overall_sentiment: str = Field(default="NEUTRAL", description="POSITIVE, NEGATIVE, NEUTRAL, or MIXED")
    sentiment_score: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Normalized score from -1.0 (bearish) to +1.0 (bullish)"
    )
    articles: List[ArticleSentiment] = Field(default_factory=list)
    positive_events: List[str] = Field(default_factory=list)
    negative_events: List[str] = Field(default_factory=list)
    risk_observations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class NewsSentimentState(BaseModel):
    """Blackboard state domain model for News and Sentiment intelligence."""

    status: FindingStatus = FindingStatus.PENDING
    producer: Optional[str] = None
    timestamp_utc: Optional[str] = None
    source: str = "google_news_rss"
    ticker: Optional[str] = None
    total_articles: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    overall_sentiment: str = "NEUTRAL"
    sentiment_score: float = 0.0
    articles: List[ArticleSentiment] = Field(default_factory=list)
    positive_events: List[str] = Field(default_factory=list)
    negative_events: List[str] = Field(default_factory=list)
    risk_observations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ForecastPoint(BaseModel):
    """Point prediction for a specific trading day horizon."""

    horizon_trading_days: int = Field(
        ..., ge=1, le=1000, description="Trading days ahead (e.g., 1, 5, 10, 21, 63, 126, 252, 504)"
    )
    forecast_date: str = Field(..., description="Projected trading session date (YYYY-MM-DD)")
    predicted_close: float = Field(..., gt=0.0, description="Forecasted closing price in native currency")
    predicted_change_pct: float = Field(..., description="Percentage change relative to latest observed close")
    lower_bound_95: Optional[float] = Field(default=None, description="Lower 95% prediction interval bound")
    upper_bound_95: Optional[float] = Field(default=None, description="Upper 95% prediction interval bound")
    model_name: str = Field(..., description="Model that generated this forecast (ARIMA, ExponentialSmoothing, LightGBM)")

    @field_validator("predicted_close")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Predicted close must be strictly positive.")
        return round(v, 4)

    @field_validator("predicted_change_pct")
    @classmethod
    def round_change(cls, v: float) -> float:
        return round(v, 2)

    @property
    def step(self) -> int:
        return self.horizon_trading_days

    @property
    def target_date(self) -> str:
        return self.forecast_date

    @property
    def predicted_price(self) -> float:
        return self.predicted_close

    @property
    def pct_change(self) -> float:
        return self.predicted_change_pct

    @property
    def conf_lower(self) -> Optional[float]:
        return self.lower_bound_95

    @property
    def conf_upper(self) -> Optional[float]:
        return self.upper_bound_95


class ModelEvaluationMetrics(BaseModel):
    """Validation performance metrics evaluated on chronological out-of-sample data."""

    model_name: str = Field(..., description="Model identifier")
    mae: float = Field(default=0.0, ge=0.0, description="Mean Absolute Error on validation window")
    rmse: float = Field(default=0.0, ge=0.0, description="Root Mean Squared Error on validation window")
    directional_accuracy_pct: float = Field(
        default=50.0, ge=0.0, le=100.0, description="Percentage of correct directional movement predictions"
    )
    status: str = Field(default="success", description="Status of model training: success or failed")
    error_message: Optional[str] = Field(default=None, description="Failure reason if model failed to converge")

    @property
    def directional_accuracy(self) -> float:
        return self.directional_accuracy_pct


class ForecastModelResult(BaseModel):
    """Complete forecast output and evaluation for an individual model."""

    model_name: str
    forecast_points: List[ForecastPoint] = Field(default_factory=list)
    metrics: ModelEvaluationMetrics

    @property
    def forecasts(self) -> List[ForecastPoint]:
        return self.forecast_points

    @property
    def validation_metrics(self) -> ModelEvaluationMetrics:
        return self.metrics

    @property
    def status(self) -> str:
        return self.metrics.status


class ForecastingState(BaseModel):
    """Blackboard state domain model for multi-model forward price forecasting."""

    status: FindingStatus = FindingStatus.PENDING
    producer: Optional[str] = None
    timestamp_utc: Optional[str] = None
    ticker: Optional[str] = None
    latest_observed_close: float = 0.0
    latest_observed_date: Optional[str] = None
    selected_model_name: str = "NONE"
    selection_reason: str = ""
    selected_forecasts: List[ForecastPoint] = Field(default_factory=list)
    model_results: Dict[str, ForecastModelResult] = Field(default_factory=dict)
    data_sufficiency_status: str = "pending"
    is_stale_data: bool = False
    forecast_label: str = "current_forward_looking"
    historical_bars_used: int = 0
    warnings: List[str] = Field(default_factory=list)

    @property
    def best_model(self) -> Optional[ForecastModelResult]:
        if self.selected_model_name and self.selected_model_name in self.model_results:
            return self.model_results[self.selected_model_name]
        return None

    @property
    def models(self) -> List[ForecastModelResult]:
        return list(self.model_results.values())

    @property
    def model_divergence_pct(self) -> float:
        """Percentage difference between maximum and minimum 10-step forecast across models."""
        h10_preds = []
        for m in self.model_results.values():
            p10 = next((p for p in m.forecast_points if p.horizon_trading_days == 10), None)
            if p10:
                h10_preds.append(p10.predicted_close)
        if len(h10_preds) >= 2 and min(h10_preds) > 0:
            diff = max(h10_preds) - min(h10_preds)
            avg = sum(h10_preds) / len(h10_preds)
            return round((diff / avg) * 100.0, 2)
        return 0.0

    @property
    def directional_consensus(self) -> str:
        """Consensus directional trend across models."""
        directions = []
        for m in self.model_results.values():
            p10 = next((p for p in m.forecast_points if p.horizon_trading_days == 10), None)
            if p10:
                if p10.predicted_change_pct > 0.5:
                    directions.append("UP")
                elif p10.predicted_change_pct < -0.5:
                    directions.append("DOWN")
                else:
                    directions.append("NEUTRAL")
        if not directions:
            return "NEUTRAL"
        up_c = directions.count("UP")
        down_c = directions.count("DOWN")
        if up_c > len(directions) / 2:
            return "BULLISH"
        elif down_c > len(directions) / 2:
            return "BEARISH"
        return "MIXED"

    @property
    def findings(self) -> List[str]:
        return self.warnings


class ScenarioCategory(str, Enum):
    """Categories of scenario simulation and stress testing."""

    PRICE_SHOCK = "price_shock"
    VOLATILITY_SHOCK = "volatility_shock"
    NEWS_SENTIMENT = "news_sentiment"
    TECHNICAL_TREND = "technical_trend"
    COMBINED_STRESS = "combined_stress"
    CUSTOM = "custom"
    MONTE_CARLO = "monte_carlo"


class TechnicalTrendShock(str, Enum):
    """Hypothetical technical trend transition states."""

    NONE = "none"
    BULLISH_TO_NEUTRAL = "bullish_to_neutral"
    NEUTRAL_TO_BEARISH = "neutral_to_bearish"
    BREAK_BELOW_SMA20 = "break_below_sma20"
    BREAK_BELOW_SMA50 = "break_below_sma50"
    BREAK_BELOW_SMA200 = "break_below_sma200"
    BULLISH_RECOVERY = "bullish_recovery"


class CustomScenarioInput(BaseModel):
    """User-supplied hypothetical scenario parameters with strict bounds validation."""

    name: str = Field(default="Custom Scenario", min_length=1, max_length=100)
    category: ScenarioCategory = Field(default=ScenarioCategory.CUSTOM)
    description: Optional[str] = Field(default=None, max_length=500)
    price_shock_pct: float = Field(default=0.0, ge=-90.0, le=200.0)
    volatility_shock_pct: float = Field(default=0.0, ge=-80.0, le=500.0)
    volatility_multiplier: Optional[float] = Field(default=None, gt=0.0, le=10.0)
    sentiment_score: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    technical_trend: TechnicalTrendShock = Field(default=TechnicalTrendShock.NONE)
    portfolio_exposure_shares: Optional[float] = Field(default=None, ge=0.0)
    portfolio_exposure_value: Optional[float] = Field(default=None, ge=0.0)

    @field_validator("name", "description")
    @classmethod
    def sanitize_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        disallowed = ["<script", "javascript:", "__import__", "exec(", "eval("]
        for term in disallowed:
            if term in v.lower():
                raise ValueError(f"Dangerous expression detected in scenario input: '{term}'")
        return v.strip()


class BaselineMetrics(BaseModel):
    """Baseline actual market, sentiment, technical, and risk metrics prior to shock."""

    stock_price: float = Field(..., gt=0.0)
    volatility_pct: float = Field(..., ge=0.0)
    news_sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    news_sentiment_label: str
    technical_signal: str
    composite_risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: str
    recommendation: str


class SimulatedMetrics(BaseModel):
    """Hypothetical post-shock metrics calculated deterministically."""

    hypothetical_price: float = Field(..., gt=0.0)
    absolute_price_change: float
    percentage_price_change: float
    portfolio_value_impact: Optional[float] = None
    hypothetical_volatility_pct: float = Field(..., ge=0.0)
    volatility_change_pct: float
    hypothetical_sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    hypothetical_sentiment_label: str
    hypothetical_technical_signal: str
    scenario_risk_score: float = Field(..., ge=0.0, le=1.0)
    scenario_risk_level: str
    scenario_recommendation: str


class ScenarioComparison(BaseModel):
    """Detailed differential analysis comparing hypothetical scenario against baseline."""

    risk_score_delta: float
    risk_level_changed: bool
    recommendation_changed: bool
    recommendation_flip_direction: Optional[str] = None
    material_risk_increase: bool
    explanation: str


class ScenarioResult(BaseModel):
    """Complete stress test evaluation result for an individual scenario."""

    scenario_name: str
    category: ScenarioCategory
    description: str
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    inputs: CustomScenarioInput
    baseline: BaselineMetrics
    simulated: SimulatedMetrics
    comparison: ScenarioComparison
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    methodology: str = "deterministic_stress_testing"


class MonteCarloResult(BaseModel):
    """Stochastic price path simulation outputs using Geometric Brownian Motion."""

    num_simulations: int = Field(..., gt=0)
    horizon_days: int = Field(..., gt=0)
    random_seed: Optional[int] = None
    initial_price: float = Field(..., gt=0.0)
    mean_terminal_price: float = Field(..., gt=0.0)
    median_terminal_price: float = Field(..., gt=0.0)
    percentile_5_price: float = Field(..., gt=0.0)
    percentile_25_price: float = Field(..., gt=0.0)
    percentile_75_price: float = Field(..., gt=0.0)
    percentile_95_price: float = Field(..., gt=0.0)
    probability_loss_pct: float = Field(..., ge=0.0, le=100.0)
    probability_severe_loss_pct: float = Field(..., ge=0.0, le=100.0)
    expected_annualized_volatility: float = Field(..., ge=0.0)
    assumptions_and_disclosures: List[str] = Field(default_factory=list)


class ScenarioSimulationState(BaseModel):
    """Blackboard domain state model for Scenario Simulation and Stress Testing."""

    status: FindingStatus = FindingStatus.PENDING
    producer: Optional[str] = None
    timestamp_utc: Optional[str] = None
    ticker: Optional[str] = None
    baseline_price: float = 0.0
    baseline_volatility_pct: float = 0.0
    baseline_sentiment_score: float = 0.0
    baseline_risk_score: float = 0.0
    baseline_risk_level: str = "PENDING"
    baseline_recommendation: str = "PENDING"
    total_scenarios_evaluated: int = 0
    scenarios: List[ScenarioResult] = Field(default_factory=list)
    worst_case_scenario: Optional[ScenarioResult] = None
    best_case_scenario: Optional[ScenarioResult] = None
    scenarios_changing_recommendation: List[str] = Field(default_factory=list)
    scenarios_material_risk_increase: List[str] = Field(default_factory=list)
    monte_carlo_result: Optional[MonteCarloResult] = None
    warnings: List[str] = Field(default_factory=list)

    @property
    def worst_scenario_name(self) -> Optional[str]:
        return self.worst_case_scenario.scenario_name if self.worst_case_scenario else None

    @property
    def worst_scenario_risk_score(self) -> Optional[float]:
        return self.worst_case_scenario.simulated.scenario_risk_score if self.worst_case_scenario else None


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
    experiment_id: Optional[str] = None
    workflow_mode: str = "sequential"  # sequential, parallel, hierarchical
    time_horizon: str = "short_term"  # short_term, mid_term, long_term
    forecast_horizon: str = "1_month"  # 1_month, 3_months, 6_months, 1_year, 2_years
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING
    created_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at_utc: Optional[str] = None

    # Typed domain states
    market_data: MarketDataState = Field(default_factory=MarketDataState)
    technical_findings: TechnicalFindingsState = Field(default_factory=TechnicalFindingsState)
    fundamental_findings: FundamentalFindingsState = Field(default_factory=FundamentalFindingsState)
    news_sentiment: NewsSentimentState = Field(default_factory=NewsSentimentState)
    forecasting: ForecastingState = Field(default_factory=ForecastingState)
    risk_findings: RiskFindingsState = Field(default_factory=RiskFindingsState)
    scenario_simulation: ScenarioSimulationState = Field(default_factory=ScenarioSimulationState)
    final_report: FinalReportState = Field(default_factory=FinalReportState)
    judge_evaluation: JudgeEvaluationState = Field(default_factory=JudgeEvaluationState)

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
