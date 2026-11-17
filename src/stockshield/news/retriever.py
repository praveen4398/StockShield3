"""News retrieval component for Indian equities in StockShield 2.0.

Retrieves verified financial news for NSE/BSE tickers using accessible,
zero-cost sources (Google News RSS for Indian markets) with optional NewsAPI
integration when configured via environment variables.

Strictly adheres to:
- No fabrication of news or dates
- Deduplication and relevance filtering
- Untrusted content sanitization and prompt-injection neutralization
- Robust network error and timeout handling
"""

import html
import json
import logging
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from stockshield.news.models import NewsArticle

logger = logging.getLogger(__name__)

# Canonical company name and alias mapping for prominent Indian equities
INDIAN_COMPANY_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "TCS.NS": {"name": "Tata Consultancy Services", "aliases": ["TCS", "Tata Consultancy"]},
    "INFY.NS": {"name": "Infosys", "aliases": ["Infosys", "Infy"]},
    "RELIANCE.NS": {"name": "Reliance Industries", "aliases": ["Reliance", "RIL", "Jio"]},
    "HDFCBANK.NS": {"name": "HDFC Bank", "aliases": ["HDFC Bank", "HDFCBANK", "HDFC"]},
    "WIPRO.NS": {"name": "Wipro", "aliases": ["Wipro"]},
    "ICICIBANK.NS": {"name": "ICICI Bank", "aliases": ["ICICI Bank", "ICICIBANK", "ICICI"]},
    "SBIN.NS": {"name": "State Bank of India", "aliases": ["State Bank of India", "SBI", "SBIN"]},
    "ITC.NS": {"name": "ITC", "aliases": ["ITC Limited", "ITC"]},
    "TATAMOTORS.NS": {"name": "Tata Motors", "aliases": ["Tata Motors", "TaMo"]},
    "BHARTIARTL.NS": {"name": "Bharti Airtel", "aliases": ["Bharti Airtel", "Airtel"]},
    "LT.NS": {"name": "Larsen & Toubro", "aliases": ["Larsen & Toubro", "L&T"]},
    "KOTAKBANK.NS": {"name": "Kotak Mahindra Bank", "aliases": ["Kotak Mahindra Bank", "Kotak Bank", "Kotak"]},
}

# Prompt injection patterns to detect and neutralize in untrusted external text
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"you\s+are\s+now\s+dan",
    r"system\s+prompt\s+override",
    r"reveal\s+(the\s+)?(developer|system)\s+prompt",
    r"disregard\s+all\s+safety",
    r"bypass\s+risk\s+checks",
    r"<script[\s\S]*?>[\s\S]*?<\/script>",
]


