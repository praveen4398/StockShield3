"""Standardized predefined scenario definitions for StockShield 2.0.

Provides standard definitions across price shocks, volatility shocks, news sentiment
scenarios, technical trend transitions, and combined macro market stress scenarios.
"""

from typing import Dict, List, Optional

from stockshield.simulation.models import (
    ScenarioCategory,
    ScenarioDefinition,
    TechnicalTrendShock,
)

PREDEFINED_SCENARIOS: List[ScenarioDefinition] = [
    # -------------------------------------------------------------
    # Category A: Price Shock Scenarios
    # -------------------------------------------------------------
    ScenarioDefinition(
        name="Price Drop 5%",
        category=ScenarioCategory.PRICE_SHOCK,
        description="Hypothetical 5% single-phase equity price decline.",
        price_shock_pct=-5.0,
    ),
    ScenarioDefinition(
        name="Price Drop 10%",
        category=ScenarioCategory.PRICE_SHOCK,
        description="Hypothetical 10% substantial equity price contraction.",
        price_shock_pct=-10.0,
    ),
    ScenarioDefinition(
        name="Price Drop 15%",
        category=ScenarioCategory.PRICE_SHOCK,
        description="Hypothetical 15% severe equity price drawdown.",
        price_shock_pct=-15.0,
    ),
    ScenarioDefinition(
        name="Price Gain 5%",
        category=ScenarioCategory.PRICE_SHOCK,
        description="Hypothetical 5% upward price appreciation.",
        price_shock_pct=5.0,
    ),
    ScenarioDefinition(
        name="Price Gain 10%",
        category=ScenarioCategory.PRICE_SHOCK,
        description="Hypothetical 10% strong bullish price advance.",
        price_shock_pct=10.0,
    ),
    # -------------------------------------------------------------
    # Category B: Volatility Shock Scenarios
    # -------------------------------------------------------------
    ScenarioDefinition(
        name="Volatility Increase 25%",
        category=ScenarioCategory.VOLATILITY_SHOCK,
        description="Hypothetical 25% expansion in annualized return volatility.",
        volatility_shock_pct=25.0,
    ),
    ScenarioDefinition(
        name="Volatility Increase 50%",
        category=ScenarioCategory.VOLATILITY_SHOCK,
        description="Hypothetical 50% sharp expansion in market volatility.",
        volatility_shock_pct=50.0,
    ),
    ScenarioDefinition(
        name="Volatility Doubling (100%)",
        category=ScenarioCategory.VOLATILITY_SHOCK,
        description="Hypothetical 100% doubling in equity price dispersion and volatility.",
        volatility_shock_pct=100.0,
    ),
    ScenarioDefinition(
        name="Volatility Decrease 25%",
        category=ScenarioCategory.VOLATILITY_SHOCK,
        description="Hypothetical 25% volatility contraction (calm market regime).",
        volatility_shock_pct=-25.0,
    ),
    # -------------------------------------------------------------
    # Category C: News Sentiment Scenarios
    # -------------------------------------------------------------
    ScenarioDefinition(
        name="Strongly Positive Sentiment",
        category=ScenarioCategory.NEWS_SENTIMENT,
        description="Hypothetical media environment with strongly bullish narrative consensus (+0.80).",
        sentiment_score=0.80,
    ),
    ScenarioDefinition(
        name="Neutral Sentiment",
        category=ScenarioCategory.NEWS_SENTIMENT,
        description="Hypothetical balanced or absent media headlines (0.00 score).",
        sentiment_score=0.0,
    ),
    ScenarioDefinition(
        name="Moderately Negative Sentiment",
        category=ScenarioCategory.NEWS_SENTIMENT,
        description="Hypothetical media environment with adverse operational or earnings reports (-0.50 score).",
        sentiment_score=-0.50,
    ),
    ScenarioDefinition(
        name="Strongly Negative Sentiment",
        category=ScenarioCategory.NEWS_SENTIMENT,
        description="Hypothetical media environment with severe adverse headlines or corporate scrutiny (-0.90 score).",
        sentiment_score=-0.90,
    ),
    # -------------------------------------------------------------
    # Category D: Technical Trend Scenarios
    # -------------------------------------------------------------
    ScenarioDefinition(
        name="Bullish-to-Neutral Transition",
        category=ScenarioCategory.TECHNICAL_TREND,
        description="Hypothetical loss of upward momentum transitioning into trend consolidation.",
        technical_trend=TechnicalTrendShock.BULLISH_TO_NEUTRAL,
    ),
    ScenarioDefinition(
        name="Neutral-to-Bearish Transition",
        category=ScenarioCategory.TECHNICAL_TREND,
        description="Hypothetical breakdown from consolidation into downward trend structure.",
        technical_trend=TechnicalTrendShock.NEUTRAL_TO_BEARISH,
    ),
    ScenarioDefinition(
        name="Price Falling Below SMA-20",
        category=ScenarioCategory.TECHNICAL_TREND,
        description="Hypothetical price breach below short-term 20-day moving average.",
        technical_trend=TechnicalTrendShock.BREAK_BELOW_SMA20,
    ),
    ScenarioDefinition(
        name="Price Falling Below SMA-50",
        category=ScenarioCategory.TECHNICAL_TREND,
        description="Hypothetical price breach below intermediate 50-day moving average.",
        technical_trend=TechnicalTrendShock.BREAK_BELOW_SMA50,
    ),
    ScenarioDefinition(
        name="Price Falling Below SMA-200",
        category=ScenarioCategory.TECHNICAL_TREND,
        description="Hypothetical structural breakdown below long-term 200-day moving average benchmark.",
        technical_trend=TechnicalTrendShock.BREAK_BELOW_SMA200,
    ),
    # -------------------------------------------------------------
    # Category E: Combined Market Stress Scenarios
    # -------------------------------------------------------------
    ScenarioDefinition(
        name="Mild Correction",
        category=ScenarioCategory.COMBINED_STRESS,
        description="Standard market pullback: 5% price drop, 25% volatility uptick, and moderately negative media narrative.",
        price_shock_pct=-5.0,
        volatility_shock_pct=25.0,
        sentiment_score=-0.50,
        technical_trend=TechnicalTrendShock.BULLISH_TO_NEUTRAL,
    ),
    ScenarioDefinition(
        name="Market Downturn",
        category=ScenarioCategory.COMBINED_STRESS,
        description="Substantial cyclical contraction: 10% price decline, 50% volatility increase, strongly negative media, and bearish trend.",
        price_shock_pct=-10.0,
        volatility_shock_pct=50.0,
        sentiment_score=-0.80,
        technical_trend=TechnicalTrendShock.NEUTRAL_TO_BEARISH,
    ),
    ScenarioDefinition(
        name="Severe Market Crash",
        category=ScenarioCategory.COMBINED_STRESS,
        description="Systemic shock scenario: 15% severe crash, volatility doubles (+100%), adverse media headline crisis (-1.00), and breach below SMA-200.",
        price_shock_pct=-15.0,
        volatility_shock_pct=100.0,
        sentiment_score=-1.00,
        technical_trend=TechnicalTrendShock.BREAK_BELOW_SMA200,
    ),
    ScenarioDefinition(
        name="Bullish Recovery",
        category=ScenarioCategory.COMBINED_STRESS,
        description="V-shaped recovery: 10% price advance, 25% volatility contraction, strongly positive media (+0.80), and bullish trend reclaim.",
        price_shock_pct=10.0,
        volatility_shock_pct=-25.0,
        sentiment_score=0.80,
        technical_trend=TechnicalTrendShock.BULLISH_RECOVERY,
    ),
    ScenarioDefinition(
        name="High Volatility Without Price Decline",
        category=ScenarioCategory.COMBINED_STRESS,
        description="Turbulence without directional bias: volatility doubles (+100%) while price and sentiment remain at neutral baseline.",
        price_shock_pct=0.0,
        volatility_shock_pct=100.0,
        sentiment_score=0.0,
        technical_trend=TechnicalTrendShock.NONE,
    ),
]

_SCENARIO_LOOKUP: Dict[str, ScenarioDefinition] = {
    s.name.lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace("%", "pct"): s
    for s in PREDEFINED_SCENARIOS
}
# Also index by exact name lowercase
for s in PREDEFINED_SCENARIOS:
    _SCENARIO_LOOKUP[s.name.lower()] = s


def get_predefined_scenarios() -> List[ScenarioDefinition]:
    """Retrieve complete list of all predefined standard scenarios."""
    return list(PREDEFINED_SCENARIOS)


def get_combined_stress_scenarios() -> List[ScenarioDefinition]:
    """Retrieve only the 5 combined market stress scenarios."""
    return [s for s in PREDEFINED_SCENARIOS if s.category == ScenarioCategory.COMBINED_STRESS]


def get_predefined_scenario_by_name(identifier: str) -> Optional[ScenarioDefinition]:
    """Find a predefined scenario by name or normalized slug."""
    if not identifier:
        return None
    cleaned = identifier.lower().strip()
    if cleaned in _SCENARIO_LOOKUP:
        return _SCENARIO_LOOKUP[cleaned]

    norm = cleaned.replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "").replace("%", "pct")
    return _SCENARIO_LOOKUP.get(norm)

