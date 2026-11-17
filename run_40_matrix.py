"""Entry point script to execute the pure multi-agent 40-run evaluation matrix and generate artifacts."""

import argparse
import asyncio
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "src")

from stockshield.evaluation.runner import AcademicEvaluationRunner
from stockshield.evaluation.visualizer import EvaluationVisualizer


async def main():
    parser = argparse.ArgumentParser(description="StockShield 2.0 40-Run Evaluation Matrix Entrypoint")
    parser.add_argument(
        "--experiment-id",
        type=str,
        default=None,
        help="Isolated experiment identifier. If omitted, a unique timestamped ID is generated.",
    )
    args = parser.parse_args()

    exp_id = args.experiment_id or f"exp_40run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    print("=" * 80)
    print("StockShield 2.0 Academic Pure Multi-Agent Evaluation Matrix")
    print(f"Isolated Experiment ID: {exp_id}")
    print("=" * 80)
    t0 = time.perf_counter()

    runner = AcademicEvaluationRunner(experiment_id=exp_id)

    # Phase 1: 40 Controlled Workflow Runs (36 Architecture + 4 Callback Ablation)
    print("\n[Phase 1/4] Executing 40 Controlled Workflow Runs...")
    results = await runner.execute_40_runs_matrix()
    elapsed_wf = time.perf_counter() - t0
    print(f"Phase 1 Complete: {len(results)} full workflow runs in {elapsed_wf:.2f}s.")

    # Phase 2: Post-Hoc Gemini Judge Evaluations (5 Representative Runs)
    print("\n[Phase 2/4] Executing 5 Post-Hoc Gemini Judge Evaluations...")
    judge_results = await runner.execute_gemini_judge_post_hoc(results)
    print(f"Phase 2 Complete: {len(judge_results)} judge evaluations completed.")

    # Phase 3: Security Benchmark Battery (8 Isolated Tests)
    print("\n[Phase 3/4] Executing 8 Security Benchmark Tests...")
    security_results = runner.execute_security_benchmark()
    print(f"Phase 3 Complete: {len(security_results)} security test cases evaluated.")

    # Phase 4: Visual and Statistical Artifact Generation (Filtered strictly to this experiment)
    print(f"\n[Phase 4/4] Generating Academic Visualizations and Statistical Tables (Filtered to {exp_id})...")
    visualizer = EvaluationVisualizer(experiment_id=exp_id)
    visualizer.generate_all_artifacts()

    total_time = time.perf_counter() - t0
    print("=" * 80)
    print(f"ALL EVALUATION ARTIFACTS GENERATED SUCCESSFULLY FOR {exp_id} IN {total_time:.2f}s!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

