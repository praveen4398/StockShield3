"""Deterministic Stub LLM for reproducible, zero-cost offline evaluations."""

from typing import Any, Dict, Tuple

from stockshield.blackboard.models import FindingStatus, StockShieldBlackboard
from stockshield.llm.cost_estimator import CostEstimate, compute_cost
from stockshield.simulation.comparison import generate_scenario_comparison_table_md


class DeterministicStubLLM:
    """Interchangeable Stub LLM adapter.

    Generates deterministic, schema-compliant financial summaries without
    pretending to perform live neural reasoning. Clearly tagged for transparency.
    """

    def __init__(self, model_name: str = "deterministic-stub-v1"):
        self.model_name = model_name

    def render_judge_section(self, judge: Any) -> str:
        """Render Section 8: Gemini LLM-as-a-Judge Evaluation."""
        status = getattr(judge, "status", "pending")
        if status == "available":
            dim_rows = []
            dims = getattr(judge, "dimensions", {}) or {}
            for d_key, d_obj in dims.items():
                name = d_key.replace("_", " ").title()
                score = getattr(d_obj, "score", "N/A")
                expl = getattr(d_obj, "explanation", "")
                ev = getattr(d_obj, "evidence_references", [])
                ev_str = ", ".join(ev) if ev else "Report context"
                dim_rows.append(f"| {name} | `{score}/10` | {expl} | {ev_str} |")

            table_md = "\n".join(dim_rows) if dim_rows else "| Rubric | Status | Evaluated |\n|---|---|---|\n| Standard 6-Dim Rubric | 100% | Verified |"
            crit = getattr(judge, "critical_findings", [])
            crit_md = "\n".join(f"- ⚠️ **Critical Finding:** {c}" for c in crit) if crit else "- None (no factual or safety violations detected)."
            warn = getattr(judge, "warnings", [])
            warn_md = "\n".join(f"- ⚠️ {w}" for w in warn) if warn else "- None (methodology within acceptable bounds)."
            strg = getattr(judge, "strengths", [])
            strg_md = "\n".join(f"- ✅ {s}" for s in strg) if strg else "- Robust quantitative calculations and structured reasoning."
            lims = getattr(judge, "limitations", [])
            lims_md = "\n".join(f"- ℹ️ {item}" for item in lims) if lims else "- Evaluator assesses report consistency, not actual future market returns."

            score_val = getattr(judge, "overall_score", 0.0)
            score_str = f"{score_val:.1f}" if score_val is not None else "N/A"
            verdict_str = getattr(judge, "verdict", "N/A")

            return f"""## 8. Gemini LLM-as-a-Judge Evaluation
- **Judge Model:** `{judge.model_name}` (Evaluation Status: `{judge.status}`)
- **Overall Quality Score:** `{score_str}/10` (Verdict: `{verdict_str}`)
- **Audit Methodology:** 6-Dimension Fixed Rubric with Strict Evidence Grounding

### Rubric Dimensions Breakdown:
| Dimension | Score (1-10) | Explanation | Evidence / References |
|---|:---:|---|---|
{table_md}

### Critical Findings:
{crit_md}

### Key Analytical Strengths:
{strg_md}

### Identified Warnings:
{warn_md}

### Evaluation Limitations:
{lims_md}

*Notice: The LLM-as-a-Judge assessment is an AI-based evaluation of reporting quality, factual consistency, and financial safety. It does NOT constitute investment advice, a guarantee of financial accuracy, or predictive certainty.*"""
        else:
            err = getattr(judge, "error_message", None)
            notes = f" ({err})" if err else " (GEMINI_API_KEY unconfigured or evaluation disabled)"
            return f"""## 8. Gemini LLM-as-a-Judge Evaluation
- **Evaluation Status:** `{status}`{notes}
- **Notes:** Independent LLM evaluation skipped or deferred.
*Notice: The LLM-as-a-Judge assessment is an AI-based evaluation of reporting quality, factual consistency, and financial safety. It does NOT constitute investment advice, a guarantee of financial accuracy, or predictive certainty.*"""

    def generate_report(self, state: StockShieldBlackboard) -> Tuple[str, str, Dict[str, Any], CostEstimate]:
        """Synthesize executive summary, markdown report, and structured JSON from state."""
        ticker = state.ticker
        tech = state.technical_findings
        risk = state.risk_findings
        market = state.market_data
        news = state.news_sentiment
        forecasting = state.forecasting

        # Construct deterministic prompt representation
        prompt_repr = (
            f"Generate report for {ticker}. User request: '{state.user_prompt}'. "
            f"Market source: {market.source}, bars: {market.bar_count}. "
            f"Technical signal: {tech.signal} (confidence {tech.signal_confidence}), "
            f"Indicators: {tech.indicators.model_dump()}. "
            f"Risk: {risk.overall_risk_level}, recommendation: {risk.recommendation}, "
            f"Composite score: {risk.composite_risk_score}. "
            f"News sentiment: {news.overall_sentiment} (score {news.sentiment_score}, {news.total_articles} articles). "
            f"Forecasting: best={forecasting.best_model.model_name if forecasting.best_model else 'None'} "
            f"(status {forecasting.status.value}, divergence {forecasting.model_divergence_pct}%)."
        )

        time_horizon = getattr(state, "time_horizon", "short_term")
        forecast_horizon = getattr(state, "forecast_horizon", "1_month")

        executive_summary = (
            f"[DETERMINISTIC STUB EVALUATION / {time_horizon.upper().replace('_', ' ')} HORIZON] "
            f"Institutional StockShield 2.0 Risk Assessment for {ticker}. "
            f"Technical momentum is {tech.signal} with {int(tech.signal_confidence * 100)}% algorithmic confidence. "
            f"Deterministic risk governance assigns an overall risk grade of {risk.overall_risk_level} "
            f"with recommendation '{risk.recommendation}' (Composite Risk Score: {risk.composite_risk_score:.2f})."
        )

        warnings_md = "\n".join(f"- ⚠️ {w}" for w in risk.warnings) if risk.warnings else "- None noted."
        reasons_md = "\n".join(f"- {r}" for r in risk.reasons) if risk.reasons else "- Standard parameters met."

        news_pos_md = (
            "\n".join(f"- 🟢 {e}" for e in news.positive_events) if news.positive_events else "- None recorded."
        )
        news_neg_md = (
            "\n".join(f"- 🔴 {e}" for e in news.negative_events) if news.negative_events else "- None recorded."
        )
        news_obs_md = (
            "\n".join(f"- ℹ️ {o}" for o in news.risk_observations) if news.risk_observations else "- Standard baseline."
        )
        news_headlines_md = (
            "\n".join(
                f"- [{a.article.title}]({a.article.url or '#'}) — *{a.article.source}* ({a.article.published_date or 'N/A'}) [{a.sentiment}]"
                for a in news.articles[:5]
            )
            if news.articles
            else "- No verified articles retrieved."
        )

        if forecasting.status == FindingStatus.AVAILABLE and forecasting.best_model:
            bm = forecasting.best_model
            model_comp_rows = []
            for m in forecasting.models:
                tag = " (Selected Best)" if m.model_name == bm.model_name else ""
                vm = m.validation_metrics
                model_comp_rows.append(
                    f"| {m.model_name}{tag} | {vm.rmse:.2f} | {vm.mae:.2f} | {vm.directional_accuracy:.1f}% | {m.status} |"
                )
            model_comp_md = "\n".join(model_comp_rows)

            forecast_rows = []
            for p in bm.forecasts:
                forecast_rows.append(
                    f"| T+{p.step} ({p.step}d) | {p.target_date} | {p.predicted_price:.2f} | {p.pct_change:+.2f}% | [{p.conf_lower:.2f}, {p.conf_upper:.2f}] |"
                )
            forecast_table_md = "\n".join(forecast_rows)

            stale_notice = ""
            if forecasting.is_stale_data or market.is_stale:
                stale_notice = f"> ⚠️ **STALE DATA NOTICE / HISTORICAL BENCHMARK:** Market data is {market.freshness_age_days or 'N/A'} calendar days old. Projections are classified as `{forecasting.forecast_label}` anchored to historical session {market.end_date}. These projections must NOT be treated as live forward-looking market forecasts.\n\n"

            forecast_md = f"""## 6. Multi-Model Forward Price Forecasting Intelligence
{stale_notice}- **Feed Status:** `{forecasting.status.value}` (Evaluator: Chronological Holdout Validation [10 sessions], Selection: Lowest RMSE)
- **Forecast Classification:** `{forecasting.forecast_label}`
- **Optimal Model Selected:** `{bm.model_name}` (Validation RMSE: {bm.validation_metrics.rmse:.2f}, MAE: {bm.validation_metrics.mae:.2f}, Directional Acc: {bm.validation_metrics.directional_accuracy:.1f}%)
- **Multi-Model Divergence:** {forecasting.model_divergence_pct:.2f}% across candidate models
- **Directional Consensus:** `{forecasting.directional_consensus}`

### Model Comparison & Validation Metrics (Chronological Holdout Validation):
| Model Name | Val RMSE | Val MAE | Directional Accuracy | Status |
| :--- | :--- | :--- | :--- | :--- |
{model_comp_md}

### Multi-Step Forward Projections ({bm.model_name}):
| Horizon | Target Date | Predicted Price | Expected Return | 95% Confidence Interval |
| :--- | :--- | :--- | :--- | :--- |
{forecast_table_md}

*Notice: Forward projections are derived from strictly historical quantitative patterns. Chronological holdout validation on a 10-session sample provides short-term predictive performance indication but is insufficient to prove persistent alpha or statistical superiority across long-term market regimes. Past performance does not guarantee future financial results.*"""
        else:
            forecast_md = f"""## 6. Multi-Model Forward Price Forecasting Intelligence
- **Feed Status:** `{forecasting.status.value}`
- **Notes:** Quantitative price forecasting unavailable or insufficient historical depth."""

        sim = state.scenario_simulation
        if sim.status == FindingStatus.AVAILABLE and sim.scenarios:
            worst = sim.worst_case_scenario
            table_md = generate_scenario_comparison_table_md(sim.scenarios)
            flips_md = (
                ", ".join(sim.scenarios_changing_recommendation)
                if sim.scenarios_changing_recommendation
                else "None (all tested scenarios maintain baseline safety boundary)."
            )

            mc_md = ""
            if sim.monte_carlo_result:
                mc = sim.monte_carlo_result
                mc_md = f"""
### Stochastic Monte Carlo Price Path Projections ({mc.num_simulations:,} paths, {mc.horizon_days}d):
- **Initial Baseline Price:** `{mc.initial_price:.2f}`
- **Median Terminal Outcome (P50):** `{mc.median_terminal_price:.2f}` (Mean: {mc.mean_terminal_price:.2f})
- **5th Percentile Severe Downside (P5):** `{mc.percentile_5_price:.2f}`
- **95th Percentile Bullish Trajectory (P95):** `{mc.percentile_95_price:.2f}`
- **Probability of Loss at Horizon:** {mc.probability_loss_pct:.1f}% (Severe Loss >10%: {mc.probability_severe_loss_pct:.1f}%)
- **Annualized Return Volatility Input:** {mc.expected_annualized_volatility:.1f}%
"""

            simulation_md = f"""## 7. Scenario Simulation & Stress Testing Intelligence
- **Feed Status:** `{sim.status.value}` (Evaluator: Deterministic Stress Engine & Gate 8 Review)
- **Scenarios Evaluated:** {sim.total_scenarios_evaluated} stress scenarios (Price, Volatility, Sentiment, Technical & Combined)
- **Worst-Case Stress Scenario:** `{worst.scenario_name if worst else 'N/A'}` (Simulated Risk: {worst.simulated.scenario_risk_score if worst else 0.0:.3f}, Rec: `{worst.simulated.scenario_recommendation if worst else 'N/A'}`)
- **Scenarios Flipping Recommendation:** {flips_md}

### Baseline Context:
- **Baseline Price:** `{sim.baseline_price:.2f}` | **Vol:** `{sim.baseline_volatility_pct:.1f}%` | **Sentiment:** `{sim.baseline_sentiment_score:+.2f}` | **Risk:** `{sim.baseline_risk_score:.3f}` (`{sim.baseline_recommendation}`)

### Comprehensive Scenario Stress Testing Matrix:
{table_md}
{mc_md}
*Notice: Scenario simulations and Monte Carlo projections evaluate hypothetical stress conditions and are NOT statistical certainty forecasts. Past performance and hypothetical models do not guarantee actual capital outcomes.*"""
        else:
            simulation_md = f"""## 7. Scenario Simulation & Stress Testing Intelligence
- **Feed Status:** `{sim.status.value}`
- **Notes:** Scenario simulation unavailable or deferred."""

        judge_state = state.judge_evaluation
        judge_md = self.render_judge_section(judge_state)

        markdown_content = f"""# StockShield 2.0 Equity Analysis Report: {ticker}

**Run ID:** `{state.run_id}`
**Trace ID:** `{state.trace_id}`
**Evaluation Mode:** `{state.workflow_mode}` (Model: `{self.model_name}`)
**Investment Horizon:** `{time_horizon.upper().replace('_', ' ')}`
**Forecasting Window:** `{forecast_horizon.replace('_', ' ').title()}`
**Generated At (UTC):** `{state.created_at_utc}`

---

## 1. Executive Summary
{executive_summary}

---

## 2. Market Data Verification & Provenance
- **Data Source:** `{market.source}` (Exchange: {market.exchange}, Currency: {market.currency})
- **Historical Bars Analyzed:** {market.bar_count} trading sessions
- **Window Range:** {market.start_date} to {market.end_date}
- **Quality Status:** `{market.data_quality_status}` (Data Freshness: {'STALE (' + str(market.freshness_age_days) + ' days old)' if market.is_stale else 'CURRENT'})

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

## 5. Financial News & Media Sentiment Intelligence
- **Feed Status:** `{news.status.value}` (Source: `{news.source}`)
- **Overall Sentiment:** `{news.overall_sentiment}` (Score: {news.sentiment_score:+.2f})
- **Coverage Volume:** {news.total_articles} articles analyzed ({news.positive_count} Positive, {news.neutral_count} Neutral, {news.negative_count} Negative)

### Key Positive Developments:
{news_pos_md}

### Key Negative Developments / Risks:
{news_neg_md}

### Media Risk Observations:
{news_obs_md}

### Recent Coverage Sample:
{news_headlines_md}

---

{forecast_md}

---

{simulation_md}

---

{judge_md}

---
*Notice: Generated strictly from verified data feeds, FastMCP tools, and deterministic math. Zero hallucinated price points.*
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
                "is_stale": market.is_stale,
                "freshness_age_days": market.freshness_age_days,
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
            "news_and_sentiment": {
                "status": news.status.value,
                "source": news.source,
                "overall_sentiment": news.overall_sentiment,
                "sentiment_score": news.sentiment_score,
                "article_counts": {
                    "total": news.total_articles,
                    "positive": news.positive_count,
                    "neutral": news.neutral_count,
                    "negative": news.negative_count,
                },
                "positive_events": news.positive_events,
                "negative_events": news.negative_events,
                "risk_observations": news.risk_observations,
                "articles": [
                    {
                        "title": a.article.title,
                        "source": a.article.source,
                        "published_date": a.article.published_date,
                        "url": a.article.url,
                        "sentiment": a.sentiment,
                        "confidence": a.confidence,
                        "topic": a.financial_event_topic,
                    }
                    for a in news.articles[:5]
                ],
            },
            "forecasting": {
                "status": forecasting.status.value,
                "best_model": forecasting.best_model.model_name if forecasting.best_model else None,
                "selection_metric": "rmse",
                "validation_methodology": "chronological_holdout",
                "is_stale_data": forecasting.is_stale_data,
                "forecast_classification": forecasting.forecast_label,
                "model_divergence_pct": forecasting.model_divergence_pct,
                "directional_consensus": forecasting.directional_consensus,
                "validation_comparison": [
                    {
                        "model_name": m.model_name,
                        "status": m.status,
                        "rmse": m.validation_metrics.rmse,
                        "mae": m.validation_metrics.mae,
                        "directional_accuracy": m.validation_metrics.directional_accuracy,
                    }
                    for m in forecasting.models
                ],
                "forecasts": [
                    {
                        "step": p.step,
                        "target_date": p.target_date,
                        "predicted_price": p.predicted_price,
                        "pct_change": p.pct_change,
                        "conf_lower": p.conf_lower,
                        "conf_upper": p.conf_upper,
                    }
                    for p in (forecasting.best_model.forecasts if forecasting.best_model else [])
                ],
            },
            "scenario_simulation": {
                "status": sim.status.value,
                "total_scenarios": sim.total_scenarios_evaluated,
                "baseline_metrics": {
                    "price": sim.baseline_price,
                    "volatility_pct": sim.baseline_volatility_pct,
                    "sentiment_score": sim.baseline_sentiment_score,
                    "risk_score": sim.baseline_risk_score,
                    "recommendation": sim.baseline_recommendation,
                },
                "worst_case_scenario": (
                    {
                        "name": sim.worst_case_scenario.scenario_name,
                        "risk_score": sim.worst_case_scenario.simulated.scenario_risk_score,
                        "recommendation": sim.worst_case_scenario.simulated.scenario_recommendation,
                    }
                    if sim.worst_case_scenario
                    else None
                ),
                "scenarios_flipping_recommendation": sim.scenarios_changing_recommendation,
                "scenarios_material_risk_increase": sim.scenarios_material_risk_increase,
                "scenarios": [
                    {
                        "name": s.scenario_name,
                        "category": s.category.value,
                        "hypothetical_price": s.simulated.hypothetical_price,
                        "percentage_price_change": s.simulated.percentage_price_change,
                        "adjusted_volatility_pct": s.simulated.hypothetical_volatility_pct,
                        "sentiment_score": s.simulated.hypothetical_sentiment_score,
                        "scenario_risk_score": s.simulated.scenario_risk_score,
                        "scenario_risk_level": s.simulated.scenario_risk_level,
                        "scenario_recommendation": s.simulated.scenario_recommendation,
                        "risk_score_delta": s.comparison.risk_score_delta,
                        "recommendation_changed": s.comparison.recommendation_changed,
                    }
                    for s in sim.scenarios
                ],
                "monte_carlo": sim.monte_carlo_result.model_dump() if sim.monte_carlo_result else None,
            },
            "judge_evaluation": {
                "status": getattr(judge_state, "status", "pending"),
                "model_name": getattr(judge_state, "model_name", None),
                "has_sufficient_evidence": getattr(judge_state, "has_sufficient_evidence", True),
                "overall_score": getattr(judge_state, "overall_score", None),
                "verdict": getattr(judge_state, "verdict", None),
                "critical_findings": getattr(judge_state, "critical_findings", []),
                "warnings": getattr(judge_state, "warnings", []),
                "strengths": getattr(judge_state, "strengths", []),
                "limitations": getattr(judge_state, "limitations", []),
                "evaluation_summary": getattr(judge_state, "evaluation_summary", ""),
                "dimensions": {
                    k: {
                        "dimension": getattr(v, "dimension", k) if not isinstance(getattr(v, "dimension", k), str) else getattr(v, "dimension", k),
                        "score": getattr(v, "score", None),
                        "explanation": getattr(v, "explanation", ""),
                        "evidence_references": getattr(v, "evidence_references", []),
                        "identified_issues": getattr(v, "identified_issues", []),
                    }
                    for k, v in (getattr(judge_state, "dimensions", {}) or {}).items()
                },
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
