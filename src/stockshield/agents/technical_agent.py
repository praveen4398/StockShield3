"""Google ADK-based Technical Analysis Agent for StockShield 2.0."""

import time
import uuid
from typing import Any, Dict

from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from stockshield.agents.indicators import compute_all_indicators
from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus
from stockshield.llm.adk_stub import ADKDeterministicStubLlm


class GoogleADKTechnicalAgent:
    """Technical Agent powered by Google ADK.

    Computes deterministic technical indicators, extracts momentum signals,
    and publishes findings to the Blackboard with lineage and timing metrics.
    Executes genuine Google ADK Runner lifecycle.
    """

    def __init__(self, name: str = "GoogleADKTechnicalAgent"):
        self.name = name
        self.session_service = InMemorySessionService()
        self.stub_model = ADKDeterministicStubLlm()
        # Initialize official Google ADK Agent instance with custom BaseLlm stub
        self.adk_agent = Agent(
            name=self.name,
            model=self.stub_model,
            instruction=(
                "You are an institutional technical quantitative analyst. Calculate SMA (20, 50, 200), "
                "EMA (12, 26), MACD, RSI (14, Wilder), Bollinger Bands, and ATR (14) with strict mathematical precision."
            ),
        )
        self.runner = Runner(
            agent=self.adk_agent,
            app_name="StockShieldApp",
            session_service=self.session_service,
            auto_create_session=True,
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
        session_id = f"sess_{uuid.uuid4().hex[:8]}"

        await blackboard.log_event(
            component=self.name,
            event_type="agent_start",
            status="running",
            details={"framework": "google-adk", "session_id": session_id},
        )

        # Genuine Google ADK Runner execution
        adk_events = []
        try:
            await self.session_service.create_session(
                app_name="StockShieldApp",
                user_id="stockshield_orchestrator",
                session_id=session_id,
            )
            async for event in self.runner.run_async(
                user_id="stockshield_orchestrator",
                session_id=session_id,
            ):
                adk_events.append(event)
        except Exception as e:
            await blackboard.log_event(
                component=self.name,
                event_type="adk_runner_warning",
                status="warning",
                details={"error": str(e)},
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
        time_horizon = getattr(state, "time_horizon", "short_term")
        raw_bars = [b.model_dump() for b in market_data.bars]
        indicators, signal, confidence, warnings = compute_all_indicators(raw_bars, time_horizon=time_horizon)

        # Build diagnostic summary tailored to investment horizon
        latest_bar = raw_bars[-1]
        summary = (
            f"[Google ADK TechnicalAgent / Runner Session {session_id} / {time_horizon.upper().replace('_', ' ')}] "
            f"Review for {state.ticker}: Close={latest_bar.get('close')} INR, "
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
                "adk_events_count": len(adk_events),
            },
        )
        return {
            "status": "completed",
            "duration_ms": duration_ms,
            "signal": signal,
            "confidence": confidence,
            "indicators": indicators,
            "adk_events_count": len(adk_events),
        }
