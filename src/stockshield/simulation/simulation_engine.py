"""Deterministic Simulation Engine for StockShield 2.0.

Calculates hypothetical prices, adjusted volatility, news sentiment mapping,
and deterministic scenario-specific institutional risk ratings without modifying
the original baseline Blackboard state.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from stockshield.blackboard.models import StockShieldBlackboard
from stockshield.simulation.models import (
    BaselineMetrics,
    CustomScenarioInput,
    ScenarioComparison,
    ScenarioResult,
    SimulatedMetrics,
    TechnicalTrendShock,
)


def compute_baseline_metrics(state: StockShieldBlackboard) -> Tuple[BaselineMetrics, float, Dict[str, Any]]:
    """Extract and calculate ground-truth baseline market and risk metrics.

    Returns:
        (baseline_metrics, historical_peak_price, current_indicators_dict)
    """
    market = state.market_data
    risk = state.risk_findings
    tech = state.technical_findings
    news = state.news_sentiment

    closes = [
        float(b.close)
        for b in market.bars
        if b.close is not None and not math.isnan(float(b.close)) and float(b.close) > 0
    ]

    if not closes:
        # Fallback if market bars missing
        stock_price = 100.0
        historical_peak = 100.0
        volatility_pct = 20.0
    else:
        stock_price = float(closes[-1])
        historical_peak = float(max(closes))

        if len(closes) >= 10:
            returns = np.diff(np.log(closes))
            daily_vol = float(np.std(returns))
            volatility_pct = round(daily_vol * math.sqrt(252) * 100.0, 2)
        else:
            volatility_pct = 20.0

    # News sentiment baseline
    news_score = round(news.sentiment_score, 2) if news.sentiment_score is not None else 0.0
    news_label = news.overall_sentiment if news.overall_sentiment else "NEUTRAL"

    # Technical baseline
    tech_signal = tech.signal if tech.signal else "NEUTRAL"
    inds_dict: Dict[str, Any] = tech.indicators.model_dump() if tech.indicators else {}

    # Risk baseline
    comp_score = round(risk.composite_risk_score, 3) if risk.composite_risk_score > 0 else 0.35
    risk_lvl = risk.overall_risk_level if risk.overall_risk_level else "MODERATE"
    rec = risk.recommendation if risk.recommendation else "APPROVED_WITH_CAUTION"

    baseline = BaselineMetrics(
        stock_price=round(stock_price, 2),
        volatility_pct=volatility_pct,
        news_sentiment_score=news_score,
        news_sentiment_label=news_label,
        technical_signal=tech_signal,
        composite_risk_score=comp_score,
        risk_level=risk_lvl,
        recommendation=rec,
    )
    return baseline, historical_peak, inds_dict


class DeterministicSimulationEngine:
    """Core simulation engine performing deterministic stress calculations."""

    def simulate(
        self,
        scenario_input: CustomScenarioInput,
        baseline: BaselineMetrics,
        historical_peak: float,
        current_indicators: Optional[Dict[str, Any]] = None,
    ) -> ScenarioResult:
        """Run a single deterministic stress scenario simulation against the baseline."""
        assumptions: List[str] = []
        warnings: List[str] = []

        # -------------------------------------------------------------
        # 1. Price Shock Calculation
        # -------------------------------------------------------------
        # Formula: scenario_price = current_price * (1 + price_shock_pct / 100)
        p_shock = scenario_input.price_shock_pct
        sim_price = round(baseline.stock_price * (1.0 + p_shock / 100.0), 2)
        sim_price = max(0.01, sim_price)  # Bounds safety

        abs_price_change = round(sim_price - baseline.stock_price, 2)
        pct_price_change = round(p_shock, 2)
        assumptions.append(f"Instantaneous price shock of {pct_price_change:+.2f}% applied.")

        # Portfolio Impact
        portfolio_impact: Optional[float] = None
        if scenario_input.portfolio_exposure_shares is not None:
            portfolio_impact = round(abs_price_change * scenario_input.portfolio_exposure_shares, 2)
            assumptions.append(f"Portfolio exposure evaluated for {scenario_input.portfolio_exposure_shares:,.0f} shares.")
        elif scenario_input.portfolio_exposure_value is not None:
            portfolio_impact = round(scenario_input.portfolio_exposure_value * (pct_price_change / 100.0), 2)
            assumptions.append(f"Portfolio exposure evaluated for capital of {scenario_input.portfolio_exposure_value:,.2f}.")

        # -------------------------------------------------------------
        # 2. Volatility Shock Calculation
        # -------------------------------------------------------------
        if scenario_input.volatility_multiplier is not None:
            mult = scenario_input.volatility_multiplier
            sim_vol = round(baseline.volatility_pct * mult, 2)
            vol_change_pct = round((mult - 1.0) * 100.0, 2)
            assumptions.append(f"Volatility scaled by multiplier {mult:.2f}x.")
        else:
            v_shock = scenario_input.volatility_shock_pct
            sim_vol = round(baseline.volatility_pct * (1.0 + v_shock / 100.0), 2)
            vol_change_pct = round(v_shock, 2)
            if abs(v_shock) > 0.001:
                assumptions.append(f"Volatility shifted by {v_shock:+.2f}%.")

        sim_vol = max(0.1, sim_vol)

        # -------------------------------------------------------------
        # 3. News Sentiment Shock
        # -------------------------------------------------------------
        if scenario_input.sentiment_score is not None:
            sim_sent_score = round(scenario_input.sentiment_score, 2)
            assumptions.append(f"Hypothetical media sentiment score fixed at {sim_sent_score:+.2f}.")
        else:
            sim_sent_score = baseline.news_sentiment_score

        if sim_sent_score >= 0.25:
            sim_sent_label = "POSITIVE"
        elif sim_sent_score <= -0.25:
            sim_sent_label = "NEGATIVE"
        else:
            sim_sent_label = "NEUTRAL"

        # -------------------------------------------------------------
        # 4. Technical Trend Shock
        # -------------------------------------------------------------
        t_trend = scenario_input.technical_trend
        if t_trend == TechnicalTrendShock.BULLISH_RECOVERY:
            sim_tech_signal = "BULLISH"
            assumptions.append("Technical posture assumes bullish breakout and momentum recovery.")
        elif t_trend in [
            TechnicalTrendShock.NEUTRAL_TO_BEARISH,
            TechnicalTrendShock.BREAK_BELOW_SMA20,
            TechnicalTrendShock.BREAK_BELOW_SMA50,
            TechnicalTrendShock.BREAK_BELOW_SMA200,
        ]:
            sim_tech_signal = "BEARISH"
            assumptions.append(f"Technical trend assumes bearish breakdown ({t_trend.value}).")
        elif t_trend == TechnicalTrendShock.BULLISH_TO_NEUTRAL:
            sim_tech_signal = "NEUTRAL"
            assumptions.append("Technical posture assumes momentum decay into neutral consolidation.")
        else:
            sim_tech_signal = baseline.technical_signal

        # -------------------------------------------------------------
        # 5. Deterministic Hypothetical Risk Engine Calculation
        # (Reuses the exact 7 institutional gates from DeterministicRiskEngine)
        # -------------------------------------------------------------
        gate_scores: List[float] = []

        # Gate 1: Data Sufficiency (retains baseline validity)
        gate_scores.append(0.0)

        # Gate 2: Price Validity
        if sim_price <= 0:
            gate_scores.append(1.0)
            warnings.append("Hypothetical price breaches non-positive numerical boundary.")
        else:
            gate_scores.append(0.0)

        # Gate 3: Maximum Drawdown & Volatility Stress
        peak = max(historical_peak, sim_price)
        sim_drawdown = (peak - sim_price) / peak if peak > 0 else 0.0
        if sim_drawdown > 0.35 or sim_vol >= baseline.volatility_pct * 1.8:
            gate_scores.append(0.80)
            warnings.append(
                f"Severe simulated drawdown/volatility hazard: drawdown {sim_drawdown * 100:.1f}%, vol {sim_vol:.1f}%."
            )
        elif sim_drawdown > 0.20 or sim_vol >= baseline.volatility_pct * 1.3:
            gate_scores.append(0.40)
            warnings.append(f"Elevated simulated drawdown ({sim_drawdown * 100:.1f}%) and volatility ({sim_vol:.1f}%).")
        else:
            gate_scores.append(0.10)

        # Gate 4: Technical Indicators & Trend Sanity
        if t_trend == TechnicalTrendShock.BREAK_BELOW_SMA200:
            gate_scores.append(0.70)
            warnings.append("Critical trend breakdown: Price breaches below long-term SMA-200 support.")
        elif t_trend in [TechnicalTrendShock.NEUTRAL_TO_BEARISH, TechnicalTrendShock.BREAK_BELOW_SMA50]:
            gate_scores.append(0.50)
            warnings.append("Bearish technical deterioration below intermediate moving average.")
        elif t_trend in [TechnicalTrendShock.BULLISH_TO_NEUTRAL, TechnicalTrendShock.BREAK_BELOW_SMA20]:
            gate_scores.append(0.35)
        elif t_trend == TechnicalTrendShock.BULLISH_RECOVERY:
            gate_scores.append(0.10)
        else:
            gate_scores.append(0.15 if sim_tech_signal == "BULLISH" else 0.35)

        # Gate 5: Fundamental Solvency (retains baseline balance sheet score)
        gate_scores.append(0.05)

        # Gate 6: News Sentiment Risk (Exact Gate 6 formulas)
        if sim_sent_score <= -0.80:
            gate_scores.append(0.80)
            warnings.append(f"Severe media headline crisis simulated (sentiment score {sim_sent_score:+.2f}).")
        elif sim_sent_score <= -0.25:
            gate_scores.append(0.65)
            warnings.append(f"Adverse media sentiment simulated (score {sim_sent_score:+.2f}).")
        elif sim_sent_score >= 0.25:
            gate_scores.append(0.05)
        else:
            gate_scores.append(0.20)

        # Gate 7: Predictive Price / Forward Stress Trajectory
        if pct_price_change <= -8.0:
            gate_scores.append(0.75)
            warnings.append(f"Severe price shock scenario ({pct_price_change:+.1f}%) imposes high capital risk.")
        elif pct_price_change <= -3.0:
            gate_scores.append(0.50)
        elif pct_price_change >= 3.0:
            gate_scores.append(0.05)
        else:
            gate_scores.append(0.15)

        # Compute Scenario Composite Risk Score
        # In institutional stress testing, tail-weighted scoring blends average baseline risk
        # with peak stressed dimensions so data validity checks do not dilute severe tail hazards.
        mean_score = sum(gate_scores) / len(gate_scores)
        max_score = max(gate_scores)
        sorted_scores = sorted(gate_scores, reverse=True)
        top3_mean = sum(sorted_scores[:3]) / 3.0

        if top3_mean >= 0.65:
            scenario_risk_score = round(0.25 * mean_score + 0.75 * top3_mean, 3)
        elif max_score >= 0.50:
            scenario_risk_score = round(0.50 * mean_score + 0.50 * max_score, 3)
        else:
            scenario_risk_score = round(mean_score, 3)

        # Assign Scenario Risk Category & Recommendation
        has_critical_gate = any(s >= 0.95 for s in gate_scores)
        if scenario_risk_score >= 0.65 or has_critical_gate:
            scenario_risk_level = "HIGH" if scenario_risk_score < 0.85 else "CRITICAL"
            scenario_recommendation = "REJECTED_HIGH_RISK"
        elif scenario_risk_score >= 0.35 or warnings:
            scenario_risk_level = "MODERATE"
            scenario_recommendation = "APPROVED_WITH_CAUTION"
        else:
            scenario_risk_level = "LOW"
            scenario_recommendation = "APPROVED"

        # -------------------------------------------------------------
        # 6. Baseline vs. Scenario Comparison
        # -------------------------------------------------------------
        risk_score_delta = round(scenario_risk_score - baseline.composite_risk_score, 3)
        risk_level_changed = scenario_risk_level != baseline.risk_level
        recommendation_changed = scenario_recommendation != baseline.recommendation
        recommendation_flip_direction = (
            f"{baseline.recommendation} -> {scenario_recommendation}" if recommendation_changed else None
        )

        material_risk_increase = (
            risk_score_delta >= 0.15
            or (scenario_recommendation == "REJECTED_HIGH_RISK" and baseline.recommendation != "REJECTED_HIGH_RISK")
            or (scenario_risk_level in ["HIGH", "CRITICAL"] and baseline.risk_level in ["LOW", "MODERATE"])
        )

        if material_risk_increase:
            explanation = (
                f"Scenario causes MATERIAL RISK INCREASE (+{risk_score_delta:.3f} risk score). "
                f"Recommendation shifts: {recommendation_flip_direction or scenario_recommendation}."
            )
        elif risk_score_delta < -0.10:
            explanation = (
                f"Scenario demonstrates RISK RELIEF ({risk_score_delta:.3f} risk score). "
                f"Favorable conditions lower capital risk to {scenario_risk_level}."
            )
        else:
            explanation = (
                f"Scenario produces modest risk drift ({risk_score_delta:+.3f} score). "
                f"Recommendation remains {scenario_recommendation}."
            )

        simulated_metrics = SimulatedMetrics(
            hypothetical_price=sim_price,
            absolute_price_change=abs_price_change,
            percentage_price_change=pct_price_change,
            portfolio_value_impact=portfolio_impact,
            hypothetical_volatility_pct=sim_vol,
            volatility_change_pct=vol_change_pct,
            hypothetical_sentiment_score=sim_sent_score,
            hypothetical_sentiment_label=sim_sent_label,
            hypothetical_technical_signal=sim_tech_signal,
            scenario_risk_score=scenario_risk_score,
            scenario_risk_level=scenario_risk_level,
            scenario_recommendation=scenario_recommendation,
        )

        comparison = ScenarioComparison(
            risk_score_delta=risk_score_delta,
            risk_level_changed=risk_level_changed,
            recommendation_changed=recommendation_changed,
            recommendation_flip_direction=recommendation_flip_direction,
            material_risk_increase=material_risk_increase,
            explanation=explanation,
        )

        return ScenarioResult(
            scenario_name=scenario_input.name,
            category=scenario_input.category,
            description=scenario_input.description or f"Stress simulation: {scenario_input.name}",
            assumptions=assumptions,
            warnings=warnings,
            inputs=scenario_input,
            baseline=baseline,
            simulated=simulated_metrics,
            comparison=comparison,
        )
