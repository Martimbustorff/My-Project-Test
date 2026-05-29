"""
watchlist
=========
Dynamic stock watchlist that produces **weekly recommendations** of growing
American and European stocks, ranked across three dimensions:

1. **Biggest upside**     – analyst price target vs. current price.
2. **Financial growth**   – revenue / earnings growth history.
3. **Analyst consensus**  – aggregated buy / hold / sell ratings.

The watchlist targets a holding horizon of up to **3 months** and is designed
to be regenerated every week (see :func:`watchlist.watchlist.WatchlistBuilder`).

Public API
----------
    from watchlist import WatchlistBuilder, StockMetrics, Recommendation

The scoring layer (:mod:`watchlist.scoring`) is pure and has no network
dependency, so it can be unit-tested in isolation.  The screening layer
(:mod:`watchlist.screener`) fetches live data via yfinance.
"""

from .scoring import (
    StockMetrics,
    score_upside,
    score_growth,
    score_consensus,
    composite_score,
    is_growing,
)
from .watchlist import WatchlistBuilder, Recommendation, WeeklyWatchlist

__all__ = [
    "StockMetrics",
    "score_upside",
    "score_growth",
    "score_consensus",
    "composite_score",
    "is_growing",
    "WatchlistBuilder",
    "Recommendation",
    "WeeklyWatchlist",
]
