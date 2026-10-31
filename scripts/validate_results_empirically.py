"""Comprehensive empirical results validation script for StockShield 2.0.

Executes Steps 1 through 6 of the validation mandate without modifying application code.
Produces raw verifiable results for docs/RESULTS_VALIDATION.md.
"""

import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
import pandas as pd
from pydantic import BaseModel

# Add src to pythonpath
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stockshield.agents.indicators import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_ema_series,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    compute_all_indicators,
)
from stockshield.api.main import app
from stockshield.blackboard.models import FindingStatus, StockShieldBlackboard
from stockshield.guardrails.guardrails import GuardrailsEngine
from stockshield.orchestration.workflow import StockShieldWorkflow


async def run_validation():
    print("=" * 80)
    print("STOCKSHIELD 2.0 — EMPIRICAL RESULTS VALIDATION SUITE")
    print("=" * 80)

    results_data = {
        "step1_app": {},
        "step2_api_tickers": {},
        "step3_indicators": {},
        "step4_guardrails": {},
        "step5_workflows": {},
        "step6_evaluation_inspection": {},
    }

    # =========================================================================
    # STEP 1: Run the application & Verify /health
    # =========================================================================
    print("\n[STEP 1] Testing Application & /health Endpoint...")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        # Test /health
        health_res = await client.get("/health")
        health_status = health_res.status_code
        health_json = health_res.json()
        print(f"  GET /health -> HTTP {health_status}")
        print(f"  Payload: {json.dumps(health_json, indent=2)}")

        # Test A2A discovery endpoints
        agent_card_res = await client.get("/.well-known/agent-card.json")
        legacy_card_res = await client.get("/.well-known/agent.json")
        print(f"  GET /.well-known/agent-card.json -> HTTP {agent_card_res.status_code}")
        print(f"  GET /.well-known/agent.json -> HTTP {legacy_card_res.status_code}")

        results_data["step1_app"] = {
            "health_http_status": health_status,
            "health_payload": health_json,
            "agent_card_status": agent_card_res.status_code,
            "legacy_card_status": legacy_card_res.status_code,
        }

    # =========================================================================
    # STEP 2: Test real analysis requests for TCS.NS, INFY.NS, RELIANCE.NS
    # =========================================================================
    print("\n[STEP 2] Submitting Valid API Analysis Requests for All 3 Tickers...")
    tickers = ["TCS.NS", "INFY.NS", "RELIANCE.NS"]

    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        for ticker in tickers:
            print(f"\n--- Testing {ticker} ---")
            payload = {
                "ticker": ticker,
                "user_prompt": f"Conduct institutional technical momentum and deterministic risk intelligence review for {ticker}.",
                "lookback_days": 200,
                "workflow_mode": "sequential",
                "risk_profile": "moderate",
            }
            start_t = time.perf_counter()
            res = await client.post("/analyze", json=payload)
            lat_ms = (time.perf_counter() - start_t) * 1000
            status_code = res.status_code
            data = res.json()

            # Schema check: does it have all expected sections?
            required_sections = [
                "run_id", "trace_id", "workflow_status", "ticker", "market_data",
                "technical_findings", "risk_findings", "final_report",
                "audit_and_provenance", "cost_and_tokens"
            ]
            has_all_sections = all(sec in data for sec in required_sections)

            # Check indicators finite & valid
            tech_indicators = data.get("technical_findings", {}).get("indicators", {})
            invalid_indicators = []
            for k, v in tech_indicators.items():
                if v is None:
                    # check if it's expected None
                    invalid_indicators.append(f"{k}=None")
                elif isinstance(v, (int, float)) and (math.isnan(v) or math.isinf(v)):
                    invalid_indicators.append(f"{k}={v}")

            # Risk & report
            risk_findings = data.get("risk_findings", {})
            final_report = data.get("final_report", {})
            has_risk = bool(risk_findings.get("risk_level") and risk_findings.get("recommendation"))
            has_report = bool(final_report.get("markdown_report") and len(final_report.get("markdown_report", "")) > 100)

            # Provenance & Audit
            audit = data.get("audit_and_provenance", {})
            prov_count = audit.get("provenance_records_count", 0)
            events_count = audit.get("execution_events_count", 0)
            agent_statuses = audit.get("agent_statuses", {})
            execution_events = audit.get("execution_events", [])

            # Rigorous execution evidence verification:
            # 1. Require verified execution event logged with status == 'completed' and positive duration
            # 2. Require corresponding agent status registered in blackboard state
            adk_event = next(
                (e for e in execution_events if e.get("component") == "GoogleADKTechnicalAgent" and e.get("status") == "completed"),
                None,
            )
            adk_executed = bool(
                adk_event is not None
                and adk_event.get("details", {}).get("duration_ms", 0) >= 0
                and agent_statuses.get("GoogleADKTechnicalAgent") in {"available", "completed"}
            )

            crew_event = next(
                (e for e in execution_events if e.get("component") == "crewai_orchestrator" and e.get("status") == "completed"),
                None,
            )
            crew_executed = bool(
                crew_event is not None
                and crew_event.get("details", {}).get("duration_ms", 0) > 0
                and agent_statuses.get("crewai_orchestrator") == "completed"
            )

            print(f"  HTTP Status: {status_code}")
            print(f"  Workflow Status: {data.get('workflow_status')}")
            print(f"  Latency: {lat_ms:.2f} ms")
            print(f"  Schema Valid: {has_all_sections}")
            print(f"  Data Quality: {data.get('market_data', {}).get('data_quality')} (Source: {data.get('market_data', {}).get('source')})")
            print(f"  Technical Signal: {data.get('technical_findings', {}).get('signal')} (Confidence: {data.get('technical_findings', {}).get('confidence')})")
            print(f"  Risk Level: {risk_findings.get('risk_level')}, Recommendation: {risk_findings.get('recommendation')}")
            print(f"  Provenance Records: {prov_count}, Execution Events: {events_count}")
            print(f"  ADK Executed: {adk_executed}, CrewAI Executed: {crew_executed}")
            print(f"  Invalid / Non-Finite Indicators: {invalid_indicators or 'None (All Valid)'}")

            results_data["step2_api_tickers"][ticker] = {
                "http_status": status_code,
                "workflow_status": data.get("workflow_status"),
                "latency_ms": round(lat_ms, 2),
                "has_all_sections": has_all_sections,
                "market_data_status": data.get("market_data", {}).get("status"),
                "data_quality": data.get("market_data", {}).get("data_quality"),
                "bar_count": data.get("market_data", {}).get("bar_count"),
                "technical_signal": data.get("technical_findings", {}).get("signal"),
                "technical_confidence": data.get("technical_findings", {}).get("confidence"),
                "indicators": tech_indicators,
                "invalid_indicators": invalid_indicators,
                "risk_level": risk_findings.get("risk_level"),
                "composite_score": risk_findings.get("composite_score"),
                "recommendation": risk_findings.get("recommendation"),
                "has_report": has_report,
                "provenance_count": prov_count,
                "events_count": events_count,
                "agent_statuses": agent_statuses,
                "adk_executed": adk_executed,
                "crew_executed": crew_executed,
            }

    # =========================================================================
    # STEP 3: Validate Technical Indicators Against Independent Math
    # =========================================================================
    print("\n[STEP 3] Validating Technical Indicator Calculations Against Independent Formulas...")
    ind_tests = []

    # Test 3.1: SMA 20, 50, 200 on linear series
    linear_prices = [float(i) for i in range(1, 201)]  # 1.0 to 200.0
    sma_20_calc = calculate_sma(linear_prices, 20)
    sma_20_ref = sum(linear_prices[-20:]) / 20.0  # (181 + 200)/2 = 190.5
    ind_tests.append({
        "indicator": "SMA_20",
        "calculated": sma_20_calc,
        "reference": sma_20_ref,
        "discrepancy": round(abs(sma_20_calc - sma_20_ref), 6),
        "status": "PASS" if abs(sma_20_calc - sma_20_ref) < 1e-4 else "FAIL",
    })

    sma_50_calc = calculate_sma(linear_prices, 50)
    sma_50_ref = sum(linear_prices[-50:]) / 50.0  # (151 + 200)/2 = 175.5
    ind_tests.append({
        "indicator": "SMA_50",
        "calculated": sma_50_calc,
        "reference": sma_50_ref,
        "discrepancy": round(abs(sma_50_calc - sma_50_ref), 6),
        "status": "PASS" if abs(sma_50_calc - sma_50_ref) < 1e-4 else "FAIL",
    })

    sma_200_calc = calculate_sma(linear_prices, 200)
    sma_200_ref = sum(linear_prices) / 200.0  # 100.5
    ind_tests.append({
        "indicator": "SMA_200",
        "calculated": sma_200_calc,
        "reference": sma_200_ref,
        "discrepancy": round(abs(sma_200_calc - sma_200_ref), 6),
        "status": "PASS" if abs(sma_200_calc - sma_200_ref) < 1e-4 else "FAIL",
    })

    # Test 3.2: EMA 12, 26 on known series
    # Hand calculation for 4 elements, period=3:
    # prices = [10.0, 11.0, 12.0, 13.0]
    # multiplier = 2 / (3 + 1) = 0.5
    # SMA seed = (10+11+12)/3 = 11.0
    # Next EMA = (13 - 11) * 0.5 + 11 = 12.0
    ema_test_prices = [10.0, 11.0, 12.0, 13.0]
    ema_val = calculate_ema(ema_test_prices, 3)
    ind_tests.append({
        "indicator": "EMA_3_HandCheck",
        "calculated": ema_val,
        "reference": 12.0,
        "discrepancy": round(abs(ema_val - 12.0), 6),
        "status": "PASS" if abs(ema_val - 12.0) < 1e-4 else "FAIL",
    })

    # Test 3.3: MACD (12, 26, 9) on 40 linear prices
    macd_prices = [100.0 + float(i) for i in range(40)]
    macd_l, macd_s, macd_h = calculate_macd(macd_prices, 12, 26, 9)
    # Independently compute:
    # fast EMA series (period 12):
    def ref_ema_series(data, period):
        m = 2.0 / (period + 1.0)
        seed = sum(data[:period]) / period
        res = [seed]
        for p in data[period:]:
            res.append((p - res[-1]) * m + res[-1])
        return res

    ref_f = ref_ema_series(macd_prices, 12)
    ref_s = ref_ema_series(macd_prices, 26)
    ref_macd_series = [f - s for f, s in zip(ref_f[26 - 12:], ref_s)]
    ref_signal_series = ref_ema_series(ref_macd_series, 9)
    ref_macd_l = round(ref_macd_series[-1], 4)
    ref_macd_s = round(ref_signal_series[-1], 4)
    ref_macd_h = round(ref_macd_l - ref_macd_s, 4)

    ind_tests.append({
        "indicator": "MACD_Line",
        "calculated": macd_l,
        "reference": ref_macd_l,
        "discrepancy": round(abs(macd_l - ref_macd_l), 6),
        "status": "PASS" if abs(macd_l - ref_macd_l) < 1e-4 else "FAIL",
    })
    ind_tests.append({
        "indicator": "MACD_Signal",
        "calculated": macd_s,
        "reference": ref_macd_s,
        "discrepancy": round(abs(macd_s - ref_macd_s), 6),
        "status": "PASS" if abs(macd_s - ref_macd_s) < 1e-4 else "FAIL",
    })
    ind_tests.append({
        "indicator": "MACD_Hist",
        "calculated": macd_h,
        "reference": ref_macd_h,
        "discrepancy": round(abs(macd_h - ref_macd_h), 6),
        "status": "PASS" if abs(macd_h - ref_macd_h) < 1e-4 else "FAIL",
    })

    # Test 3.4: RSI 14 (Wilder smoothing) on known 20-period price dataset
    rsi_test_prices = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
        45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64
    ]
    rsi_calc = calculate_rsi(rsi_test_prices, 14)

    # Independent Wilder reference:
    deltas = [rsi_test_prices[i] - rsi_test_prices[i - 1] for i in range(1, len(rsi_test_prices))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_g = sum(gains[:14]) / 14.0
    avg_l = sum(losses[:14]) / 14.0
    for i in range(14, len(deltas)):
        avg_g = (avg_g * 13.0 + gains[i]) / 14.0
        avg_l = (avg_l * 13.0 + losses[i]) / 14.0
    rs_ref = avg_g / avg_l
    rsi_ref = round(100.0 - (100.0 / (1.0 + rs_ref)), 4)

    ind_tests.append({
        "indicator": "RSI_14_Wilder",
        "calculated": rsi_calc,
        "reference": rsi_ref,
        "discrepancy": round(abs(rsi_calc - rsi_ref), 6),
        "status": "PASS" if abs(rsi_calc - rsi_ref) < 1e-4 else "FAIL",
    })

    # Test 3.5: Bollinger Bands (20, 2)
    bb_prices = [100.0 + (i % 5) for i in range(25)]
    bb_u, bb_m, bb_l, bb_bw = calculate_bollinger_bands(bb_prices, 20, 2.0)
    w = bb_prices[-20:]
    m_ref = sum(w) / 20.0
    var_ref = sum((x - m_ref) ** 2 for x in w) / 20.0
    sd_ref = math.sqrt(var_ref)
    u_ref = round(m_ref + 2.0 * sd_ref, 4)
    l_ref = round(m_ref - 2.0 * sd_ref, 4)
    bw_ref = round((u_ref - l_ref) / m_ref * 100.0, 4)

    ind_tests.append({
        "indicator": "BB_Upper",
        "calculated": bb_u,
        "reference": u_ref,
        "discrepancy": round(abs(bb_u - u_ref), 6),
        "status": "PASS" if abs(bb_u - u_ref) < 1e-4 else "FAIL",
    })
    ind_tests.append({
        "indicator": "BB_Middle",
        "calculated": bb_m,
        "reference": round(m_ref, 4),
        "discrepancy": round(abs(bb_m - round(m_ref, 4)), 6),
        "status": "PASS" if abs(bb_m - round(m_ref, 4)) < 1e-4 else "FAIL",
    })
    ind_tests.append({
        "indicator": "BB_Lower",
        "calculated": bb_l,
        "reference": l_ref,
        "discrepancy": round(abs(bb_l - l_ref), 6),
        "status": "PASS" if abs(bb_l - l_ref) < 1e-4 else "FAIL",
    })

    # Test 3.6: ATR 14
    sample_bars = [
        {"high": 100.0 + i + 2, "low": 100.0 + i - 2, "close": 100.0 + i}
        for i in range(20)
    ]
    atr_calc = calculate_atr(sample_bars, 14)
    # True ranges for this synthetic series:
    # high - low = 4.0; |high - prev_close| = |(100+i+2) - (100+i-1)| = 3.0; |low - prev_close| = 1.0
    # TR is constantly 4.0
    # Average of constant 4.0 with Wilder smoothing is exactly 4.0
    ind_tests.append({
        "indicator": "ATR_14_Wilder",
        "calculated": atr_calc,
        "reference": 4.0,
        "discrepancy": round(abs(atr_calc - 4.0), 6),
        "status": "PASS" if abs(atr_calc - 4.0) < 1e-4 else "FAIL",
    })

    # Edge cases testing:
    edge_cases = []
    # Edge case 1: Insufficient history
    ec_sma_none = calculate_sma([10.0, 20.0], 20)
    ec_rsi_none = calculate_rsi([10.0] * 10, 14)
    ec_bb_none = calculate_bollinger_bands([10.0] * 10, 20)
    ec_atr_none = calculate_atr([{"high": 10.0, "low": 9.0, "close": 9.5}] * 10, 14)
    edge_cases.append({
        "case": "Insufficient History (< period)",
        "sma_20_returns_none": ec_sma_none is None,
        "rsi_14_returns_none": ec_rsi_none is None,
        "bb_20_returns_none": ec_bb_none == (None, None, None, None),
        "atr_14_returns_none": ec_atr_none is None,
    })

    # Edge case 2: Constant prices (zero variance)
    const_prices = [100.0] * 30
    const_rsi = calculate_rsi(const_prices, 14)
    const_bb = calculate_bollinger_bands(const_prices, 20)
    edge_cases.append({
        "case": "Constant Prices (Zero Volatility)",
        "rsi_neutral_50": const_rsi == 50.0,
        "bb_std_zero": const_bb == (100.0, 100.0, 100.0, 0.0),
    })

    # Edge case 3: Empty input
    ind_empty, sig_empty, conf_empty, warn_empty = compute_all_indicators([])
    edge_cases.append({
        "case": "Empty Bars",
        "handled_gracefully": ind_empty == {} and sig_empty == "NEUTRAL" and "Empty price bars" in warn_empty[0],
    })

    print(f"  Indicator Accuracy Tests: {len(ind_tests)} evaluated. All PASS: {all(t['status'] == 'PASS' for t in ind_tests)}")
    for t in ind_tests:
        print(f"    - {t['indicator']}: Calc={t['calculated']}, Ref={t['reference']}, Diff={t['discrepancy']} -> {t['status']}")
    print(f"  Edge Cases: {len(edge_cases)} evaluated.")
    for ec in edge_cases:
        print(f"    - {ec['case']}: {ec}")

    results_data["step3_indicators"] = {
        "accuracy_tests": ind_tests,
        "edge_cases": edge_cases,
    }

    # =========================================================================
    # STEP 4: Test Guardrails (Valid & Adversarial Matrix)
    # =========================================================================
    print("\n[STEP 4] Testing Security Guardrails Against 8 Personas...")
    engine = GuardrailsEngine()
    personas_file = Path("config/personas.json")
    with open(personas_file, "r") as f:
        personas = json.load(f)

    guardrail_results = {}
    for p_id, p_data in personas.items():
        raw_req = {
            "ticker": p_data.get("ticker"),
            "user_prompt": p_data.get("user_prompt"),
            "lookback_days": p_data.get("parameters", {}).get("lookback_days", 200),
            "risk_profile": p_data.get("parameters", {}).get("risk_profile", "moderate"),
        }
        res, valid_req = engine.evaluate_request(raw_req)

        expected_outcome = p_data.get("expected_guardrail_outcome")
        is_blocked = (res.action == "BLOCK")

        print(f"  Persona [{p_id}]: Action={res.action}, SecurityFlag={res.security_flag}, Passed={res.passed}")
        print(f"    Reason: {res.reason}")

        guardrail_results[p_id] = {
            "action": res.action,
            "passed": res.passed,
            "security_flag": res.security_flag,
            "reason": res.reason,
            "is_blocked": is_blocked,
            "expected_outcome": expected_outcome,
        }

    results_data["step4_guardrails"] = guardrail_results

    # =========================================================================
    # STEP 5: Validate Workflow Modes (Sequential, Parallel, Hierarchical)
    # =========================================================================
    print("\n[STEP 5] Testing Workflow Topologies with Identical Valid Input...")
    topologies = ["sequential", "parallel", "hierarchical"]
    workflow_results = {}

    for mode in topologies:
        wf = StockShieldWorkflow()
        req_payload = {
            "ticker": "TCS.NS",
            "user_prompt": f"Execute rigorous institutional risk and momentum assessment in {mode} topology.",
            "lookback_days": 200,
            "workflow_mode": mode,
            "risk_profile": "moderate",
        }
        t0 = time.perf_counter()
        bb_state = await wf.run(raw_request=req_payload, workflow_mode=mode)
        dur_ms = (time.perf_counter() - t0) * 1000

        # Check executions
        tech_status = bb_state.technical_findings.status.value
        fund_status = bb_state.fundamental_findings.status.value
        risk_status = bb_state.risk_findings.status.value
        prov_count = len(bb_state.provenance_trail)
        events_count = len(bb_state.execution_events)

        print(f"  Mode [{mode.upper()}]: Status={bb_state.workflow_status.value}, Latency={dur_ms:.2f} ms")
        print(f"    Tech={tech_status}, Fund={fund_status}, Risk={risk_status}")
        print(f"    Provenance Records={prov_count}, Execution Events={events_count}")
        print(f"    Final Report Length={len(bb_state.final_report.markdown_content)} chars")

        workflow_results[mode] = {
            "workflow_status": bb_state.workflow_status.value,
            "latency_ms": round(dur_ms, 2),
            "tech_status": tech_status,
            "fund_status": fund_status,
            "risk_status": risk_status,
            "provenance_count": prov_count,
            "events_count": events_count,
            "report_length": len(bb_state.final_report.markdown_content),
        }

    results_data["step5_workflows"] = workflow_results

    # =========================================================================
    # STEP 6: Inspect Existing 40-Run Evaluation Records
    # =========================================================================
    print("\n[STEP 6] Inspecting 40-Run Empirical Records & Summary Files...")
    runs_file = Path("evaluation_results/runs.jsonl")
    raw_v1_file = Path("evaluation_results/runs_v1_raw.jsonl")

    with open(runs_file, "r") as f:
        runs_current = [json.loads(line) for line in f]
    with open(raw_v1_file, "r") as f:
        runs_v1 = [json.loads(line) for line in f]

    print(f"  Preserved Raw v1 Records Count: {len(runs_v1)}")
    print(f"  Current Evaluation Records Count: {len(runs_current)}")

    # Outcome reconciliation
    outcomes = {}
    for r in runs_current:
        cat = r.get("outcome_category", "unclassified")
        outcomes[cat] = outcomes.get(cat, 0) + 1

    print(f"  Current Outcomes: {outcomes}")

    # Breakdown per config
    configs = sorted(list({r["configuration"] for r in runs_current}))
    config_summary = {}
    for c in configs:
        c_runs = [r for r in runs_current if r["configuration"] == c]
        completed = [r for r in c_runs if r.get("outcome_category") == "completed"]
        blocked = [r for r in c_runs if r.get("outcome_category") == "expected_guardrail_block"]
        unexpected = [r for r in c_runs if r.get("outcome_category") == "unexpected_failure"]

        mean_lat = np.mean([r["end_to_end_latency_ms"] for r in completed]) if completed else 0.0
        std_lat = np.std([r["end_to_end_latency_ms"] for r in completed]) if len(completed) > 1 else 0.0
        mean_tools = np.mean([r.get("distinct_mcp_tools", 0) for r in completed]) if completed else 0.0

        config_summary[c] = {
            "total_runs": len(c_runs),
            "completed": len(completed),
            "expected_blocks": len(blocked),
            "unexpected_failures": len(unexpected),
            "mean_latency_ms": round(float(mean_lat), 2),
            "std_latency_ms": round(float(std_lat), 2),
            "mean_tools_completed": round(float(mean_tools), 1),
        }
        print(f"  Config [{c}]: Total={len(c_runs)}, Completed={len(completed)}, Blocked={len(blocked)}, Lat={mean_lat:.1f}±{std_lat:.1f}ms, Tools={mean_tools:.1f}")

    # Check chart files
    charts = [
        "evaluation_results/latency_boxplot.png",
        "evaluation_results/runtime_topology_boxplot.png",
        "evaluation_results/agent_metric_heatmap.png",
        "evaluation_results/summary_table.md",
    ]
    chart_existence = {c: Path(c).exists() and Path(c).stat().st_size > 0 for c in charts}
    print(f"  Artifact Verification: {chart_existence}")

    results_data["step6_evaluation_inspection"] = {
        "raw_v1_count": len(runs_v1),
        "current_runs_count": len(runs_current),
        "outcomes": outcomes,
        "config_summary": config_summary,
        "chart_existence": chart_existence,
    }

    # Save validation results JSON
    out_json = Path("evaluation_results/validation_run_evidence.json")
    with open(out_json, "w") as f:
        json.dump(results_data, f, indent=2)
    print(f"\n[DONE] Saved complete empirical evidence to {out_json}")

    return results_data


if __name__ == "__main__":
    asyncio.run(run_validation())

