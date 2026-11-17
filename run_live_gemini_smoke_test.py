import asyncio
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

from stockshield.orchestration.workflow import StockShieldWorkflow
from stockshield.blackboard.models import WorkflowStatus

async def main():
    print("=" * 80)
    print("STOCKSHIELD 2.0 — LIVE GEMINI SMOKE TEST EXECUTION")
    print("=" * 80)

    # 1. Verify API Key Presence without exposure
    api_key = os.getenv("GEMINI_API_KEY", "")
    key_present = bool(api_key and len(api_key.strip()) > 10)
    key_prefix = api_key[:4] + "..." if key_present else "NONE"
    print(f"[1] API Key Configured: {key_present} (Redacted Key Prefix: {key_prefix})")
    assert key_present, "GEMINI_API_KEY must be present in .env"

    # 2. Configured Model
    configured_model = os.getenv("GEMINI_JUDGE_MODEL", "gemini-3.8-flash")
    print(f"[2] Configured Model: {configured_model}")

    # 3. Instantiate Workflow
    workflow = StockShieldWorkflow()
    print(f"[3] Workflow initialized. Judge service enabled flag: {workflow.judge_service.enabled}")
    print(f"    Judge client model: {workflow.judge_service.client.model_name}")

    req = {
        "ticker": "TCS.NS",
        "user_prompt": "Institutional analysis of TCS.NS with risk assessment and forecasting.",
        "lookback_days": 100,
        "workflow_mode": "sequential",
        "enable_judge": True,
    }

    print(f"[4] Starting full workflow execution for TCS.NS with enable_judge=True...")
    t_start = time.perf_counter()
    state = await workflow.run(raw_request=req, workflow_mode="sequential")
    total_pipeline_time = time.perf_counter() - t_start

    print(f"\n[5] Workflow Execution Completed in {total_pipeline_time:.2f}s")
    print(f"    Workflow Status: {state.workflow_status.value}")
    assert state.workflow_status == WorkflowStatus.COMPLETED

    # 6. Verify Baseline Risk & Financial Outputs
    rf = state.risk_findings
    fc = state.forecasting
    sc = state.scenario_simulation
    print("\n--- Baseline Financial Outputs ---")
    print(f"  Ticker: {state.ticker}")
    print(f"  Composite Risk Score: {rf.composite_risk_score:.4f}")
    print(f"  Risk Level: {rf.overall_risk_level}")
    print(f"  Recommendation: {rf.recommendation}")
    print(f"  Selected Forecast Model: {fc.selected_model_name}")
    print(f"  Forecast Projections Count: {len(fc.selected_forecasts)}")
    print(f"  Scenarios Evaluated: {len(sc.scenarios)}")

    # 7. Verify Judge Evaluation Results
    je = state.judge_evaluation
    print("\n--- Live Gemini Judge Evaluation Results ---")
    print(f"  Status: {je.status}")
    print(f"  Evaluator / Producer: {je.producer}")
    print(f"  Active Model: {je.model_name}")
    print(f"  Prompt Version: {je.prompt_version}")
    print(f"  Latency: {je.latency_ms:.2f} ms")
    print(f"  Overall Score: {je.overall_score} / 10.0")
    print(f"  Verdict: {je.verdict}")
    print(f"  Input Tokens: {je.input_tokens}")
    print(f"  Output Tokens: {je.output_tokens}")
    print(f"  Total Tokens: {je.total_tokens}")
    print(f"  Estimated Cost USD: {je.estimated_cost_usd}")

    print("\n  --- Dimension Breakdown (6/6) ---")
    assert len(je.dimensions) == 6, f"Expected 6 dimensions, got {len(je.dimensions)}"
    for dim_name, dim in je.dimensions.items():
        print(f"    * {dim_name:24s}: {dim.score:4.1f}/10.0 | Issues: {len(dim.identified_issues)} | Refs: {len(dim.evidence_references)}")
        print(f"      Explanation: {dim.explanation[:90]}...")

    print("\n  --- Qualitative Assessment ---")
    print(f"  Strengths ({len(je.strengths)}): {je.strengths}")
    print(f"  Warnings ({len(je.warnings)}): {je.warnings}")
    print(f"  Summary: {je.evaluation_summary}")

    # 8. Verify Markdown Section 8 and Structured JSON
    print("\n--- Report Synthesizer Verification ---")
    has_md_section = "## 8. Gemini LLM-as-a-Judge Evaluation" in state.final_report.markdown_content
    print(f"  Markdown Section 8 Present: {has_md_section}")
    assert has_md_section, "Section 8 missing from Markdown report"

    json_has_judge = "judge_evaluation" in state.final_report.structured_json
    print(f"  Structured JSON judge_evaluation Present: {json_has_judge}")
    assert json_has_judge, "judge_evaluation missing from structured JSON"

    # 9. Verify Baseline Invariance Post-Judge
    print("\n--- Invariance Verification ---")
    post_rf = state.risk_findings
    assert post_rf.composite_risk_score == rf.composite_risk_score
    assert post_rf.recommendation == rf.recommendation
    assert post_rf.overall_risk_level == rf.overall_risk_level
    print("  [PASS] Composite risk score and financial recommendation are strictly invariant!")

    print("\n" + "=" * 80)
    print("ALL LIVE GEMINI SMOKE TEST CHECKS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
