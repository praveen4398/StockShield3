"""Deterministic financial sentiment analyzer for StockShield 2.0.

Implements rule-based, financial-lexicon scoring tailored to Indian capital markets
(inspired by the Loughran-McDonald financial dictionary and NSE disclosure standards).

Guarantees:
- Purely deterministic, reproducible output
- No random or stochastic variables
- Distinct separation of article sentiment vs. overall market risk
- Extensible architecture ready for future neural / LLM plug-in adapters
"""

import re
from typing import List, Optional

from stockshield.news.models import (
    ArticleSentiment,
    NewsArticle,
    NewsSentimentResult,
)

# High-conviction financial sentiment phrases (multi-word phrases weighted higher)
STRONG_POSITIVE_PHRASES = [
    "profit surge",
    "profit jumps",
    "record profit",
    "revenue jumps",
    "net profit climbs",
    "beats estimates",
    "outperforms",
    "rating upgrade",
    "strong buy",
    "dividend hike",
    "bonus issue",
    "bags deal",
    "contract win",
    "secures order",
    "multi-year deal",
    "partnership agreement",
    "acquisition approved",
    "market share gain",
    "all-time high",
    "strong earnings",
    "guidance raised",
]

POSITIVE_KEYWORDS = [
    "growth",
    "profit",
    "surge",
    "rally",
    "climbs",
    "advances",
    "bullish",
    "gain",
    "soars",
    "outperform",
    "expansion",
    "dividend",
    "deal",
    "partnership",
    "alliance",
    "contract",
    "order",
    "bags",
    "win",
    "resilient",
    "turnaround",
    "wins",
    "upgraded",
]

STRONG_NEGATIVE_PHRASES = [
    "profit slump",
    "profit plunges",
    "net loss",
    "revenue drops",
    "misses estimates",
    "rating cut",
    "rating downgrade",
    "regulatory probe",
    "sebi penalty",
    "rbi fine",
    "fraud investigation",
    "accounting irregularity",
    "insolvency",
    "bankruptcy",
    "lawsuit filed",
    "litigation",
    "cbi charges",
    "ed raid",
    "tax evasion",
    "ceo resigns",
    "cfo resigns",
    "cyber breach",
    "shares tumble",
    "shares plunge",
    "warning issued",
]

NEGATIVE_KEYWORDS = [
    "decline",
    "loss",
    "slump",
    "plunge",
    "tumble",
    "fall",
    "bearish",
    "fine",
    "penalty",
    "probe",
    "scam",
    "fraud",
    "warning",
    "headwinds",
    "weakness",
    "breach",
    "litigation",
    "downgraded",
    "drop",
    "drags",
]

# Topic classification keywords
TOPIC_RULES = [
    (
        "Regulatory & Compliance Action",
        [
            r"\bsebi\b",
            r"\brbi\b",
            r"\bprobe\b",
            r"\binvestigation\b",
            r"\bpenalty\b",
            r"\bfine\b",
            r"\bcourt\b",
            r"\bed\b",
            r"\bcbi\b",
            r"\bregulatory\b",
            r"\bnclt\b",
            r"\btax\b",
        ],
    ),
    (
        "Quarterly Earnings & Financials",
        [
            r"\bq[1-4]\b",
            r"\bquarterly\b",
            r"\bresults\b",
            r"\bprofit\b",
            r"\brevenue\b",
            r"\bearnings\b",
            r"\bebitda\b",
            r"\bpat\b",
            r"\bmargin\b",
        ],
    ),
    (
        "Contracts & Technology Partnerships",
        [
            r"\bdeal\b",
            r"\bcontract\b",
            r"\border\b",
            r"\bpartnership\b",
            r"\btie-up\b",
            r"\balliance\b",
            r"\bcloud\b",
            r"\bai\b",
            r"\bdigital\b",
        ],
    ),
    (
        "Mergers & Capital Allocation",
        [
            r"\bmerger\b",
            r"\bacquisition\b",
            r"\btakeover\b",
            r"\bdividend\b",
            r"\bbuyback\b",
            r"\bcapex\b",
            r"\bstake\b",
        ],
    ),
    (
        "Leadership & Governance",
        [
            r"\bceo\b",
            r"\bcfo\b",
            r"\bboard\b",
            r"\bdirector\b",
            r"\bresigns\b",
            r"\bappoints\b",
            r"\bgovernance\b",
            r"\bmanagement\b",
        ],
    ),
    (
        "Market & Analyst Valuation",
        [
            r"\btarget price\b",
            r"\bupgrade\b",
            r"\bdowngrade\b",
            r"\bbrokerage\b",
            r"\brating\b",
            r"\bvaluation\b",
        ],
    ),
]

NEGATION_PATTERNS = [
    r"\bnot\b",
    r"\bno\b",
    r"\bfailed to\b",
    r"\bfailure to\b",
    r"\bunable to\b",
    r"\bwithout\b",
]


