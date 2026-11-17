"""Pydantic v2 structured models for News and Sentiment analysis in StockShield 2.0.

Re-exports core news models defined in stockshield.blackboard.models.
"""

from stockshield.blackboard.models import (
    ArticleSentiment,
    NewsArticle,
    NewsSentimentResult,
    NewsSentimentState,
)

__all__ = [
    "ArticleSentiment",
    "NewsArticle",
    "NewsSentimentResult",
    "NewsSentimentState",
]
