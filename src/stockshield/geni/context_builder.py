"""Analysis Context Builder for GENI.

Extracts structured, grounded evidence from completed StockShield 2.0 analysis
runs persisted in SQLite (ExperimentStorage) and full JSON snapshots.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from stockshield.evaluation.storage import ExperimentStorage


class RunNotFoundError(Exception):
    """Raised when the specified run_id is not found in SQLite or snapshot store."""

    pass


class AnalysisNotReadyError(Exception):
    """Raised when the analysis is still pending or running."""

    pass


class AnalysisFailedError(Exception):
    """Raised when the target run terminated with a failure status."""

    pass


class AnalysisInconsistentError(Exception):
    """Raised when the analysis records are corrupted or unparseable."""

    pass


def validate_run_id_safe(run_id: str) -> str:
    """Validate run_id syntax and guard against path traversal attacks."""
    if not isinstance(run_id, str):
        raise ValueError("run_id must be a string.")
    cleaned = run_id.strip()
    if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
        raise ValueError("Path traversal sequences are strictly disallowed in run_id.")
    if not re.match(r"^run_[a-zA-Z0-9_\-]+$", cleaned):
        raise ValueError(
            f"Invalid run_id syntax '{run_id}'. Expected alphanumeric pattern matching '^run_[a-zA-Z0-9_\\-]+$'."
        )
    return cleaned


class GeniContextBuilder:
    """Constructs comprehensive, structured, domain-grounded context for GENI."""

    def __init__(self, storage: Optional[ExperimentStorage] = None):
        self.storage = storage or ExperimentStorage()

    def get_raw_analysis_payload(self, run_id: str) -> Dict[str, Any]:
        """Retrieve canonical analysis record from snapshot file or SQLite storage.

        Source-of-truth priority:
        1. Full-fidelity JSON snapshot file on disk.
        2. Snapshot JSON stored in SQLite `runs.snapshot_json`.
        3. Reconstructed dictionary from SQLite joined stage tables.
        """
        valid_id = validate_run_id_safe(run_id)

        # 1. Query SQLite run metadata first to verify existence and completion status
        run_record = self.storage.get_run(valid_id)

        # Check snapshot file on disk
        snap_path = (self.storage.snapshot_dir / f"{valid_id}.json").resolve()
        # Verify path traversal protection
        try:
            snap_path.relative_to(self.storage.snapshot_dir.resolve())
        except ValueError:
            raise ValueError(f"Path traversal detected in snapshot path resolution for '{valid_id}'.")

        snapshot_data: Optional[Dict[str, Any]] = None

        if snap_path.exists():
            try:
                raw_text = snap_path.read_text(encoding="utf-8")
                snapshot_data = json.loads(raw_text)
            except Exception:
                snapshot_data = None

        if not snapshot_data and run_record and run_record.get("snapshot_json"):
            try:
                snapshot_data = json.loads(run_record["snapshot_json"])
            except Exception:
                snapshot_data = None

        # If neither snapshot file nor snapshot_json exists, check if run_record has stage tables
        if not snapshot_data:
            if not run_record:
                raise RunNotFoundError(f"Run '{valid_id}' not found in SQLite storage or snapshot registry.")
            # Use joined stage record from SQLite
            snapshot_data = run_record

        # Verify actual run completion status
        status = str(
            snapshot_data.get("workflow_status")
            or (run_record.get("status") if run_record else None)
            or "UNKNOWN"
        ).upper()

        if status in {"PENDING", "RUNNING"}:
            raise AnalysisNotReadyError(
                f"Analysis for run '{valid_id}' is currently {status}. GENI requires a fully COMPLETED analysis."
            )
        if status in {"FAILED", "ERROR"}:
            err_msg = (
                snapshot_data.get("notes")
                or (run_record.get("error_message") if run_record else None)
                or "Unknown analysis failure"
            )
            raise AnalysisFailedError(f"Analysis for run '{valid_id}' failed: {err_msg}")
        if status != "COMPLETED":
            raise AnalysisInconsistentError(
                f"Run '{valid_id}' has non-completed status '{status}'. Cannot construct reliable analysis context."
            )

        return snapshot_data

    def build_context(self, run_id: str) -> Tuple[str, List[str], str]:
        """Extract structured evidence across all 6 domains and assemble prompt context.

        Returns:
            Tuple[context_markdown, sources_used, ticker]
        """
        data = self.get_raw_analysis_payload(run_id)

        ticker = str(data.get("ticker", "UNKNOWN")).upper()
        trace_id = str(data.get("trace_id", "N/A"))
        time_horizon = str(data.get("time_horizon", "short_term"))
        forecast_horizon = str(data.get("forecast_horizon", "1_month"))
        workflow_mode = str(data.get("workflow_mode", "sequential"))
        completed_at = str(data.get("completed_at_utc", data.get("created_at_utc", "N/A")))

        sources_used: List[str] = []
        sections: List[str] = []

        sections.append(
            f"=== STOCKSHIELD 2.0 CANONICAL ANALYSIS EVIDENCE ===\n"
            f"- Ticker: {ticker}\n"
            f"- Run ID: {run_id}\n"
            f"- Trace ID: {trace_id}\n"
            f"- Workflow Architecture: {workflow_mode}\n"
            f"- Investment Horizon: {time_horizon.upper()} (Forecast Horizon: {forecast_horizon})\n"
            f"- Analysis Completed At: {completed_at}\n"
        )

        # -------------------------------------------------------------
        # Section A: Overall Market Data & Baseline
        # -------------------------------------------------------------
        mkt = data.get("market_data") or {}
        if mkt and mkt.get("status") in {"available", "valid", "stale"}:
            sources_used.append("overall_analysis")
            source_feed = mkt.get("source", "N/A")
            bar_count = mkt.get("bar_count", 0)
            is_stale = mkt.get("is_stale", False)
            freshness_days = mkt.get("freshness_age_days", 0)
            currency = mkt.get("currency", "INR")
            exchange = mkt.get("exchange", "NSE")

            # Extract latest close price
            bars = mkt.get("bars") or []
            latest_close = "N/A"
            if bars and isinstance(bars, list) and len(bars) > 0:
                latest_close = f"{bars[-1].get('close', 'N/A')} {currency}"
            elif "close_price" in mkt:
                latest_close = f"{mkt['close_price']} {currency}"

            sections.append(
                f"### SECTION A: MARKET DATA & BASELINE PRICE\n"
                f"- Data Source: {source_feed} ({exchange}, {currency})\n"
                f"- Historical Trading Bars Analyzed: {bar_count}\n"
                f"- Latest Market Close: {latest_close}\n"
                f"- Data Freshness: {'STALE' if is_stale else 'CURRENT'} ({freshness_days} days old)\n"
            )
        else:
            sections.append("### SECTION A: MARKET DATA & BASELINE PRICE\n[UNAVAILABLE]\n")

        # -------------------------------------------------------------
        # Section B: Technical Analysis (Google ADK Technical Agent)
        # -------------------------------------------------------------
        tech = data.get("technical_findings") or data.get("technical") or {}
        if tech and tech.get("status") == "available":
            sources_used.append("technical_analysis")
            sig = tech.get("signal", "NEUTRAL")
            conf = round(float(tech.get("confidence") or tech.get("signal_confidence") or 0.0) * 100, 1)
            ind = tech.get("indicators") or {}
            summary = tech.get("summary", "")

            sections.append(
                f"### SECTION B: TECHNICAL QUANTITATIVE FINDINGS (Google ADK)\n"
                f"- Composite Technical Signal: {sig} ({conf}% algorithmic confidence)\n"
                f"- Moving Averages: SMA-20={ind.get('sma_20')}, SMA-50={ind.get('sma_50')}, SMA-200={ind.get('sma_200')}\n"
                f"- Exponential Averages: EMA-12={ind.get('ema_12')}, EMA-26={ind.get('ema_26')}\n"
                f"- Momentum Indicators: RSI-14={ind.get('rsi_14')}, MACD Line={ind.get('macd_line')}, "
                f"Signal={ind.get('macd_signal')}, Histogram={ind.get('macd_hist')}\n"
                f"- Volatility Indicators: Bollinger Upper={ind.get('bb_upper')}, Mid={ind.get('bb_middle')}, "
                f"Lower={ind.get('bb_lower')}, Bandwidth={ind.get('bb_bandwidth')}%, ATR-14={ind.get('atr_14')}\n"
                f"- Agent Summary: {summary}\n"
            )
        else:
            sections.append("### SECTION B: TECHNICAL QUANTITATIVE FINDINGS (Google ADK)\n[UNAVAILABLE]\n")

        # -------------------------------------------------------------
        # Section C: Risk Intelligence & Safety Governance
        # -------------------------------------------------------------
        risk = data.get("risk_findings") or data.get("risk") or {}
        if risk and risk.get("status") == "available":
            sources_used.append("risk_assessment")
            risk_lvl = risk.get("risk_level") or risk.get("overall_risk_level") or "UNKNOWN"
            comp_score = risk.get("composite_score") or risk.get("composite_risk_score")
            rec = risk.get("recommendation", "UNKNOWN")
            warnings = risk.get("warnings") or []
            reasons = risk.get("reasons") or []

            # Separate base-case risk warnings from downstream Gate 8 stress-test tail hazard warnings
            base_case_warnings = [
                w for w in warnings if not (w.strip().lower().startswith("gate 8") or "tail hazard" in w.lower())
            ]
            stress_test_warnings = [
                w for w in warnings if (w.strip().lower().startswith("gate 8") or "tail hazard" in w.lower())
            ]

            base_warn_text = (
                "\n".join([f"  * {w}" for w in base_case_warnings])
                if base_case_warnings
                else "  * None recorded"
            )
            stress_warn_text = (
                "\n".join([f"  * {w}" for w in stress_test_warnings])
                if stress_test_warnings
                else "  * None recorded"
            )
            reason_text = "\n".join([f"  * {r}" for r in reasons]) if reasons else "  * None recorded"

            # Determine explicit causal driver for the institutional recommendation
            rec_driver = "Unknown"
            if comp_score is not None:
                try:
                    s_val = float(comp_score)
                    if s_val >= 0.65:
                        rec_driver = (
                            f"Triggered by high base-case composite risk score ({s_val:.3f} >= 0.65 critical threshold)."
                        )
                    elif s_val >= 0.35:
                        rec_driver = (
                            f"Triggered by moderate base-case composite risk score ({s_val:.3f} >= 0.35 moderate threshold)."
                        )
                    elif base_case_warnings and rec == "APPROVED_WITH_CAUTION":
                        rec_driver = (
                            f"Base-case composite risk score ({s_val:.3f}) is in the low-risk range (< 0.35), but "
                            f"recommendation was elevated to 'APPROVED_WITH_CAUTION' strictly due to active base-case "
                            f"governance warnings: {'; '.join(base_case_warnings)}. Downstream scenario stress tests (Gate 8) "
                            f"did NOT cause or calculate this recommendation."
                        )
                    elif rec == "APPROVED":
                        rec_driver = (
                            f"Base-case composite risk score ({s_val:.3f} < 0.35) with zero active governance warnings "
                            f"yields clean 'APPROVED' status."
                        )
                    else:
                        rec_driver = f"Base-case composite score: {s_val:.3f}, recommendation: {rec}."
                except (ValueError, TypeError):
                    rec_driver = "Unspecified composite score format."

            sections.append(
                f"### SECTION C: RISK INTELLIGENCE & GOVERNANCE\n"
                f"- Overall Risk Rating: {risk_lvl}\n"
                f"- Composite Risk Score: {comp_score} (Scale 0.0 safe to 1.0 critical)\n"
                f"  * Scoring Methodology: Unweighted arithmetic mean across active base-case gates (Gates 1–7: Data Quality, "
                f"Historical Volatility, Historical Drawdown, Market Liquidity, Balance Sheet Solvency, News & Sentiment, "
                f"and Predictive Forward Trajectory). Gate 8 (Scenario Stress Testing) is NOT part of this average. "
                f"Individual risk factors do NOT have percentage weights or priority rankings.\n"
                f"- Institutional Recommendation: {rec}\n"
                f"  * Governance Recommendation Rule: Score >= 0.65 -> REJECTED_HIGH_RISK; Score >= 0.35 OR presence of "
                f"base-case warnings -> APPROVED_WITH_CAUTION; Otherwise -> APPROVED.\n"
                f"  * Recommendation Causal Driver: {rec_driver}\n"
                f"- Base-Case Governance Warnings (Causal triggers for recommendation caution rule):\n{base_warn_text}\n"
                f"- Downstream Stress-Test Warnings (Gate 8 post-hoc tail hazard - informational only, NOT a cause of base-case score or recommendation):\n{stress_warn_text}\n"
                f"- Assessment Rationales:\n{reason_text}\n"
            )
        else:
            sections.append("### SECTION C: RISK INTELLIGENCE & GOVERNANCE\n[UNAVAILABLE]\n")

        # -------------------------------------------------------------
        # Section D: Financial News & Media Sentiment
        # -------------------------------------------------------------
        news = data.get("news_and_sentiment") or data.get("news_sentiment") or {}
        if news and news.get("status") == "available":
            sources_used.append("news_and_sentiment")
            sent_str = news.get("overall_sentiment", "NEUTRAL")
            sent_score = news.get("sentiment_score", 0.0)
            counts = news.get("article_counts") or {}
            pos_cnt = counts.get("positive", news.get("positive_count", 0))
            neu_cnt = counts.get("neutral", news.get("neutral_count", 0))
            neg_cnt = counts.get("negative", news.get("negative_count", 0))
            tot_cnt = counts.get("total", news.get("total_articles", 0))
            pos_events = news.get("positive_events") or []
            neg_events = news.get("negative_events") or []
            observations = news.get("risk_observations") or []

            sections.append(
                f"### SECTION D: FINANCIAL NEWS & MEDIA SENTIMENT\n"
                f"- Overall Sentiment: {sent_str} (Score: {sent_score})\n"
                f"- Coverage Volume: {tot_cnt} articles (Positive: {pos_cnt}, Neutral: {neu_cnt}, Negative: {neg_cnt})\n"
                f"- Key Positive Developments: {'; '.join(pos_events) if pos_events else 'None'}\n"
                f"- Key Negative Developments: {'; '.join(neg_events) if neg_events else 'None'}\n"
                f"- News Observations: {'; '.join(observations) if observations else 'None'}\n"
            )
        else:
            sections.append("### SECTION D: FINANCIAL NEWS & MEDIA SENTIMENT\n[UNAVAILABLE]\n")

        # -------------------------------------------------------------
        # Section E: Quantitative Forward Forecasting
        # -------------------------------------------------------------
        fc = data.get("forecasting") or {}
        if fc and fc.get("status") == "available":
            sources_used.append("forecasting")
            best_model = fc.get("best_model", "N/A")
            div_pct = fc.get("model_divergence_pct", 0.0)
            consensus = fc.get("directional_consensus", "N/A")

            models_eval = fc.get("models_evaluated") or fc.get("models") or []
            model_lines = []
            for m in models_eval:
                m_name = m.get("model_name", "Unknown")
                m_rmse = m.get("rmse") or (m.get("validation_metrics", {}) or {}).get("rmse")
                m_mae = m.get("mae") or (m.get("validation_metrics", {}) or {}).get("mae")
                m_dir = m.get("directional_accuracy") or (m.get("validation_metrics", {}) or {}).get(
                    "directional_accuracy"
                )
                model_lines.append(f"  * {m_name}: Val RMSE={m_rmse}, Val MAE={m_mae}, Directional Acc={m_dir}%")

            forecasts = fc.get("forecasts") or []
            fc_lines = []
            for f in forecasts:
                step = f.get("step")
                dt = f.get("target_date")
                price = f.get("predicted_price")
                pct = f.get("pct_change")
                ci_low = f.get("conf_lower")
                ci_up = f.get("conf_upper")
                fc_lines.append(f"  * T+{step} ({dt}): {price} ({pct}%), 95% CI: [{ci_low}, {ci_up}]")

            sections.append(
                f"### SECTION E: FORWARD PRICE FORECASTING\n"
                f"- Selected Optimal Model: {best_model}\n"
                f"- Multi-Model Divergence: {div_pct}% (Directional Consensus: {consensus})\n"
                f"- Candidate Model Validation Performance:\n"
                f"{chr(10).join(model_lines) if model_lines else '  * None'}\n"
                f"- Forward Price Projections:\n"
                f"{chr(10).join(fc_lines) if fc_lines else '  * None'}\n"
                f"- Limitation Notice: Chronological holdout validation evaluates short-term pattern fit; "
                f"it does not guarantee persistent alpha or eliminate regime-shift risk.\n"
            )
        else:
            sections.append("### SECTION E: FORWARD PRICE FORECASTING\n[UNAVAILABLE]\n")

        # -------------------------------------------------------------
        # Section F: Scenario Simulation & Stress Testing
        # -------------------------------------------------------------
        sim = data.get("scenario_simulation") or {}
        if sim and sim.get("status") == "available":
            sources_used.append("scenario_simulation")
            tot_scen = sim.get("total_scenarios", sim.get("total_scenarios_evaluated", 0))
            worst = sim.get("worst_case_scenario") or {}
            w_name = worst.get("name") or worst.get("scenario_name", "N/A")
            w_score = worst.get("risk_score") or (worst.get("simulated") or {}).get("scenario_risk_score")
            w_rec = worst.get("recommendation") or (worst.get("simulated") or {}).get("scenario_recommendation")

            flips = sim.get("scenarios_flipping_recommendation") or sim.get("scenarios_changing_recommendation") or []
            mat_risks = sim.get("scenarios_material_risk_increase") or []

            # Monte Carlo results
            mc = sim.get("monte_carlo") or {}
            mc_text = ""
            if mc:
                mc_p5 = mc.get("percentile_5") or mc.get("p5")
                mc_p50 = mc.get("percentile_50") or mc.get("p50")
                mc_p95 = mc.get("percentile_95") or mc.get("p95")
                loss_prob = mc.get("probability_of_loss_pct")
                severe_loss_prob = mc.get("probability_of_severe_loss_pct")
                mc_text = (
                    f"- Stochastic Monte Carlo (1,000 paths, 20d horizon):\n"
                    f"  * Median (P50): {mc_p50} | P5 Severe Downside: {mc_p5} | P95 Bullish Trajectory: {mc_p95}\n"
                    f"  * Probability of Loss: {loss_prob}% | Severe Loss (>10%): {severe_loss_prob}%\n"
                )

            sections.append(
                f"### SECTION F: SCENARIO STRESS TESTING & MONTE CARLO\n"
                f"- Total Scenarios Evaluated: {tot_scen}\n"
                f"- Worst-Case Stress Scenario: '{w_name}' (Simulated Risk: {w_score}, Recommendation: {w_rec})\n"
                f"- Scenarios Flipping Recommendation: {', '.join(flips) if flips else 'None'}\n"
                f"- Scenarios Causing Material Risk Increase: {', '.join(mat_risks) if mat_risks else 'None'}\n"
                f"{mc_text}"
                f"- Simulation Scope & Causality Note: Hypothetical stress scenarios evaluate tail exposures under extreme macro conditions; "
                f"they are post-hoc simulations that do NOT contribute to or alter the baseline composite risk score or original recommendation.\n"
            )
        else:
            sections.append("### SECTION F: SCENARIO STRESS TESTING & MONTE CARLO\n[UNAVAILABLE]\n")

        # -------------------------------------------------------------
        # Section G: Multi-Agent Conflict & Divergence Synthesis
        # -------------------------------------------------------------
        # Identify explicit divergence across components to guide GENI's explanation
        conflicts: List[str] = []
        tech_sig = (
            (data.get("technical_findings") or data.get("technical") or {}).get("signal", "NEUTRAL")
            if tech
            else "NEUTRAL"
        )
        risk_rec = (
            (data.get("risk_findings") or data.get("risk") or {}).get("recommendation", "UNKNOWN")
            if risk
            else "UNKNOWN"
        )
        worst_rec = (sim.get("worst_case_scenario") or {}).get("recommendation") if sim else None

        if tech_sig == "BULLISH" and risk_rec == "APPROVED_WITH_CAUTION":
            conflicts.append(
                "Technical momentum is BULLISH (short-term upward momentum), but Risk Governance enforces "
                "'APPROVED_WITH_CAUTION' due to active base-case risk warnings (such as historical drawdown or forecast uncertainty). "
                "Downstream stress scenarios evaluate tail resilience under hypothetical crashes, but do not determine the base-case recommendation."
            )
        if worst_rec == "REJECTED_HIGH_RISK" and risk_rec != "REJECTED_HIGH_RISK":
            conflicts.append(
                f"Base-case risk recommendation is '{risk_rec}', but hypothetical extreme stress under "
                f"'{w_name}' severely flips the simulated outcome to 'REJECTED_HIGH_RISK'. "
                f"This downstream stress test highlights tail vulnerability under severe macro conditions, "
                f"but did NOT calculate or alter the original base-case score or recommendation."
            )
        if fc and fc.get("best_model"):
            models_eval = fc.get("models_evaluated") or []
            for m in models_eval:
                acc = m.get("directional_accuracy") or (m.get("validation_metrics", {}) or {}).get(
                    "directional_accuracy"
                )
                if acc is not None and acc < 45.0:
                    conflicts.append(
                        f"Forecasting model '{m.get('model_name')}' exhibits low directional accuracy ({acc}% < 45% threshold). "
                        f"In the Risk Engine, this triggers a cautionary governance warning that contributes to the 'APPROVED_WITH_CAUTION' "
                        f"recommendation rule, while the forecast price trajectory gate score itself is separately calculated."
                    )
                    break

        if conflicts:
            sections.append(
                "### SECTION G: MULTI-AGENT CROSS-EXAMINATION & CONFLICT NOTES\n"
                + "\n".join([f"- Note: {c}" for c in conflicts])
                + "\n"
            )

        context_markdown = "\n".join(sections)
        return context_markdown, sources_used, ticker