class DeterministicFinancialSentimentAnalyzer:
    """Institutional deterministic sentiment classifier for financial press."""

    def extract_financial_topic(self, text: str) -> str:
        """Classify key financial event topic using rule-based regex patterns."""
        lowered = text.lower()
        for topic_name, patterns in TOPIC_RULES:
            for pattern in patterns:
                if re.search(pattern, lowered):
                    return topic_name
        return "Corporate & Market Update"

    def analyze_article(self, article: NewsArticle, ticker: str) -> ArticleSentiment:
        """Analyze an individual article and return structured ArticleSentiment."""
        text = f"{article.title} {article.description}".lower()
        topic = self.extract_financial_topic(text)

        # 1. Check strong multi-word phrases first
        strong_pos = sum(2.0 for phrase in STRONG_POSITIVE_PHRASES if phrase in text)
        strong_neg = sum(2.0 for phrase in STRONG_NEGATIVE_PHRASES if phrase in text)

        # 2. Check single keywords
        words = re.findall(r"\b[a-z]{3,}\b", text)
        kw_pos = sum(1.0 for word in words if word in POSITIVE_KEYWORDS)
        kw_neg = sum(1.0 for word in words if word in NEGATIVE_KEYWORDS)

        # 3. Check for negation near positive words (e.g. 'not growing', 'failed to profit')
        negated_pos = 0.0
        for neg in NEGATION_PATTERNS:
            for kw in POSITIVE_KEYWORDS:
                if re.search(rf"{neg}\s+(\w+\s+)?{kw}", text):
                    negated_pos += 1.5

        total_pos = max(0.0, (strong_pos + kw_pos) - negated_pos)
        total_neg = strong_neg + kw_neg + (negated_pos * 0.5)

        # Classification logic
        if total_pos > total_neg and (total_pos - total_neg) >= 1.0:
            sentiment = "POSITIVE"
            diff = total_pos - total_neg
            confidence = min(0.60 + (diff * 0.08), 0.95)
            explanation = (
                f"Favorable indicators detected in headline/lead (score +{total_pos:.1f} vs -{total_neg:.1f}). "
                f"Topic: {topic}."
            )
        elif total_neg > total_pos and (total_neg - total_pos) >= 1.0:
            sentiment = "NEGATIVE"
            diff = total_neg - total_pos
            confidence = min(0.60 + (diff * 0.08), 0.95)
            explanation = (
                f"Adverse market/regulatory headwinds identified (score -{total_neg:.1f} vs +{total_pos:.1f}). "
                f"Topic: {topic}."
            )
        else:
            sentiment = "NEUTRAL"
            confidence = 0.55
            explanation = (
                f"Balanced or neutral corporate reporting without strong directional momentum. "
                f"Topic: {topic}."
            )

        return ArticleSentiment(
            article=article,
            sentiment=sentiment,
            explanation=explanation,
            financial_event_topic=topic,
            ticker=ticker,
            confidence=round(confidence, 2),
        )

    def analyze_corpus(
        self,
        articles: List[NewsArticle],
        ticker: str,
        retrieval_warnings: Optional[List[str]] = None,
    ) -> NewsSentimentResult:
        """Aggregate sentiment over all retrieved articles and derive institutional summary."""
        warnings = list(retrieval_warnings or [])
        if not articles:
            return NewsSentimentResult(
                ticker=ticker,
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
                warnings=warnings,
            )

        analyzed_articles: List[ArticleSentiment] = [self.analyze_article(art, ticker) for art in articles]

        pos_count = sum(1 for a in analyzed_articles if a.sentiment == "POSITIVE")
        neg_count = sum(1 for a in analyzed_articles if a.sentiment == "NEGATIVE")
        neu_count = sum(1 for a in analyzed_articles if a.sentiment == "NEUTRAL")
        total = len(analyzed_articles)

        # Normalized sentiment score: (-1.0 to +1.0)
        raw_score = (pos_count - neg_count) / total if total > 0 else 0.0
        sentiment_score = round(raw_score, 3)

        if sentiment_score >= 0.20:
            overall_sentiment = "POSITIVE"
        elif sentiment_score <= -0.20:
            overall_sentiment = "NEGATIVE"
        elif pos_count > 0 and neg_count > 0:
            overall_sentiment = "MIXED"
        else:
            overall_sentiment = "NEUTRAL"

        # Extract notable events
        positive_events: List[str] = []
        negative_events: List[str] = []
        risk_observations: List[str] = []

        for item in analyzed_articles:
            event_entry = f"[{item.financial_event_topic}] {item.article.title} ({item.article.source})"
            if item.sentiment == "POSITIVE" and len(positive_events) < 3:
                positive_events.append(event_entry)
            elif item.sentiment == "NEGATIVE" and len(negative_events) < 3:
                negative_events.append(event_entry)

            # Check for critical regulatory or legal topics
            if item.financial_event_topic == "Regulatory & Compliance Action":
                note = f"Regulatory scrutiny noted: '{item.article.title}' ({item.article.source})"
                if note not in risk_observations:
                    risk_observations.append(note)

        # Contextual risk observations
        if neg_count > pos_count and neg_count >= 2:
            risk_observations.append(
                f"Negative coverage predominates ({neg_count}/{total} articles negative, sentiment score {sentiment_score:+.2f})."
            )
        elif pos_count >= 2 and neg_count == 0:
            risk_observations.append(
                f"Supportive media consensus ({pos_count}/{total} articles positive, zero negative)."
            )

        risk_observations.append(
            "Media sentiment reflects short-term market perception; does not guarantee future price movement."
        )

        return NewsSentimentResult(
            ticker=ticker,
            total_articles=total,
            positive_count=pos_count,
            negative_count=neg_count,
            neutral_count=neu_count,
            overall_sentiment=overall_sentiment,
            sentiment_score=sentiment_score,
            articles=analyzed_articles,
            positive_events=positive_events,
            negative_events=negative_events,
            risk_observations=risk_observations,
            warnings=warnings,
        )
