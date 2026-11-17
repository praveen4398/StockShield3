"""News and Sentiment Agent for StockShield 2.0.

Collects financial news for target Indian equity tickers, performs deterministic
sentiment classification, identifies corporate/regulatory events, and commits
findings with full provenance and timing metrics to the Blackboard.
"""

import time
from typing import Any, Dict, Optional

from stockshield.blackboard.blackboard import BlackboardManager
from stockshield.blackboard.models import FindingStatus
from stockshield.news.retriever import NewsRetriever
from stockshield.news.sentiment import DeterministicFinancialSentimentAnalyzer


class NewsSentimentAgent:
    """Agent that retrieves and analyzes news sentiment for Indian equities."""

    def __init__(
        self,
        name: str = "NewsSentimentAgent",
        retriever: Optional[NewsRetriever] = None,
        analyzer: Optional[DeterministicFinancialSentimentAnalyzer] = None,
    ):
        self.name = name
        self.retriever = retriever or NewsRetriever()
        self.analyzer = analyzer or DeterministicFinancialSentimentAnalyzer()

    async def execute(
        self,
        blackboard: BlackboardManager,
        provider_mode: str = "auto",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Execute news retrieval and sentiment analysis lifecycle step."""
        start_time = time.perf_counter()

        await blackboard.log_event(
            component=self.name,
            event_type="agent_start",
            status="running",
            details={"provider_mode": provider_mode, "limit": limit},
        )

        state = await blackboard.get_state_snapshot()
        ticker = state.ticker

        if not ticker or ticker == "UNKNOWN":
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = "Cannot execute NewsSentimentAgent: ticker is missing or UNKNOWN."
            await blackboard.update_news_sentiment(
                producer=self.name,
                total_articles=0,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                overall_sentiment="UNKNOWN",
                sentiment_score=0.0,
                warnings=[err_msg],
                status=FindingStatus.FAILED,
                notes=err_msg,
            )
            await blackboard.log_event(
                component=self.name,
                event_type="agent_complete",
                status="failed",
                details={"duration_ms": duration_ms, "error": err_msg},
            )
            return {"status": "failed", "duration_ms": duration_ms, "error": err_msg}

        # Retrieve news articles
        try:
            articles, retrieval_warnings = self.retriever.fetch_news(
                ticker=ticker,
                limit=limit,
                provider_mode=provider_mode,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"News retrieval exception: {str(e)}"
            await blackboard.update_news_sentiment(
                producer=self.name,
                total_articles=0,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                overall_sentiment="UNKNOWN",
                sentiment_score=0.0,
                warnings=[err_msg],
                status=FindingStatus.UNAVAILABLE,
                notes=err_msg,
            )
            await blackboard.log_event(
                component=self.name,
                event_type="agent_complete",
                status="unavailable",
                details={"duration_ms": duration_ms, "warning": err_msg},
            )
            return {"status": "unavailable", "duration_ms": duration_ms, "warning": err_msg}

        if not articles:
            duration_ms = (time.perf_counter() - start_time) * 1000
            warn = retrieval_warnings or ["No news articles available for ticker."]
            has_error = any(
                term in " ".join(warn).lower()
                for term in ["network error", "timed out", "http error", "failure", "dns", "disabled", "exception"]
            )
            status_finding = (
                FindingStatus.UNAVAILABLE if (provider_mode == "fixture" or has_error) else FindingStatus.AVAILABLE
            )
            await blackboard.update_news_sentiment(
                producer=self.name,
                total_articles=0,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                overall_sentiment="NEUTRAL",
                sentiment_score=0.0,
                articles=[],
                positive_events=[],
                negative_events=[],
                risk_observations=["No recent news articles identified for ticker."],
                warnings=warn,
                status=status_finding,
                notes="Zero articles retrieved; marked neutral baseline.",
            )
            await blackboard.log_event(
                component=self.name,
                event_type="agent_complete",
                status="completed" if status_finding == FindingStatus.AVAILABLE else "unavailable",
                details={"duration_ms": duration_ms, "articles_count": 0},
            )
            return {
                "status": status_finding.value,
                "duration_ms": duration_ms,
                "total_articles": 0,
                "overall_sentiment": "NEUTRAL",
            }

        # Analyze corpus
        result = self.analyzer.analyze_corpus(articles, ticker, retrieval_warnings)

        time_horizon = getattr(state, "time_horizon", "short_term")
        horizon_note = (
            "Short-term news weighting: high sensitivity to breaking catalysts, headlines, and immediate sentiment momentum."
            if time_horizon == "short_term"
            else (
                "Mid-term news weighting: focus on quarterly earnings trends, sector rotation, and monetary policy."
                if time_horizon == "mid_term"
                else "Long-term news weighting: focus on corporate governance, regulatory stability, and secular fundamentals."
            )
        )
        risk_obs = list(result.risk_observations)
        risk_obs.append(f"[{time_horizon.upper().replace('_', ' ')}] {horizon_note}")

        duration_ms = (time.perf_counter() - start_time) * 1000

        await blackboard.update_news_sentiment(
            producer=self.name,
            total_articles=result.total_articles,
            positive_count=result.positive_count,
            negative_count=result.negative_count,
            neutral_count=result.neutral_count,
            overall_sentiment=result.overall_sentiment,
            sentiment_score=result.sentiment_score,
            articles=result.articles,
            positive_events=result.positive_events,
            negative_events=result.negative_events,
            risk_observations=risk_obs,
            warnings=result.warnings,
            source="google_news_rss" if not self.retriever.news_api_key else "newsapi",
            status=FindingStatus.AVAILABLE,
            notes=(
                f"Completed sentiment analysis ({time_horizon.upper().replace('_', ' ')}): {result.total_articles} articles, "
                f"sentiment={result.overall_sentiment} (score={result.sentiment_score:+.2f})"
            ),
        )

        await blackboard.log_event(
            component=self.name,
            event_type="agent_complete",
            status="completed",
            details={
                "duration_ms": duration_ms,
                "total_articles": result.total_articles,
                "overall_sentiment": result.overall_sentiment,
                "sentiment_score": result.sentiment_score,
            },
        )

        return {
            "status": "completed",
            "duration_ms": duration_ms,
            "total_articles": result.total_articles,
            "overall_sentiment": result.overall_sentiment,
            "sentiment_score": result.sentiment_score,
        }