class NewsRetriever:
    """Robust news retriever for Indian stock tickers."""

    def __init__(
        self,
        timeout_seconds: float = 8.0,
        max_articles: int = 10,
        fixtures_dir: Optional[Path] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_articles = max_articles
        self.fixtures_dir = fixtures_dir or Path("data/fixtures/news")
        self.news_api_key = os.getenv("NEWS_API_KEY", "").strip()

    def get_company_metadata(self, ticker: str) -> Tuple[str, List[str]]:
        """Return (canonical_name, list_of_search_aliases) for a given ticker."""
        clean_ticker = ticker.strip().upper()
        if clean_ticker in INDIAN_COMPANY_MAPPINGS:
            data = INDIAN_COMPANY_MAPPINGS[clean_ticker]
            return data["name"], data["aliases"]

        # Fallback for unmapped tickers (e.g. TATAPOWER.NS -> TataPower)
        base = clean_ticker.split(".")[0]
        return base, [base, clean_ticker]

    def sanitize_untrusted_text(self, text: str, max_chars: int = 500) -> str:
        """Strip HTML, unescape entities, neutralize prompt injection, and truncate length."""
        if not text:
            return ""

        # Unescape and strip HTML tags
        clean = html.unescape(text)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = " ".join(clean.split()).strip()

        # Neutralize prompt injection attempts in external news
        for pattern in INJECTION_PATTERNS:
            clean = re.sub(pattern, "[REDACTED_UNTRUSTED_CONTENT]", clean, flags=re.IGNORECASE)

        if len(clean) > max_chars:
            clean = clean[:max_chars].rstrip() + "..."
        return clean

    def _normalize_title_key(self, title: str) -> str:
        """Create a fingerprint for deduplicating headlines."""
        return re.sub(r"[^a-z0-9]", "", title.lower())

    def _is_article_relevant(self, title: str, description: str, aliases: List[str], base_ticker: str) -> bool:
        """Filter out articles that do not mention the company, ticker, or financial context."""
        combined = f"{title} {description}".lower()
        # Direct alias match
        for alias in aliases:
            if alias.lower() in combined:
                return True
        if base_ticker.lower() in combined:
            return True
        return False

    def fetch_news(
        self,
        ticker: str,
        limit: Optional[int] = None,
        provider_mode: str = "auto",
    ) -> Tuple[List[NewsArticle], List[str]]:
        """Fetch real news for the ticker.

        Returns:
            (articles, warnings)
        """
        max_items = limit or self.max_articles
        warnings: List[str] = []
        clean_ticker = ticker.strip().upper()

        if provider_mode == "fixture":
            # Load deterministic offline news fixture without making network calls
            fixture_path = self.fixtures_dir / f"{clean_ticker}.json"
            if fixture_path.exists():
                try:
                    with open(fixture_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    raw_articles = data.get("articles", []) if isinstance(data, dict) else data
                    articles = [
                        NewsArticle(
                            title=self.sanitize_untrusted_text(a["title"]),
                            source=a.get("source", "Offline Fixture"),
                            published_date=a.get("published_date"),
                            url=a.get("url"),
                            description=self.sanitize_untrusted_text(a.get("description", "")),
                        )
                        for a in raw_articles
                    ]
                    return articles[:max_items], []
                except Exception as e:
                    logger.error("Failed to load news fixture %s: %s", fixture_path, e)
                    return [], [f"Failed to parse offline news fixture for '{clean_ticker}': {str(e)}"]
            return [], [f"No offline news fixture found for ticker '{clean_ticker}'. Expected file at '{fixture_path}'."]

        company_name, aliases = self.get_company_metadata(ticker)
        base_ticker = ticker.split(".")[0]

        # 1. Primary retrieval: Google News RSS for Indian markets
        articles, rss_warnings = self._fetch_google_news_rss(company_name, aliases, base_ticker, max_items)
        warnings.extend(rss_warnings)

        if articles:
            return articles[:max_items], warnings

        # 2. Secondary fallback: NewsAPI if configured
        if self.news_api_key:
            api_articles, api_warnings = self._fetch_newsapi(company_name, base_ticker, max_items)
            warnings.extend(api_warnings)
            if api_articles:
                return api_articles[:max_items], warnings

        if not articles and not warnings:
            warnings.append(f"No recent news articles found matching company query '{company_name}'.")

        return [], warnings

    def _fetch_google_news_rss(
        self,
        company_name: str,
        aliases: List[str],
        base_ticker: str,
        max_items: int,
    ) -> Tuple[List[NewsArticle], List[str]]:
        """Retrieve and parse Google News RSS XML."""
        warnings: List[str] = []
        articles: List[NewsArticle] = []
        seen_titles: Set[str] = set()
        seen_urls: Set[str] = set()

        query_str = f'"{company_name}" stock OR share'
        encoded_query = urllib.parse.quote_plus(query_str)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"

        req = urllib.request.Request(
            rss_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/rss+xml, application/xml, text/xml",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                xml_content = resp.read()
        except urllib.error.HTTPError as e:
            warnings.append(f"Google News RSS HTTP error: status {e.code} ({e.reason})")
            return [], warnings
        except urllib.error.URLError as e:
            warnings.append(f"Google News RSS network error: {str(e.reason)}")
            return [], warnings
        except TimeoutError:
            warnings.append("Google News RSS request timed out.")
            return [], warnings
        except Exception as e:
            warnings.append(f"Google News RSS retrieval failure: {str(e)}")
            return [], warnings

        # Parse XML
        try:
            root = ET.fromstring(xml_content)
            items = root.findall(".//item")
        except ET.ParseError as e:
            warnings.append(f"Failed to parse news RSS XML: {str(e)}")
            return [], warnings

        for item in items:
            title_elem = item.find("title")
            link_elem = item.find("link")
            pub_date_elem = item.find("pubDate")
            source_elem = item.find("source")
            desc_elem = item.find("description")

            raw_title = title_elem.text if title_elem is not None and title_elem.text else ""
            raw_url = link_elem.text if link_elem is not None and link_elem.text else None
            raw_pub_date = pub_date_elem.text if pub_date_elem is not None else None
            raw_source = source_elem.text if source_elem is not None and source_elem.text else "Financial Press"
            raw_desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""

            if not raw_title or not raw_title.strip():
                continue

            clean_title = self.sanitize_untrusted_text(raw_title, max_chars=300)
            clean_desc = self.sanitize_untrusted_text(raw_desc, max_chars=500)
            clean_source = self.sanitize_untrusted_text(raw_source, max_chars=100) or "Financial Press"

            # Deduplication
            title_key = self._normalize_title_key(clean_title)
            if not title_key or title_key in seen_titles:
                continue
            if raw_url and raw_url in seen_urls:
                continue

            # Relevance check
            if not self._is_article_relevant(clean_title, clean_desc, aliases, base_ticker):
                continue

            seen_titles.add(title_key)
            if raw_url:
                seen_urls.add(raw_url)

            try:
                article = NewsArticle(
                    title=clean_title,
                    source=clean_source,
                    published_date=raw_pub_date,
                    url=raw_url,
                    description=clean_desc,
                )
                articles.append(article)
            except Exception as ex:
                logger.debug(f"Skipping malformed article: {ex}")
                continue

            if len(articles) >= max_items:
                break

        return articles, warnings

    def _fetch_newsapi(
        self,
        company_name: str,
        base_ticker: str,
        max_items: int,
    ) -> Tuple[List[NewsArticle], List[str]]:
        """Optional secondary retrieval via NewsAPI if API key is provided."""
        warnings: List[str] = []
        articles: List[NewsArticle] = []
        if not self.news_api_key:
            return [], warnings

        encoded_q = urllib.parse.quote_plus(f"{company_name} India")
        api_url = (
            f"https://newsapi.org/v2/everything?q={encoded_q}&apiKey={self.news_api_key}"
            f"&language=en&sortBy=publishedAt&pageSize={max_items}"
        )
        req = urllib.request.Request(api_url, headers={"User-Agent": "StockShield/2.0"})

        try:
            import json

            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            for item in data.get("articles", []):
                title = self.sanitize_untrusted_text(item.get("title", ""), max_chars=300)
                desc = self.sanitize_untrusted_text(item.get("description", ""), max_chars=500)
                source_obj = item.get("source", {})
                source_name = source_obj.get("name", "NewsAPI") if isinstance(source_obj, dict) else "NewsAPI"
                url = item.get("url")
                published_at = item.get("publishedAt")

                if not title:
                    continue

                article = NewsArticle(
                    title=title,
                    source=source_name,
                    published_date=published_at,
                    url=url,
                    description=desc,
                )
                articles.append(article)
                if len(articles) >= max_items:
                    break
        except Exception as e:
            warnings.append(f"NewsAPI query warning: {str(e)}")

        return articles, warnings
