"""Google ADK-based Technical Analysis Agent for StockShield 2.0."""

import time
from typing import Any, Dict

from google.adk import Agent

from stockshield.agents.indicators import compute_all_indicators
from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus


class GoogleADKTechnicalAgent:
    """Technical Agent powered by Google ADK.

    Computes deterministic technical indicators, extracts momentum signals,
    and publishes findings to the Blackboard with lineage and timing metrics.
    """

    def __init__(self, name: str = "GoogleADKTechnicalAgent"):
        self.name = name
        # Initialize official Google ADK Agent instance
        self.adk_agent = Agent(
            name=self.name,
            instruction=(
                "You are an institutional technical quantitative analyst. Calculate SMA (20, 50, 200), "
                "EMA (12, 26), MACD, RSI (14, Wilder), Bollinger Bands, and ATR (14) with strict mathematical precision."
            ),
        )

    def get_agent_card(self) -> Dict[str, Any]:
        """A2A protocol AgentCard defining agent capabilities and endpoints."""
        return {
            "name": self.name,
            "version": "2.0.0",
            "framework": "Google ADK (google-adk 2.13.0)",
            "role": "technical_quantitative_analyst",
            "capabilities": [
                "sma_20_50_200",
                "ema_12_26",
                "macd_12_26_9",
                "rsi_14_wilder",
                "bollinger_bands_20_2",
                "atr_14_wilder",
                "momentum_trend_scoring",
            ],
            "input_schema": {
                "ticker": "string",
                "bars": "array of OHLCV objects with adjusted_close",
            },
            "output_schema": "stockshield.blackboard.models.TechnicalFindingsState",
            "protocol": "A2A/1.0",
            "endpoints": {
                "tasks": "/a2a/tasks",
                "card": "/.well-known/agent.json",
            },
        }

    async def execute(self, blackboard: BlackboardManager) -> Dict[str, Any]:
        """Execute technical analysis step using market data present on the blackboard."""
        start_time = time.perf_counter()
        await blackboard.log_event(
            component=self.name,
            event_type="agent_start",
            status="running",
            details={"framework": "google-adk"},
        )

        state = await blackboard.get_state_snapshot()
        market_data = state.market_data

        if market_data.status != FindingStatus.AVAILABLE or not market_data.bars:
            err_msg = f"Cannot run TechnicalAgent: market_data status is {market_data.status.value}"
            await blackboard.update_technical_findings(
                producer=self.name,
                indicators={},
                signal="NEUTRAL",
                signal_confidence=0.0,
                summary=err_msg,
                lookback_periods_used=0,
                warnings=[err_msg],
                status=FindingStatus.UNAVAILABLE,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            await blackboard.log_event(
                component=self.name,
                event_type="agent_complete",
                status="unavailable",
                details={"duration_ms": duration_ms, "reason": err_msg},
            )
            return {"status": "unavailable", "duration_ms": duration_ms}

        # Convert bars to dicts
        raw_bars = [b.model_dump() for b in market_data.bars]
        indicators, signal, confidence, warnings = compute_all_indicators(raw_bars)

        # Build diagnostic summary
        latest_bar = raw_bars[-1]
        summary = (
            f"Technical review for {state.ticker}: Close={latest_bar.get('close')} INR, "
            f"SMA-20={indicators.get('sma_20')}, SMA-50={indicators.get('sma_50')}, "
            f"SMA-200={indicators.get('sma_200')}, RSI-14={indicators.get('rsi_14')}, "
            f"MACD Hist={indicators.get('macd_hist')}. Overall signal: {signal} ({int(confidence * 100)}% confidence)."
        )

        await blackboard.update_technical_findings(
            producer=self.name,
            indicators=indicators,
            signal=signal,
            signal_confidence=confidence,
            summary=summary,
            lookback_periods_used=len(raw_bars),
            warnings=warnings,
            status=FindingStatus.AVAILABLE,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000
        await blackboard.log_event(
            component=self.name,
            event_type="agent_complete",
            status="completed",
            details={
                "duration_ms": duration_ms,
                "signal": signal,
                "confidence": confidence,
                "bars_analyzed": len(raw_bars),
            },
        )
        return {
            "status": "completed",
            "duration_ms": duration_ms,
            "signal": signal,
            "confidence": confidence,
            "indicators": indicators,
        }
