"""Deterministic Risk Intelligence Engine for StockShield 2.0.

Consumes findings directly from the Blackboard. Evaluates data sufficiency,
volatility, maximum drawdown, numerical sanity, and conflicting signals.
Deterministic rule enforcement guarantees no LLM can override safety boundaries.
"""

import time
from typing import Any, Dict, List

from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus


class DeterministicRiskEngine:
    """Institutional deterministic risk review step."""

    def __init__(self, name: str = "DeterministicRiskEngine"):
        self.name = name

    async def execute(self, blackboard: BlackboardManager) -> Dict[str, Any]:
        start_time = time.perf_counter()
        await blackboard.log_event(
            component=self.name,
            event_type="agent_start",
            status="running",
            details={"type": "deterministic_safety_gate"},
        )

        state = await blackboard.get_state_snapshot()
        market_data = state.market_data
        tech = state.technical_findings
        fund = state.fundamental_findings
        news = state.news_sentiment
        forecasting = state.forecasting

        checks: List[Dict[str, Any]] = []
        warnings: List[str] = []
        reasons: List[str] = []
        risk_scores: List[float] = []

        # -------------------------------------------------------------
        # 1. Check Data Sufficiency
        # -------------------------------------------------------------
        bar_count = len(market_data.bars)
        if bar_count < 50:
            checks.append(
                {
                    "name": "data_sufficiency",
                    "passed": False,
                    "score": 1.0,
                    "message": f"Critical data shortage: only {bar_count} bars available (minimum 50 required).",
                }
            )
            reasons.append("Data volume is insufficient for statistical confidence.")
            risk_scores.append(1.0)
        elif bar_count < 200:
            checks.append(
                {
                    "name": "data_sufficiency",
                    "passed": True,
                    "score": 0.3,
                    "message": f"Moderate data volume: {bar_count} bars available. SMA-200 lookback unavailable.",
                }
            )
            warnings.append(f"Lookback limited to {bar_count} bars; 200-bar trend context unavailable.")
            risk_scores.append(0.3)
        else:
            checks.append(
                {
                    "name": "data_sufficiency",
                    "passed": True,
                    "score": 0.0,
                    "message": f"Optimal data sufficiency: {bar_count} bars verified.",
                }
            )
            risk_scores.append(0.0)

        # -------------------------------------------------------------
        # 2. Check Price Validity & Stale/Corrupted Data
        # -------------------------------------------------------------
        invalid_bars = [b for b in market_data.bars if b.close <= 0 or b.low <= 0 or b.high < b.low]
        if invalid_bars:
            checks.append(
                {
                    "name": "price_validity",
                    "passed": False,
                    "score": 1.0,
                    "message": f"Detected {len(invalid_bars)} corrupted price bars with invalid or non-positive quotes.",
                }
            )
            reasons.append("Price series contains non-positive or geometrically corrupted bars.")
            risk_scores.append(1.0)
        else:
            checks.append(
                {
                    "name": "price_validity",
                    "passed": True,
                    "score": 0.0,
                    "message": "All historical price bars passed numerical bounds validation.",
                }
            )
            risk_scores.append(0.0)

        # -------------------------------------------------------------
        # 3. Volatility and Maximum Drawdown Analysis
        # -------------------------------------------------------------
        if bar_count > 10:
            closes = [b.close for b in market_data.bars]
            peak = closes[0]
            max_drawdown = 0.0
            for c in closes:
                if c > peak:
                    peak = c
                dd = (peak - c) / peak if peak > 0 else 0.0
                if dd > max_drawdown:
                    max_drawdown = dd

            max_dd_pct = round(max_drawdown * 100, 2)
            if max_drawdown > 0.35:
                checks.append(
                    {
                        "name": "maximum_drawdown",
                        "passed": False,
                        "score": 0.8,
                        "message": f"Severe maximum drawdown detected: {max_dd_pct}% over lookback window.",
                    }
                )
                reasons.append(f"Asset suffered substantial peak-to-trough decline of {max_dd_pct}%.")
                risk_scores.append(0.8)
            elif max_drawdown > 0.20:
                checks.append(
                    {
                        "name": "maximum_drawdown",
                        "passed": True,
                        "score": 0.4,
                        "message": f"Elevated drawdown observed: {max_dd_pct}%.",
                    }
                )
                warnings.append(f"Asset experienced historical drawdown of {max_dd_pct}%.")
                risk_scores.append(0.4)
            else:
                checks.append(
                    {
                        "name": "maximum_drawdown",
                        "passed": True,
                        "score": 0.1,
                        "message": f"Controlled historical drawdown: {max_dd_pct}%.",
                    }
                )
                risk_scores.append(0.1)
        else:
            checks.append(
                {
                    "name": "maximum_drawdown",
                    "passed": False,
                    "score": 0.5,
                    "message": "Insufficient history to compute drawdown.",
                }
            )
            risk_scores.append(0.5)

        # -------------------------------------------------------------
        # 4. Technical Indicator Sanity & Overextension Checks
        # -------------------------------------------------------------
        if tech.status == FindingStatus.AVAILABLE:
            inds = tech.indicators
            rsi = inds.rsi_14
            if rsi is not None:
                if rsi > 80.0:
                    checks.append(
                        {
                            "name": "rsi_extreme_bound",
                            "passed": True,
                            "score": 0.6,
                            "message": f"RSI indicates extreme overbought condition ({rsi}). High reversal hazard.",
                        }
                    )
                    warnings.append(f"Overbought warning: RSI-14 is elevated at {rsi}.")
                    risk_scores.append(0.6)
                elif rsi < 20.0:
                    checks.append(
                        {
                            "name": "rsi_extreme_bound",
                            "passed": True,
                            "score": 0.5,
                            "message": f"RSI indicates severe oversold condition ({rsi}). High volatility hazard.",
                        }
                    )
                    warnings.append(f"Oversold warning: RSI-14 depressed at {rsi}.")
                    risk_scores.append(0.5)
                else:
                    checks.append(
                        {
                            "name": "rsi_extreme_bound",
                            "passed": True,
                            "score": 0.1,
                            "message": f"RSI within normal operational boundaries ({rsi}).",
                        }
                    )
                    risk_scores.append(0.1)

            # Check Bollinger Band bounds
            if inds.bb_lower is not None and inds.bb_upper is not None:
                if inds.bb_lower > inds.bb_upper:
                    checks.append(
                        {
                            "name": "indicator_math_integrity",
                            "passed": False,
                            "score": 1.0,
                            "message": "Bollinger Bands inversion detected (lower > upper).",
                        }
                    )
                    reasons.append("Technical indicator mathematical integrity check failed.")
                    risk_scores.append(1.0)
        else:
            checks.append(
                {
                    "name": "technical_findings_availability",
                    "passed": False,
                    "score": 0.5,
                    "message": "Technical findings unavailable for risk corroboration.",
                }
            )
            warnings.append("Risk assessment executed without completed technical indicators.")
            risk_scores.append(0.5)

        # -------------------------------------------------------------
        # 5. Fundamental Solvency & Conflicting Evidence Check
        # -------------------------------------------------------------
        if fund.status == FindingStatus.AVAILABLE:
            de_ratio = fund.ratios.get("debt_to_equity")
            if de_ratio is not None:
                if de_ratio > 3.0:
                    checks.append(
                        {
                            "name": "debt_solvency",
                            "passed": False,
                            "score": 0.85,
                            "message": f"High leverage alert: Debt-to-Equity is {de_ratio} (> 3.0 benchmark).",
                        }
                    )
                    reasons.append(f"Balance sheet exhibits aggressive leverage (D/E: {de_ratio}).")
                    risk_scores.append(0.85)
                else:
                    checks.append(
                        {
                            "name": "debt_solvency",
                            "passed": True,
                            "score": 0.05,
                            "message": f"Conservative balance sheet leverage: D/E is {de_ratio}.",
                        }
                    )
                    risk_scores.append(0.05)

        # -------------------------------------------------------------
        # 6. News & Media Sentiment Risk Analysis
        # -------------------------------------------------------------
        if news.status == FindingStatus.AVAILABLE:
            if news.total_articles == 0:
                checks.append(
                    {
                        "name": "news_sentiment_risk",
                        "passed": True,
                        "score": 0.2,
                        "message": "Zero verified news articles found; neutral media baseline applied.",
                    }
                )
                warnings.append("Risk evaluated with zero verified news media coverage.")
                risk_scores.append(0.2)
            else:
                # Check for critical regulatory, fraud, or legal scrutiny
                combined_adverse = " ".join(news.negative_events + news.risk_observations).lower()
                has_regulatory_issue = any(
                    term in combined_adverse
                    for term in ["sebi", "rbi", "probe", "investigation", "penalty", "fraud", "court", "cbi", "ed raid"]
                )

                if has_regulatory_issue:
                    checks.append(
                        {
                            "name": "news_sentiment_risk",
                            "passed": False,
                            "score": 0.8,
                            "message": "Severe corporate governance, regulatory scrutiny, or legal inquiry detected in news media.",
                        }
                    )
                    reasons.append("Active regulatory scrutiny or compliance proceeding identified in recent media coverage.")
                    risk_scores.append(0.8)
                elif news.overall_sentiment == "NEGATIVE" or news.sentiment_score <= -0.25:
                    checks.append(
                        {
                            "name": "news_sentiment_risk",
                            "passed": False,
                            "score": 0.65,
                            "message": (
                                f"Elevated negative media coverage ({news.negative_count}/{news.total_articles} articles negative, "
                                f"score {news.sentiment_score:+.2f})."
                            ),
                        }
                    )
                    reasons.append(f"Adverse media sentiment indicates near-term headline risk ({news.negative_count} negative articles).")
                    warnings.append(f"Repeated negative media coverage observed (sentiment score {news.sentiment_score:+.2f}).")
                    risk_scores.append(0.65)
                elif news.overall_sentiment == "POSITIVE" and news.sentiment_score >= 0.25:
                    checks.append(
                        {
                            "name": "news_sentiment_risk",
                            "passed": True,
                            "score": 0.05,
                            "message": (
                                f"Favorable media consensus ({news.positive_count}/{news.total_articles} articles positive, "
                                f"score {news.sentiment_score:+.2f})."
                            ),
                        }
                    )
                    reasons.append(f"Supportive media sentiment ({news.positive_count} positive reports) provides positive institutional context.")
                    risk_scores.append(0.05)
                else:
                    # Neutral or mixed
                    checks.append(
                        {
                            "name": "news_sentiment_risk",
                            "passed": True,
                            "score": 0.2,
                            "message": (
                                f"Balanced/neutral media sentiment ({news.positive_count} pos, {news.neutral_count} neu, "
                                f"{news.negative_count} neg, score {news.sentiment_score:+.2f})."
                            ),
                        }
                    )
                    risk_scores.append(0.2)
        elif news.status == FindingStatus.UNAVAILABLE:
            checks.append(
                {
                    "name": "news_sentiment_risk",
                    "passed": True,
                    "score": 0.25,
                    "message": "News sentiment feed unavailable; evaluating risk without media sentiment.",
                }
            )
            warnings.append("Risk assessment conducted without media sentiment corroboration (news feed unavailable).")
            risk_scores.append(0.25)
        else:
            # PENDING or FAILED
            checks.append(
                {
                    "name": "news_sentiment_risk",
                    "passed": True,
                    "score": 0.25,
                    "message": f"News sentiment status is {news.status.value}; neutral default applied.",
                }
            )
            warnings.append(f"Media sentiment not available (status: {news.status.value}).")
            risk_scores.append(0.25)

        # -------------------------------------------------------------
        # 7. Predictive Price Forecasting Risk Analysis
        # -------------------------------------------------------------
        if forecasting.status == FindingStatus.AVAILABLE:
            best = forecasting.best_model
            if best and best.forecasts:
                # Maximum horizon forecast point (10th trading session)
                p10 = next((p for p in best.forecasts if p.step == 10), best.forecasts[-1])
                pct_change = p10.pct_change

                if pct_change <= -8.0:
                    checks.append(
                        {
                            "name": "predictive_forecast_risk",
                            "passed": False,
                            "score": 0.75,
                            "message": (
                                f"Severe downside forecast: {best.model_name} predicts {pct_change:.1f}% "
                                f"decline over 10 trading sessions (target: {p10.predicted_price:.2f})."
                            ),
                        }
                    )
                    reasons.append(
                        f"Predictive quantitative forecast ({best.model_name}) indicates severe downward trajectory ({pct_change:.1f}%)."
                    )
                    warnings.append(f"Model {best.model_name} projects severe downside of {pct_change:.1f}% over {p10.step} sessions.")
                    risk_scores.append(0.75)
                elif pct_change <= -3.0:
                    checks.append(
                        {
                            "name": "predictive_forecast_risk",
                            "passed": True,
                            "score": 0.50,
                            "message": (
                                f"Moderate downside forecast: {best.model_name} predicts {pct_change:.1f}% "
                                f"contraction over {p10.step} trading sessions."
                            ),
                        }
                    )
                    warnings.append(f"Forward projection indicates moderate downward pressure ({pct_change:.1f}% over {p10.step} sessions).")
                    risk_scores.append(0.50)
                elif pct_change >= 3.0:
                    checks.append(
                        {
                            "name": "predictive_forecast_risk",
                            "passed": True,
                            "score": 0.05,
                            "message": (
                                f"Supportive upward forecast: {best.model_name} predicts +{pct_change:.1f}% "
                                f"gain over 10 trading sessions."
                            ),
                        }
                    )
                    reasons.append(
                        f"Quantitative forecast ({best.model_name}) projects supportive upward movement (+{pct_change:.1f}%)."
                    )
                    risk_scores.append(0.05)
                else:
                    checks.append(
                        {
                            "name": "predictive_forecast_risk",
                            "passed": True,
                            "score": 0.15,
                            "message": (
                                f"Neutral forward trajectory: {best.model_name} projects modest drift "
                                f"({pct_change:+.1f}% over 10 sessions)."
                            ),
                        }
                    )
                    risk_scores.append(0.15)

                # Check model divergence across candidate models
                if forecasting.model_divergence_pct > 6.0:
                    warnings.append(
                        f"High forecast divergence ({forecasting.model_divergence_pct:.1f}%): "
                        "Candidate models disagree significantly on forward path."
                    )

                # Check validation directional accuracy of best model
                if best.validation_metrics.directional_accuracy < 45.0:
                    warnings.append(
                        f"Low validation directional accuracy ({best.validation_metrics.directional_accuracy:.1f}%): "
                        f"{best.model_name} trend direction carries elevated uncertainty."
                    )
            else:
                checks.append(
                    {
                        "name": "predictive_forecast_risk",
                        "passed": True,
                        "score": 0.20,
                        "message": "Forecasting available but no best model forecasts generated; neutral baseline applied.",
                    }
                )
                warnings.append("Forecasting produced no valid candidate model forecasts.")
                risk_scores.append(0.20)
        elif forecasting.status == FindingStatus.UNAVAILABLE:
            checks.append(
                {
                    "name": "predictive_forecast_risk",
                    "passed": True,
                    "score": 0.20,
                    "message": "Predictive price forecasting feed unavailable; evaluating risk without forward projections.",
                }
            )
            warnings.append("Risk assessment conducted without predictive forecasting (feed unavailable).")
            risk_scores.append(0.20)
        else:
            checks.append(
                {
                    "name": "predictive_forecast_risk",
                    "passed": True,
                    "score": 0.20,
                    "message": f"Predictive forecasting status is {forecasting.status.value}; neutral baseline applied.",
                }
            )
            warnings.append(f"Predictive forecasting not available (status: {forecasting.status.value}).")
            risk_scores.append(0.20)

        # -------------------------------------------------------------
        # 8. Scenario Stress Testing & Tail Hazard Analysis (Gate 8)
        # -------------------------------------------------------------
        sim_state = state.scenario_simulation
        if sim_state.status == FindingStatus.AVAILABLE and sim_state.scenarios:
            worst = sim_state.worst_case_scenario
            worst_score = worst.simulated.scenario_risk_score if worst else 0.0
            worst_name = worst.scenario_name if worst else "None"
            worst_rec = worst.simulated.scenario_recommendation if worst else "N/A"

            gate8_passed = worst_score < 0.65
            gate8_msg = (
                f"Worst-case stress scenario '{worst_name}' yields simulated risk score {worst_score:.3f} ({worst_rec})."
            )

            if sim_state.scenarios_changing_recommendation:
                warnings.append(
                    f"Gate 8 Scenario Stress: {len(sim_state.scenarios_changing_recommendation)} scenario(s) flip baseline recommendation: "
                    f"{', '.join(sim_state.scenarios_changing_recommendation[:2])}."
                )

            if worst_score >= 0.65:
                warnings.append(
                    f"Gate 8 Tail Hazard: Severe market stress ({worst_name}) escalates simulated risk to {worst_rec}."
                )

            checks.append(
                {
                    "name": "scenario_stress_testing",
                    "passed": gate8_passed,
                    "score": round(worst_score, 3),
                    "message": gate8_msg,
                    "details": {
                        "worst_case_scenario": worst_name,
                        "worst_case_score": worst_score,
                        "worst_case_recommendation": worst_rec,
                        "scenarios_flipping_recommendation": sim_state.scenarios_changing_recommendation,
                        "scenarios_material_risk_increase": sim_state.scenarios_material_risk_increase,
                    },
                }
            )
        else:
            checks.append(
                {
                    "name": "scenario_stress_testing",
                    "passed": True,
                    "score": 0.20,
                    "message": "Scenario simulation pending or deferred to downstream stress agent.",
                }
            )

        # -------------------------------------------------------------
        # Composite Risk Calculation & Institutional Recommendation
        # -------------------------------------------------------------
        composite_score = round(sum(risk_scores) / len(risk_scores), 3) if risk_scores else 0.5
        time_horizon = getattr(state, "time_horizon", "short_term")
        horizon_label = time_horizon.upper().replace("_", " ")

        if composite_score >= 0.65 or any(c["score"] >= 0.95 for c in checks):
            overall_risk = "HIGH" if composite_score < 0.85 else "CRITICAL"
            recommendation = "REJECTED_HIGH_RISK"
            if not reasons:
                reasons.append("Multiple risk thresholds breached simultaneously.")
        elif composite_score >= 0.35 or warnings:
            overall_risk = "MODERATE"
            recommendation = "APPROVED_WITH_CAUTION"
            reasons.append("Passes institutional safety criteria with noted cautionary flags.")
        else:
            overall_risk = "LOW"
            recommendation = "APPROVED"
            reasons.append("Optimal risk profile across price sanity, drawdown, and technical metrics.")

        reasons.insert(0, f"Evaluated under institutional [{horizon_label}] risk mandate.")

        await blackboard.update_risk_findings(
            producer=self.name,
            overall_risk_level=overall_risk,
            composite_risk_score=composite_score,
            recommendation=recommendation,
            checks=checks,
            warnings=warnings,
            reasons=reasons,
            status=FindingStatus.AVAILABLE,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000
        await blackboard.log_event(
            component=self.name,
            event_type="agent_complete",
            status="completed",
            details={
                "duration_ms": duration_ms,
                "overall_risk_level": overall_risk,
                "composite_risk_score": composite_score,
                "recommendation": recommendation,
            },
        )

        return {
            "status": "completed",
            "duration_ms": duration_ms,
            "overall_risk_level": overall_risk,
            "composite_risk_score": composite_score,
            "recommendation": recommendation,
            "checks": checks,
        }

    async def evaluate_gate_8(self, blackboard: BlackboardManager) -> Dict[str, Any]:
        """Evaluate or update Gate 8 (Scenario Stress Testing) after scenario simulation completes."""
        state = await blackboard.get_state_snapshot()
        sim_state = state.scenario_simulation
        if sim_state.status != FindingStatus.AVAILABLE or not sim_state.scenarios:
            return {"status": "skipped", "message": "Scenario simulation not available"}

        worst = sim_state.worst_case_scenario
        worst_score = worst.simulated.scenario_risk_score if worst else 0.0
        worst_name = worst.scenario_name if worst else "None"
        worst_rec = worst.simulated.scenario_recommendation if worst else "N/A"

        def _get_name(c: Any) -> str:
            if hasattr(c, "name"):
                return c.name
            if isinstance(c, dict):
                return c.get("name", "")
            return ""

        from stockshield.blackboard.models import RiskCheck

        gate8_check = {
            "name": "scenario_stress_testing",
            "passed": worst_score < 0.65,
            "score": round(worst_score, 3),
            "message": (
                f"Worst-case stress scenario '{worst_name}' yields simulated risk score {worst_score:.3f} ({worst_rec})."
            ),
            "details": {
                "worst_case_scenario": worst_name,
                "worst_case_score": worst_score,
                "worst_case_recommendation": worst_rec,
                "scenarios_flipping_recommendation": sim_state.scenarios_changing_recommendation,
                "scenarios_material_risk_increase": sim_state.scenarios_material_risk_increase,
            },
        }

        gate8_model = RiskCheck(
            name="scenario_stress_testing",
            passed=worst_score < 0.65,
            score=round(worst_score, 3),
            message=(
                f"Worst-case stress scenario '{worst_name}' yields simulated risk score {worst_score:.3f} ({worst_rec})."
            ),
        )

        async with blackboard._lock:
            existing_checks = [
                c for c in blackboard._state.risk_findings.checks if _get_name(c) != "scenario_stress_testing"
            ]
            existing_checks.append(gate8_model)
            blackboard._state.risk_findings.checks = existing_checks

            if worst_score >= 0.65:
                warn_msg = (
                    f"Gate 8 Tail Hazard: Severe market stress ({worst_name}) escalates simulated risk to {worst_rec}."
                )
                if warn_msg not in blackboard._state.risk_findings.warnings:
                    blackboard._state.risk_findings.warnings.append(warn_msg)

        await blackboard.log_event(
            component=self.name,
            event_type="gate_8_evaluated",
            status="completed",
            details={
                "worst_case_scenario": worst_name,
                "worst_case_score": worst_score,
                "worst_case_recommendation": worst_rec,
            },
        )
        return {"status": "completed", "gate_8": gate8_check}
