"""
watchlist/screener.py
----------------------
Fetches the raw inputs each candidate needs and turns them into a fully-scored
:class:`StockMetrics`.

Data source: **yfinance** (already a project dependency).  yfinance covers both
American tickers (bare symbols) and European tickers (exchange-suffixed, e.g.
``ASML.AS``), which is exactly the universe scope we need.

The screener is deliberately tolerant: any per-field or per-ticker failure is
caught and logged, the affected metric falls back to ``None``, and scoring
degrades to a neutral value rather than dropping the candidate outright.  This
keeps a weekly run robust against the inevitable gaps in free fundamental data.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from .scoring import StockMetrics, GrowthGate, apply_scores
from .universe import Candidate

logger = logging.getLogger(__name__)


def _safe_float(value) -> Optional[float]:
    """Coerce to float, mapping NaN / None / bad values to None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _safe_int(value) -> Optional[int]:
    f = _safe_float(value)
    return int(f) if f is not None else None


class Screener:
    """
    Turns :class:`Candidate` entries into scored :class:`StockMetrics`.

    Parameters
    ----------
    weights : dict, optional
        Composite-score weights (see :data:`scoring.DEFAULT_WEIGHTS`).
    gate : GrowthGate, optional
        Thresholds for the "growing stock" qualification.
    """

    def __init__(self, weights: Optional[dict] = None, gate: Optional[GrowthGate] = None):
        self._weights = weights
        self._gate = gate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def screen(self, candidates: list[Candidate]) -> list[StockMetrics]:
        """Fetch + score every candidate. Failures are skipped (and logged)."""
        results: list[StockMetrics] = []
        for cand in candidates:
            try:
                metrics = self.screen_one(cand)
                if metrics is not None:
                    results.append(metrics)
            except Exception as exc:   # never let one bad ticker kill the run
                logger.warning("Screening failed for %s: %s", cand.symbol, exc)
        return results

    def screen_one(self, cand: Candidate) -> Optional[StockMetrics]:
        """Fetch + score a single candidate."""
        raw = self._fetch_raw(cand.symbol)
        if raw is None:
            return None
        metrics = self._build_metrics(cand, raw)
        return apply_scores(metrics, weights=self._weights, gate=self._gate)

    # ------------------------------------------------------------------
    # Data fetching (yfinance)
    # ------------------------------------------------------------------

    def _fetch_raw(self, symbol: str) -> Optional[dict]:
        """
        Pull the raw provider payload for *symbol*.

        Returns a dict with the keys consumed by :meth:`_build_metrics`, or
        None when the provider yields nothing usable.
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.error(
                "yfinance is not installed — cannot screen %s. "
                "Install requirements.txt.", symbol
            )
            return None

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
        except Exception as exc:
            logger.warning("yfinance.info failed for %s: %s", symbol, exc)
            info = {}

        # 3-month price action (≤3-month horizon trend)
        price_change_3m = None
        above_50d_ma = None
        try:
            hist = ticker.history(period="3mo", interval="1d")
            if hist is not None and not hist.empty and "Close" in hist:
                closes = hist["Close"].dropna()
                if len(closes) >= 2:
                    price_change_3m = float(closes.iloc[-1] / closes.iloc[0] - 1.0)
                if len(closes) >= 50:
                    ma50 = float(closes.tail(50).mean())
                    above_50d_ma = bool(closes.iloc[-1] > ma50)
        except Exception as exc:
            logger.debug("history() failed for %s: %s", symbol, exc)

        # Multi-year revenue CAGR from the income statement
        revenue_cagr = self._revenue_cagr(ticker)

        if not info and price_change_3m is None:
            return None

        return {"info": info, "price_change_3m": price_change_3m,
                "above_50d_ma": above_50d_ma, "revenue_cagr": revenue_cagr}

    @staticmethod
    def _revenue_cagr(ticker) -> Optional[float]:
        """
        Compute a multi-year revenue CAGR from the annual income statement.

        Uses the oldest and newest 'Total Revenue' rows available
        (typically a 3–4 year span).  Returns None when unavailable or when the
        oldest value is non-positive.
        """
        try:
            fin = ticker.income_stmt
            if fin is None or fin.empty or "Total Revenue" not in fin.index:
                return None
            revenue = fin.loc["Total Revenue"].dropna()
            if len(revenue) < 2:
                return None
            # Columns are ordered newest → oldest in yfinance.
            newest = float(revenue.iloc[0])
            oldest = float(revenue.iloc[-1])
            years = len(revenue) - 1
            if oldest <= 0 or newest <= 0 or years <= 0:
                return None
            return (newest / oldest) ** (1.0 / years) - 1.0
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def _build_metrics(self, cand: Candidate, raw: dict) -> StockMetrics:
        info = raw.get("info", {})

        current_price = _safe_float(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )

        return StockMetrics(
            symbol=cand.symbol,
            name=cand.name or info.get("shortName") or cand.symbol,
            region=cand.region,
            exchange=cand.exchange,
            currency=info.get("currency", "USD") or "USD",
            market_cap=_safe_float(info.get("marketCap")),
            current_price=current_price,
            target_mean_price=_safe_float(info.get("targetMeanPrice")),
            target_high_price=_safe_float(info.get("targetHighPrice")),
            target_low_price=_safe_float(info.get("targetLowPrice")),
            revenue_growth=_safe_float(info.get("revenueGrowth")),
            earnings_growth=_safe_float(
                info.get("earningsGrowth")
                if info.get("earningsGrowth") is not None
                else info.get("earningsQuarterlyGrowth")
            ),
            revenue_cagr=_safe_float(raw.get("revenue_cagr")),
            recommendation_mean=_safe_float(info.get("recommendationMean")),
            recommendation_key=info.get("recommendationKey"),
            num_analysts=_safe_int(info.get("numberOfAnalystOpinions")),
            price_change_3m=_safe_float(raw.get("price_change_3m")),
            above_50d_ma=raw.get("above_50d_ma"),
        )
