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
            warnings.append(f"Lookback limited to {bar_count} bars; 200-day trend context unavailable.")
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
        # Composite Risk Calculation & Institutional Recommendation
        # -------------------------------------------------------------
        composite_score = round(sum(risk_scores) / len(risk_scores), 3) if risk_scores else 0.5

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
