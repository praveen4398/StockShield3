"""Script to execute the 40-run evaluation and generate all artifacts."""

import asyncio
from stockshield.evaluation.runner import AcademicEvaluationRunner
from stockshield.evaluation.visualizer import EvaluationVisualizer


async def main():
    print("=" * 70)
    print("STOCKSHIELD 2.0 — ACADEMIC EVALUATION EXPERIMENT (40 RUNS)")
    print("=" * 70)

    runner = AcademicEvaluationRunner()
    print("Executing 40 controlled runs across 6 configuration groups...")
    results = await runner.execute_40_runs_matrix()
    print(f"Successfully recorded {len(results)} runs to evaluation_results/runs.jsonl and runs.csv.")

    print("\nGenerating publication artifacts...")
    visualizer = EvaluationVisualizer()
    visualizer.generate_all_artifacts()
    print("Artifact generation completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
