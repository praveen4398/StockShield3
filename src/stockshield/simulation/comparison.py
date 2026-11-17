"""Baseline-versus-Scenario Comparison and Tabular Reporting for StockShield 2.0."""

from typing import List

from stockshield.simulation.models import BaselineMetrics, ScenarioResult


def generate_scenario_comparison_table_md(scenarios: List[ScenarioResult]) -> str:
    """Generate a clean Markdown table summarizing stress test results."""
    if not scenarios:
        return "_No scenarios simulated._"

    headers = [
        "Scenario Name",
        "Category",
        "Price Shock",
        "Sim Price",
        "Vol Adj",
        "Sent Score",
        "Risk Score",
        "Risk Level",
        "Recommendation",
        "Delta vs Base",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join([":---"] * len(headers)) + " |",
    ]

    for s in scenarios:
        sim = s.simulated
        comp = s.comparison
        delta_str = f"{comp.risk_score_delta:+.3f}"
        if comp.material_risk_increase:
            delta_str += " ⚠️"

        row = [
            s.scenario_name,
            s.category.value,
            f"{sim.percentage_price_change:+.1f}%",
            f"{sim.hypothetical_price:.2f}",
            f"{sim.hypothetical_volatility_pct:.1f}%",
            f"{sim.hypothetical_sentiment_score:+.2f}",
            f"{sim.scenario_risk_score:.3f}",
            sim.scenario_risk_level,
            sim.scenario_recommendation,
            delta_str,
        ]
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def format_baseline_summary_md(baseline: BaselineMetrics) -> str:
    """Generate a clean Markdown overview of baseline state."""
    return (
        f"- **Current Stock Price:** `{baseline.stock_price:.2f}`\n"
        f"- **Historical Return Volatility:** `{baseline.volatility_pct:.2f}%` (annualized)\n"
        f"- **Media News Sentiment:** `{baseline.news_sentiment_label}` (Score: {baseline.news_sentiment_score:+.2f})\n"
        f"- **Technical Quantitative Signal:** `{baseline.technical_signal}`\n"
        f"- **Baseline Composite Risk:** `{baseline.composite_risk_score:.3f}` ({baseline.risk_level})\n"
        f"- **Baseline Recommendation:** `{baseline.recommendation}`"
    )

