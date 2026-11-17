"""Core service layer coordinating GENI retrieval, conversation, and generation."""

from typing import List, Optional

from stockshield.geni.client import GeniClient
from stockshield.geni.context_builder import (
    AnalysisFailedError,
    AnalysisInconsistentError,
    AnalysisNotReadyError,
    GeniContextBuilder,
    RunNotFoundError,
)
from stockshield.geni.conversation_manager import (
    ConversationNotFoundError,
    ConversationRunMismatchError,
    GeniConversationManager,
)
from stockshield.geni.models import (
    GeniChatRequest,
    GeniChatResponse,
    MessageRole,
)


class GeniService:
    """Coordinates analysis evidence grounding, conversation persistence, and LLM responses."""

    def __init__(
        self,
        context_builder: Optional[GeniContextBuilder] = None,
        conversation_manager: Optional[GeniConversationManager] = None,
        client: Optional[GeniClient] = None,
    ):
        self.context_builder = context_builder or GeniContextBuilder()
        self.conversation_manager = conversation_manager or GeniConversationManager()
        self.client = client or GeniClient()

    def _determine_sources_used(self, message: str, available_sources: List[str]) -> List[str]:
        """Detect which analysis domains are actively relevant to the user's question."""
        lower_msg = message.lower()
        matched: List[str] = []

        mapping = {
            "technical_analysis": ["rsi", "macd", "sma", "ema", "moving average", "bollinger", "atr", "technical", "indicator", "momentum", "bullish", "bearish"],
            "risk_assessment": ["risk", "drawdown", "gate", "recommendation", "approved", "rejected", "caution", "safety", "composite"],
            "news_and_sentiment": ["news", "sentiment", "headline", "article", "media", "event", "coverage"],
            "forecasting": ["forecast", "arima", "lightgbm", "exponential", "prediction", "projected", "accuracy", "rmse", "mae", "horizon", "target"],
            "scenario_simulation": ["scenario", "stress", "crash", "monte carlo", "p5", "p50", "p95", "simulation", "worst-case", "shock", "probability of loss"],
            "overall_analysis": ["price", "close", "data", "source", "yahoo", "ticker", "stock", "overview", "summary"],
        }

        for domain, keywords in mapping.items():
            if domain in available_sources:
                if any(k in lower_msg for k in keywords):
                    matched.append(domain)

        # Default to available sources if the question is general or comprehensive
        return matched if matched else available_sources

    def ask(self, request: GeniChatRequest) -> GeniChatResponse:
        """Process an inbound question, maintain conversation state, and return a grounded response."""
        # 1. Retrieve structured analysis context (validates run existence & completion status)
        context_markdown, available_sources, ticker = self.context_builder.build_context(request.run_id)

        # 2. Resolve or initialize conversation thread (enforces run ownership & anti-hijacking)
        if request.conversation_id:
            conv_info = self.conversation_manager.validate_conversation_for_run(
                conversation_id=request.conversation_id,
                expected_run_id=request.run_id,
            )
            conv_id = conv_info.conversation_id
        else:
            conv_info = self.conversation_manager.create_conversation(
                run_id=request.run_id,
                ticker=ticker,
            )
            conv_id = conv_info.conversation_id

        # 3. Fetch prior conversation history
        chat_history = self.conversation_manager.get_messages(conv_id, limit=10)

        # 4. Determine relevant sources based on the user question
        sources_used = self._determine_sources_used(request.message, available_sources)

        # 5. Record user message turn in persistence store
        self.conversation_manager.add_message(
            conversation_id=conv_id,
            role=MessageRole.USER,
            content=request.message,
            sources_used=sources_used,
        )

        # 6. Call Gemini LLM client
        reply_text, meta = self.client.generate_chat_reply(
            analysis_context=context_markdown,
            user_message=request.message,
            chat_history=chat_history,
        )

        status = meta.get("status", "success")
        error_msg = meta.get("error")

        if status == "success" and reply_text:
            final_reply = reply_text
        elif status == "rate_limited":
            final_reply = (
                "The Gemini API daily quota or rate limit has been reached (HTTP 429). "
                "The verified StockShield analysis for this stock remains completely intact and available in your report. "
                "Please wait for quota replenishment before asking further questions."
            )
        elif status == "not_configured":
            final_reply = (
                "GENI is currently unavailable because the GEMINI_API_KEY environment variable is not configured on the server."
            )
        elif status == "auth_failed":
            final_reply = (
                "GENI encountered an authentication error while contacting the Gemini API. "
                "Please verify that the configured GEMINI_API_KEY is valid."
            )
        elif status in {"timeout", "unavailable"}:
            final_reply = (
                f"GENI was unable to retrieve a model response due to a temporary upstream service timeout ({error_msg}). "
                "Please try asking your question again in a moment."
            )
        else:
            final_reply = (
                f"GENI encountered an unexpected error processing your request: {error_msg or 'Unknown error'}."
            )

        # 7. Record assistant message turn in persistence store
        self.conversation_manager.add_message(
            conversation_id=conv_id,
            role=MessageRole.ASSISTANT,
            content=final_reply,
            sources_used=sources_used,
            metadata=meta,
        )

        # 8. Return response payload
        return GeniChatResponse(
            run_id=request.run_id,
            conversation_id=conv_id,
            assistant_name="GENI",
            response=final_reply,
            status=status,
            sources_used=sources_used,
            model_used=meta.get("actual_model"),
            error=error_msg,
        )


__all__ = [
    "GeniService",
    "RunNotFoundError",
    "AnalysisNotReadyError",
    "AnalysisFailedError",
    "AnalysisInconsistentError",
    "ConversationNotFoundError",
    "ConversationRunMismatchError",
]
