"""
Finnhub API client for real news sentiment and company news.
Free tier: 60 API calls/minute.

Requires env var: FINNHUB_API_KEY
Falls back to yfinance keyword-based sentiment if key not set.

Install dependencies:
    pip install anthropic requests
"""
import os
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
BASE_URL = "https://finnhub.io/api/v1"


def get_news_sentiment(symbol: str) -> Optional[dict]:
    """
    Get Finnhub's pre-computed news sentiment for a symbol.

    Returns dict with:
        score: float  (-1.0 to 1.0, derived from bullishPercent - bearishPercent)
        bullish_pct: float
        bearish_pct: float
        articles_count: int
        buzz_score: float (relative to weekly average)
        reasons: List[str]  (human-readable bullet points)

    Returns None if API unavailable.
    """
    if not FINNHUB_API_KEY:
        return None

    # Finnhub uses different symbols for crypto (e.g. BINANCE:BTCUSDT not BTC-USD)
    # Skip crypto symbols
    if "-USD" in symbol or "-" in symbol:
        return None

    try:
        resp = requests.get(
            f"{BASE_URL}/news-sentiment",
            params={"symbol": symbol, "token": FINNHUB_API_KEY},
            timeout=5,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data or "sentiment" not in data:
            return None

        sentiment = data.get("sentiment", {})
        buzz = data.get("buzz", {})

        bullish_pct = float(sentiment.get("bullishPercent", 0.5))
        bearish_pct = float(sentiment.get("bearishPercent", 0.5))

        # Score: bullish - bearish, range -1 to +1
        score = (bullish_pct - bearish_pct)
        score = max(-1.0, min(1.0, score))

        articles = int(buzz.get("articlesInLastWeek", 0))
        weekly_avg = float(buzz.get("weeklyAverage", 1))
        buzz_ratio = articles / weekly_avg if weekly_avg > 0 else 1.0

        company_score = float(data.get("companyNewsScore", 0.5))
        sector_score = float(data.get("sectorAverageNewsScore", 0.5))

        # Build human-readable reasons
        reasons = []
        if bullish_pct > 0.6:
            reasons.append(f"News sentiment strongly bullish ({bullish_pct:.0%} positive headlines)")
        elif bullish_pct > 0.5:
            reasons.append(f"News sentiment mildly positive ({bullish_pct:.0%} positive headlines)")
        elif bearish_pct > 0.6:
            reasons.append(f"News sentiment strongly bearish ({bearish_pct:.0%} negative headlines)")
        else:
            reasons.append(f"News sentiment neutral ({bullish_pct:.0%} positive, {bearish_pct:.0%} negative)")

        if buzz_ratio > 1.5:
            reasons.append(f"News volume {buzz_ratio:.1f}x above weekly average — elevated attention")
        elif buzz_ratio < 0.5:
            reasons.append(f"Low news volume — below average media attention")

        if company_score > sector_score + 0.1:
            reasons.append(f"Company news score ({company_score:.2f}) above sector average ({sector_score:.2f})")

        return {
            "score": round(score, 3),
            "bullish_pct": round(bullish_pct, 3),
            "bearish_pct": round(bearish_pct, 3),
            "articles_count": articles,
            "buzz_ratio": round(buzz_ratio, 2),
            "reasons": reasons[:3],
        }

    except Exception as e:
        logger.debug("Finnhub sentiment failed for %s: %s", symbol, e)
        return None


def get_company_news(symbol: str, days: int = 3) -> list:
    """
    Get recent company news headlines from Finnhub.
    Returns list of {headline, summary, source, datetime} dicts.
    """
    if not FINNHUB_API_KEY:
        return []

    if "-USD" in symbol or "-" in symbol:
        return []

    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        resp = requests.get(
            f"{BASE_URL}/company-news",
            params={
                "symbol": symbol,
                "from": start.strftime("%Y-%m-%d"),
                "to": end.strftime("%Y-%m-%d"),
                "token": FINNHUB_API_KEY,
            },
            timeout=5,
        )

        if resp.status_code != 200:
            return []

        articles = resp.json()
        if not isinstance(articles, list):
            return []

        return [
            {
                "headline": a.get("headline", ""),
                "summary": a.get("summary", ""),
                "source": a.get("source", ""),
                "datetime": a.get("datetime", 0),
            }
            for a in articles[:10]
        ]

    except Exception as e:
        logger.debug("Finnhub news failed for %s: %s", symbol, e)
        return []
