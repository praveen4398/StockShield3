"""Pydantic v2 domain models for Gemini LLM-as-a-Judge in StockShield 2.0.

Provides strict schemas for the 6-dimension evaluation rubric, evidence references,
verdict classifications, and structured evaluation outputs.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DimensionName(str, Enum):
    """The six required evaluation dimensions for StockShield report assessment."""

    FACTUAL_GROUNDING = "factual_grounding"
    COMPLETENESS = "completeness"
    CROSS_AGENT_CONSISTENCY = "cross_agent_consistency"
    FORECASTING_ASSESSMENT = "forecasting_assessment"
    RISK_REASONING = "risk_reasoning"
    FINANCIAL_SAFETY = "financial_safety"


class JudgeVerdict(str, Enum):
    """Categorical quality verdicts based on aggregated evaluation dimensions."""

    EXCELLENT = "EXCELLENT"  # Mean score >= 8.5
    GOOD = "GOOD"  # Mean score >= 7.0
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"  # Mean score >= 5.0
    POOR = "POOR"  # Mean score < 5.0
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"  # Insufficient data to evaluate


class DimensionScore(BaseModel):
    """Evaluation score and detailed audit reasoning for an individual rubric dimension."""

    dimension: DimensionName
    score: float = Field(
        ...,
        ge=1.0,
        le=10.0,
        description="Evaluation score from 1.0 (critical deficit) to 10.0 (rigorous/exemplary).",
    )
    explanation: str = Field(
        ...,
        min_length=10,
        max_length=1500,
        description="Detailed explanation justifying the assigned score.",
    )
    evidence_references: List[str] = Field(
        default_factory=list,
        description="Explicit references to supplied fields, tables, or report sections.",
    )
    identified_issues: List[str] = Field(
        default_factory=list,
        description="Specific factual, logical, or safety issues identified in this dimension.",
    )

    @field_validator("score")
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(float(v), 2)

    @model_validator(mode="after")
    def validate_evidence_when_issues_present(self) -> "DimensionScore":
        # If specific issues are claimed, at least one evidence reference or descriptive explanation is required
        if self.identified_issues and not self.evidence_references and len(self.explanation) < 20:
            raise ValueError(
                f"Dimension '{self.dimension.value}' identified issues but provided no evidence references or detailed explanation."
            )
        return self


class JudgeEvaluationOutput(BaseModel):
    """Structured output schema returned by the Gemini LLM-as-a-Judge."""

    has_sufficient_evidence: bool = Field(
        default=True,
        description="Whether the supplied report and Blackboard findings contain sufficient data to evaluate.",
    )
    dimensions: List[DimensionScore] = Field(
        ...,
        description="Exact evaluations for each of the six rubric dimensions.",
    )
    overall_score: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=10.0,
        description="Calculated arithmetic mean across all six dimension scores.",
    )
    verdict: JudgeVerdict = Field(
        ...,
        description="Categorical quality assessment verdict.",
    )
    critical_findings: List[str] = Field(
        default_factory=list,
        description="High-priority concerns regarding factual inaccuracies or safety risks.",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Cautionary notes regarding methodology limitations, sparse data, or marginal inconsistencies.",
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Specific areas where the analysis demonstrated high rigor, clarity, or consistency.",
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Inherent constraints of the LLM-as-a-Judge assessment.",
    )
    evaluation_summary: str = Field(
        default="",
        max_length=2000,
        description="Concise executive synthesis of the evaluation.",
    )

    @field_validator("dimensions")
    @classmethod
    def validate_all_dimensions_present(cls, v: List[DimensionScore]) -> List[DimensionScore]:
        dims_present = {d.dimension for d in v}
        required = set(DimensionName)
        missing = required - dims_present
        if missing:
            raise ValueError(f"Missing required rubric dimensions: {[m.value for m in missing]}")
        return v

    @model_validator(mode="after")
    def compute_and_validate_overall(self) -> "JudgeEvaluationOutput":
        if not self.has_sufficient_evidence:
            self.overall_score = None
            self.verdict = JudgeVerdict.INSUFFICIENT_EVIDENCE
            return self

        # Compute or verify arithmetic mean
        scores = [d.score for d in self.dimensions]
        calc_mean = round(sum(scores) / len(scores), 2)
        if self.overall_score is None:
            self.overall_score = calc_mean

        # Determine verdict if not explicitly matched
        if self.overall_score >= 8.5:
            expected_verdict = JudgeVerdict.EXCELLENT
        elif self.overall_score >= 7.0:
            expected_verdict = JudgeVerdict.GOOD
        elif self.overall_score >= 5.0:
            expected_verdict = JudgeVerdict.NEEDS_IMPROVEMENT
        else:
            expected_verdict = JudgeVerdict.POOR

        # Allow assigned verdict or default to calculated
        if self.verdict == JudgeVerdict.INSUFFICIENT_EVIDENCE:
            self.verdict = expected_verdict

        return self


class JudgeEvaluationState(BaseModel):
    """Blackboard domain state representation for Gemini LLM-as-a-Judge evaluation."""

    status: str = "pending"  # pending, available, not_configured, failed, unavailable, skipped
    producer: str = "gemini_llm_judge"
    timestamp_utc: Optional[str] = None
    model_name: Optional[str] = None
    configured_model: Optional[str] = None
    actual_model: Optional[str] = None
    fallback_triggered: bool = False
    prompt_version: str = "v1.0"
    has_sufficient_evidence: bool = True
    overall_score: Optional[float] = None
    verdict: Optional[str] = None
    dimensions: Dict[str, DimensionScore] = Field(default_factory=dict)
    critical_findings: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    evaluation_summary: str = ""
    latency_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    cost_status: str = "unavailable"
    attempt_history: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None


__all__ = [
    "DimensionName",
    "DimensionScore",
    "JudgeEvaluationOutput",
    "JudgeEvaluationState",
    "JudgeVerdict",
]
