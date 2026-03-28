"""
data/news_fetcher.py
--------------------
Fetches financial news articles for symbols and general market news.
Primary source: NewsAPI (newsapi-python client).
Fallback: Google News RSS feed via feedparser.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Company name mapping for better news search
SYMBOL_TO_COMPANY = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet Google",
    "AMZN": "Amazon",
    "NVDA": "NVIDIA",
    "META": "Meta Facebook",
    "TSLA": "Tesla",
    "BRK-B": "Berkshire Hathaway",
    "JPM": "JPMorgan Chase",
    "V": "Visa",
    "UNH": "UnitedHealth",
    "JNJ": "Johnson Johnson",
    "XOM": "Exxon Mobil",
    "WMT": "Walmart",
    "MA": "Mastercard",
    "PG": "Procter Gamble",
    "HD": "Home Depot",
    "CVX": "Chevron",
    "LLY": "Eli Lilly",
    "MRK": "Merck",
    "ABBV": "AbbVie",
    "PFE": "Pfizer",
    "AVGO": "Broadcom",
    "COST": "Costco",
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
    "TMO": "Thermo Fisher",
    "CSCO": "Cisco",
    "ACN": "Accenture",
    "MCD": "McDonald's",
    "ABT": "Abbott Laboratories",
    "DHR": "Danaher",
    "TXN": "Texas Instruments",
    "NEE": "NextEra Energy",
    "WFC": "Wells Fargo",
    "BMY": "Bristol-Myers Squibb",
    "CRM": "Salesforce",
    "QCOM": "Qualcomm",
    "ORCL": "Oracle",
    "AMD": "Advanced Micro Devices",
    "INTC": "Intel",
    "HON": "Honeywell",
    "UPS": "United Parcel Service",
    "CAT": "Caterpillar",
    "BA": "Boeing",
    "GS": "Goldman Sachs",
    "MS": "Morgan Stanley",
    "AMGN": "Amgen",
    "INTU": "Intuit",
    "SBUX": "Starbucks",
}


class NewsFetcher:
    """
    Fetches financial news articles from NewsAPI with a Google News RSS fallback.

    Parameters
    ----------
    api_key : str
        NewsAPI key.  When empty, all requests fall back to RSS.
    max_articles : int
        Maximum number of articles to return per symbol per call.
    """

    def __init__(self, api_key: str = "", max_articles: int = 10):
        self._api_key = api_key
        self._max_articles = max_articles
        self._newsapi_client = None
        self._cache: dict[str, tuple[datetime, list[dict]]] = {}
        self._cache_ttl = timedelta(minutes=30)

        if api_key:
            try:
                from newsapi import NewsApiClient  # type: ignore
                self._newsapi_client = NewsApiClient(api_key=api_key)
                logger.info("NewsAPI client initialised.")
            except ImportError:
                logger.warning("newsapi-python not installed; using RSS fallback only.")
            except Exception as exc:
                logger.error("NewsAPI init error: %s", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_news(
        self,
        symbol: str,
        company_name: str = "",
        days_back: int = 2,
    ) -> list[dict]:
        """
        Fetch recent news articles for a single stock symbol.

        Parameters
        ----------
        symbol : str
            Ticker symbol, e.g. ``"AAPL"``.
        company_name : str
            Human-readable company name used to broaden searches.
            Inferred from the built-in mapping if empty.
        days_back : int
            How many calendar days of news to retrieve.

        Returns
        -------
        list[dict]
            List of article dicts with keys:
            ``title``, ``description``, ``content``, ``url``,
            ``published_at``, ``source``.
        """
        cache_key = f"{symbol}:{days_back}"
        cached = self._cache.get(cache_key)
        if cached:
            ts, articles = cached
            if datetime.now(tz=timezone.utc) - ts < self._cache_ttl:
                return articles

        if not company_name:
            company_name = SYMBOL_TO_COMPANY.get(symbol, symbol)

        articles: list[dict] = []

        if self._newsapi_client:
            articles = self._fetch_newsapi(symbol, company_name, days_back)

        if not articles:
            articles = self._fetch_rss_fallback(symbol)

        articles = articles[: self._max_articles]
        self._cache[cache_key] = (datetime.now(tz=timezone.utc), articles)
        logger.debug("Fetched %d articles for %s", len(articles), symbol)
        return articles

    def fetch_market_news(self) -> list[dict]:
        """
        Fetch general market and financial news headlines.

        Returns
        -------
        list[dict]
            Same structure as :meth:`fetch_news`.
        """
        cache_key = "MARKET"
        cached = self._cache.get(cache_key)
        if cached:
            ts, articles = cached
            if datetime.now(tz=timezone.utc) - ts < self._cache_ttl:
                return articles

        articles: list[dict] = []

        if self._newsapi_client:
            try:
                from_dt = (datetime.now(tz=timezone.utc) - timedelta(days=1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                response = self._newsapi_client.get_top_headlines(
                    category="business",
                    language="en",
                    page_size=20,
                )
                articles = self._parse_newsapi_response(response)
            except Exception as exc:
                logger.error("NewsAPI market news error: %s", exc)

        if not articles:
            articles = self._fetch_market_rss()

        self._cache[cache_key] = (datetime.now(tz=timezone.utc), articles)
        return articles

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_newsapi(
        self,
        symbol: str,
        company_name: str,
        days_back: int,
    ) -> list[dict]:
        """Query NewsAPI everything endpoint for a symbol."""
        query = f'"{symbol}" OR "{company_name}"'
        from_dt = (datetime.now(tz=timezone.utc) - timedelta(days=days_back)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        try:
            response = self._newsapi_client.get_everything(
                q=query,
                from_param=from_dt,
                language="en",
                sort_by="relevancy",
                page_size=self._max_articles,
            )
            return self._parse_newsapi_response(response)
        except Exception as exc:
            logger.warning("NewsAPI error for %s: %s", symbol, exc)
            return []

    def _parse_newsapi_response(self, response: dict) -> list[dict]:
        """Convert NewsAPI response dict to normalised article list."""
        articles = []
        for raw in response.get("articles", []):
            articles.append(
                {
                    "title": raw.get("title") or "",
                    "description": raw.get("description") or "",
                    "content": raw.get("content") or "",
                    "url": raw.get("url") or "",
                    "published_at": raw.get("publishedAt") or "",
                    "source": (raw.get("source") or {}).get("name") or "NewsAPI",
                }
            )
        return articles

    def _fetch_rss_fallback(self, symbol: str) -> list[dict]:
        """
        Fetch news via Google News RSS feed for *symbol*.

        Returns
        -------
        list[dict]
            Normalised article list (same schema as NewsAPI output).
        """
        try:
            import feedparser  # type: ignore

            url = (
                f"https://news.google.com/rss/search?"
                f"q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"
            )
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[: self._max_articles]:
                articles.append(
                    {
                        "title": getattr(entry, "title", ""),
                        "description": getattr(entry, "summary", ""),
                        "content": getattr(entry, "summary", ""),
                        "url": getattr(entry, "link", ""),
                        "published_at": getattr(entry, "published", ""),
                        "source": "Google News RSS",
                    }
                )
            return articles
        except Exception as exc:
            logger.warning("RSS fallback error for %s: %s", symbol, exc)
            return []

    def _fetch_market_rss(self) -> list[dict]:
        """Fetch general market news from Yahoo Finance RSS."""
        try:
            import feedparser  # type: ignore

            url = "https://finance.yahoo.com/rss/headline?s=^GSPC"
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[:20]:
                articles.append(
                    {
                        "title": getattr(entry, "title", ""),
                        "description": getattr(entry, "summary", ""),
                        "content": getattr(entry, "summary", ""),
                        "url": getattr(entry, "link", ""),
                        "published_at": getattr(entry, "published", ""),
                        "source": "Yahoo Finance RSS",
                    }
                )
            return articles
        except Exception as exc:
            logger.warning("Market RSS fallback error: %s", exc)
            return []

    def clear_cache(self) -> None:
        """Clear internal news cache (useful for testing)."""
        self._cache.clear()
