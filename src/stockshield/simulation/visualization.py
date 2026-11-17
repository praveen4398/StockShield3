"""Visualization utilities for Scenario Simulation in StockShield 2.0."""

from pathlib import Path
from typing import List, Optional

import matplotlib

matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt

from stockshield.simulation.models import ScenarioResult


def generate_scenario_risk_chart(
    scenarios: List[ScenarioResult],
    baseline_risk_score: float,
    ticker: str = "EQUITY",
    output_path: Optional[str] = None,
) -> Optional[str]:
    """Generate a horizontal bar chart comparing scenario risk against baseline.

    Parameters:
        scenarios: List of evaluated ScenarioResult objects.
        baseline_risk_score: Baseline composite risk score.
        ticker: Target stock symbol.
        output_path: File path to save the chart image (PNG).

    Returns:
        The output path string if generated successfully, else None.
    """
    if not scenarios:
        return None

    # Sort scenarios by risk score ascending
    sorted_scens = sorted(scenarios, key=lambda s: s.simulated.scenario_risk_score)
    names = [s.scenario_name for s in sorted_scens]
    scores = [s.simulated.scenario_risk_score for s in sorted_scens]

    colors = []
    for s in sorted_scens:
        score = s.simulated.scenario_risk_score
        if score >= 0.65:
            colors.append("#d9534f")  # Red / High risk
        elif score >= 0.35:
            colors.append("#f0ad4e")  # Amber / Moderate
        else:
            colors.append("#5cb85c")  # Green / Low

    fig, ax = plt.subplots(figsize=(10, max(6, len(names) * 0.35)))
    y_pos = range(len(names))

    ax.barh(y_pos, scores, color=colors, alpha=0.85, height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Simulated Composite Risk Score (Scale: 0.0 Safe — 1.0 Critical)", fontsize=9)
    ax.set_xlim(0.0, 1.0)

    # Reference lines
    ax.axvline(baseline_risk_score, color="blue", linestyle="--", linewidth=1.5, label=f"Baseline Risk ({baseline_risk_score:.3f})")
    ax.axvline(0.35, color="orange", linestyle=":", linewidth=1, alpha=0.7, label="Caution Threshold (0.35)")
    ax.axvline(0.65, color="red", linestyle=":", linewidth=1, alpha=0.7, label="High Risk Boundary (0.65)")

    ax.set_title(f"StockShield 2.0: Hypothetical Scenario Risk Stress Test — {ticker}\n[CONTROLLED STRESS SIMULATION ONLY — NOT STATISTICAL PREDICTION]", fontsize=10, fontweight="bold")
    ax.legend(loc="lower right", fontsize=8)
    plt.tight_layout()

    if output_path is None:
        save_dir = Path("reports")
        save_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(save_dir / f"scenario_stress_{ticker.replace('.', '_')}.png")

    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path

