"""Deterministic Stub LLM for reproducible, zero-cost offline evaluations."""

from typing import Any, Dict, Tuple

from stockshield.blackboard.models import StockShieldBlackboard
from stockshield.llm.cost_estimator import CostEstimate, compute_cost


class DeterministicStubLLM:
    """Interchangeable Stub LLM adapter.

    Generates deterministic, schema-compliant financial summaries without
    pretending to perform live neural reasoning. Clearly tagged for transparency.
    """

    def __init__(self, model_name: str = "deterministic-stub-v1"):
        self.model_name = model_name

    def generate_report(self, state: StockShieldBlackboard) -> Tuple[str, str, Dict[str, Any], CostEstimate]:
        """Synthesize executive summary, markdown report, and structured JSON from state."""
        ticker = state.ticker
        tech = state.technical_findings
        risk = state.risk_findings
        market = state.market_data

        # Construct deterministic prompt representation
        prompt_repr = (
            f"Generate report for {ticker}. User request: '{state.user_prompt}'. "
            f"Market source: {market.source}, bars: {market.bar_count}. "
            f"Technical signal: {tech.signal} (confidence {tech.signal_confidence}), "
            f"Indicators: {tech.indicators.model_dump()}. "
            f"Risk: {risk.overall_risk_level}, recommendation: {risk.recommendation}, "
            f"Composite score: {risk.composite_risk_score}."
        )

        executive_summary = (
            f"[DETERMINISTIC STUB EVALUATION] Institutional StockShield 2.0 Risk Assessment for {ticker}. "
            f"Technical momentum is {tech.signal} with {int(tech.signal_confidence * 100)}% algorithmic confidence. "
            f"Deterministic risk governance assigns an overall risk grade of {risk.overall_risk_level} "
            f"with recommendation '{risk.recommendation}' (Composite Risk Score: {risk.composite_risk_score:.2f})."
        )

        warnings_md = "\n".join(f"- ⚠️ {w}" for w in risk.warnings) if risk.warnings else "- None noted."
        reasons_md = "\n".join(f"- {r}" for r in risk.reasons) if risk.reasons else "- Standard parameters met."

        markdown_content = f"""# StockShield 2.0 Equity Analysis Report: {ticker}

**Run ID:** `{state.run_id}`
**Trace ID:** `{state.trace_id}`
**Evaluation Mode:** `{state.workflow_mode}` (Model: `{self.model_name}`)
**Generated At (UTC):** `{state.created_at_utc}`

---

## 1. Executive Summary
{executive_summary}

---

## 2. Market Data Verification & Provenance
- **Data Source:** `{market.source}` (Exchange: {market.exchange}, Currency: {market.currency})
- **Historical Bars Analyzed:** {market.bar_count} trading sessions
- **Window Range:** {market.start_date} to {market.end_date}
- **Quality Status:** `{market.data_quality_status}`

---

## 3. Google ADK Technical Quantitative Findings
- **Composite Signal:** `{tech.signal}` (Confidence: {tech.signal_confidence:.2f})
- **SMA-20:** `{tech.indicators.sma_20}` | **SMA-50:** `{tech.indicators.sma_50}` | **SMA-200:** `{tech.indicators.sma_200}`
- **EMA-12:** `{tech.indicators.ema_12}` | **EMA-26:** `{tech.indicators.ema_26}`
- **RSI (14-period Wilder):** `{tech.indicators.rsi_14}`
- **MACD Line:** `{tech.indicators.macd_line}` | **Signal:** `{tech.indicators.macd_signal}` | **Hist:** `{tech.indicators.macd_hist}`
- **Bollinger Bands:** Upper `{tech.indicators.bb_upper}`, Mid `{tech.indicators.bb_middle}`, Lower `{tech.indicators.bb_lower}` (BW: {tech.indicators.bb_bandwidth}%)
- **ATR (14-period):** `{tech.indicators.atr_14}`

---

## 4. Deterministic Risk Intelligence Review
- **Overall Risk Rating:** `{risk.overall_risk_level}`
- **Composite Risk Score:** `{risk.composite_risk_score:.3f}` (Scale 0.0 safe - 1.0 critical)
- **Institutional Recommendation:** `{risk.recommendation}`

### Actionable Warnings & Governance Triggers:
{warnings_md}

### Assessment Rationales:
{reasons_md}

---
*Notice: Generated strictly from verified offline fixtures and deterministic math. Zero hallucinated price points.*
"""

        structured_json = {
            "run_id": state.run_id,
            "trace_id": state.trace_id,
            "ticker": ticker,
            "timestamp_utc": state.created_at_utc,
            "market_data_summary": {
                "source": market.source,
                "bar_count": market.bar_count,
                "data_quality": market.data_quality_status,
            },
            "technical_findings": {
                "signal": tech.signal,
                "confidence": tech.signal_confidence,
                "indicators": tech.indicators.model_dump(),
            },
            "risk_review": {
                "overall_risk_level": risk.overall_risk_level,
                "composite_risk_score": risk.composite_risk_score,
                "recommendation": risk.recommendation,
                "warnings": risk.warnings,
                "reasons": risk.reasons,
            },
            "compliance_attestation": {
                "stub_mode": True,
                "zero_hallucination_guarantee": True,
            },
        }

        cost_est = compute_cost(
            input_text=prompt_repr,
            output_text=markdown_content,
            model_name=self.model_name,
            is_stub=True,
        )

        return executive_summary, markdown_content, structured_json, cost_est
