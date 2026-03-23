"""
data/market_data.py
-------------------
Fetches market data from Alpaca (bars, quotes, account info) and
supplements with yfinance for fundamentals, VIX, and sector performance.
Implements exponential backoff for Alpaca API rate-limit handling.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def _exponential_backoff(attempt: int, base: float = 1.0, cap: float = 60.0) -> float:
    """Return seconds to sleep for the given attempt number (0-indexed)."""
    return min(cap, base * (2 ** attempt))


class MarketDataFetcher:
    """
    Centralises all market data retrieval.

    Uses Alpaca for real-time / intraday bars and quotes;
    falls back to or supplements with yfinance for fundamentals and
    broad market metrics such as VIX and sector performance.
    """

    def __init__(self, alpaca_client=None):
        """
        Parameters
        ----------
        alpaca_client : alpaca.data.historical.StockHistoricalDataClient, optional
            Pre-initialised Alpaca data client.  When *None* the class still
            works but all Alpaca-backed methods will raise gracefully.
        """
        self._client = alpaca_client
        self._spy_cache: dict[str, Any] = {}
        self._spy_cache_ts: datetime | None = None
        self._cache_ttl = timedelta(minutes=5)

    # ------------------------------------------------------------------
    # Alpaca-backed methods
    # ------------------------------------------------------------------

    def get_bars(
        self,
        symbols: list[str],
        timeframe: str = "1Min",
        limit: int = 200,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars for one or more symbols from Alpaca.

        Parameters
        ----------
        symbols : list[str]
            Ticker symbols, e.g. ``["AAPL", "MSFT"]``.
        timeframe : str
            Alpaca timeframe string: ``"1Min"``, ``"5Min"``, ``"1Hour"``,
            ``"1Day"``, etc.
        limit : int
            Maximum number of bars to return per symbol.

        Returns
        -------
        pd.DataFrame
            Multi-index DataFrame indexed by ``(symbol, timestamp)`` with
            columns ``open, high, low, close, volume``.
            Returns an empty DataFrame on failure.
        """
        if self._client is None:
            logger.warning("No Alpaca client configured — fetching bars via yfinance fallback.")
            return self._get_bars_yfinance(symbols, timeframe, limit)

        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        tf_map = {
            "1Min": TimeFrame(1, TimeFrameUnit.Minute),
            "5Min": TimeFrame(5, TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "30Min": TimeFrame(30, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
            "1Day": TimeFrame(1, TimeFrameUnit.Day),
        }
        tf = tf_map.get(timeframe, TimeFrame(1, TimeFrameUnit.Minute))

        end = datetime.now(tz=timezone.utc)
        # Estimate start time generously so we always get `limit` bars
        minutes_per_bar = {
            "1Min": 1, "5Min": 5, "15Min": 15, "30Min": 30,
            "1Hour": 60, "1Day": 1440,
        }.get(timeframe, 1)
        # Add 50% buffer for weekends/holidays
        calendar_minutes = int(limit * minutes_per_bar * 1.5)
        start = end - timedelta(minutes=calendar_minutes)

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            start=start,
            end=end,
            limit=limit,
        )

        for attempt in range(5):
            try:
                bars = self._client.get_stock_bars(request)
                df = bars.df
                if df.empty:
                    logger.warning("Empty bars response for %s", symbols)
                    return df
                df.index.names = ["symbol", "timestamp"]
                df.columns = [c.lower() for c in df.columns]
                return df
            except Exception as exc:
                if "rate limit" in str(exc).lower() or "429" in str(exc):
                    wait = _exponential_backoff(attempt)
                    logger.warning("Rate limited fetching bars; sleeping %.1fs", wait)
                    time.sleep(wait)
                else:
                    logger.error("Error fetching bars for %s: %s", symbols, exc)
                    break

        logger.info("Falling back to yfinance for bars.")
        return self._get_bars_yfinance(symbols, timeframe, limit)

    def _get_bars_yfinance(
        self,
        symbols: list[str],
        timeframe: str = "1Min",
        limit: int = 200,
    ) -> pd.DataFrame:
        """yfinance fallback for bar data (used when Alpaca client unavailable)."""
        tf_map = {
            "1Min": ("1m", "5d"),
            "5Min": ("5m", "5d"),
            "15Min": ("15m", "5d"),
            "30Min": ("30m", "7d"),
            "1Hour": ("1h", "30d"),
            "1Day": ("1d", "200d"),
        }
        yf_interval, yf_period = tf_map.get(timeframe, ("5m", "5d"))
        frames = []
        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                df = ticker.history(period=yf_period, interval=yf_interval)
                if df.empty:
                    continue
                df.index = pd.to_datetime(df.index, utc=True)
                df.columns = [c.lower() for c in df.columns]
                df = df[["open", "high", "low", "close", "volume"]].tail(limit)
                df.index = pd.MultiIndex.from_arrays(
                    [[sym] * len(df), df.index],
                    names=["symbol", "timestamp"],
                )
                frames.append(df)
            except Exception as exc:
                logger.error("yfinance bars error for %s: %s", sym, exc)
        if frames:
            return pd.concat(frames)
        return pd.DataFrame()

    def get_latest_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """
        Retrieve the latest bid/ask/trade price for each symbol.

        Returns
        -------
        dict[str, dict]
            Mapping of symbol -> ``{price, bid, ask, volume}``.
        """
        if self._client is None:
            return self._latest_quotes_yfinance(symbols)

        from alpaca.data.requests import StockLatestTradeRequest

        result: dict[str, dict] = {}
        # Batch into groups of 50 to respect Alpaca limits
        batch_size = 50
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i: i + batch_size]
            for attempt in range(4):
                try:
                    req = StockLatestTradeRequest(symbol_or_symbols=batch)
                    trades = self._client.get_stock_latest_trade(req)
                    for sym, trade in trades.items():
                        result[sym] = {
                            "price": float(trade.price),
                            "bid": float(trade.price),
                            "ask": float(trade.price),
                            "volume": int(trade.size),
                        }
                    break
                except Exception as exc:
                    if "rate limit" in str(exc).lower() or "429" in str(exc):
                        wait = _exponential_backoff(attempt)
                        logger.warning("Rate limited on quotes; sleeping %.1fs", wait)
                        time.sleep(wait)
                    else:
                        logger.error("Error fetching quotes for batch: %s", exc)
                        break

        # Fill in any missing via yfinance
        missing = [s for s in symbols if s not in result]
        if missing:
            result.update(self._latest_quotes_yfinance(missing))
        return result

    def _latest_quotes_yfinance(self, symbols: list[str]) -> dict[str, dict]:
        """Use yfinance fast_info for latest price when Alpaca unavailable."""
        result: dict[str, dict] = {}
        for sym in symbols:
            try:
                tk = yf.Ticker(sym)
                info = tk.fast_info
                price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
                if price:
                    result[sym] = {
                        "price": float(price),
                        "bid": float(price),
                        "ask": float(price),
                        "volume": int(getattr(info, "three_month_average_volume", 0) or 0),
                    }
            except Exception as exc:
                logger.debug("yfinance quote error %s: %s", sym, exc)
        return result

    # ------------------------------------------------------------------
    # yfinance-backed fundamentals
    # ------------------------------------------------------------------

    def get_fundamentals(self, symbol: str) -> dict:
        """
        Fetch fundamental data for a symbol using yfinance.

        Returns
        -------
        dict
            Keys: ``pe_ratio``, ``eps``, ``market_cap``, ``beta``,
            ``revenue_growth``, ``profit_margin``, ``debt_to_equity``,
            ``forward_pe``, ``price_to_book``.
            Missing values are ``None``.
        """
        defaults = {
            "pe_ratio": None,
            "eps": None,
            "market_cap": None,
            "beta": None,
            "revenue_growth": None,
            "profit_margin": None,
            "debt_to_equity": None,
            "forward_pe": None,
            "price_to_book": None,
        }
        try:
            tk = yf.Ticker(symbol)
            info = tk.info
            defaults.update({
                "pe_ratio": info.get("trailingPE"),
                "eps": info.get("trailingEps"),
                "market_cap": info.get("marketCap"),
                "beta": info.get("beta"),
                "revenue_growth": info.get("revenueGrowth"),
                "profit_margin": info.get("profitMargins"),
                "debt_to_equity": info.get("debtToEquity"),
                "forward_pe": info.get("forwardPE"),
                "price_to_book": info.get("priceToBook"),
            })
        except Exception as exc:
            logger.error("Fundamentals error for %s: %s", symbol, exc)
        return defaults

    # ------------------------------------------------------------------
    # Market regime
    # ------------------------------------------------------------------

    def get_market_regime(self) -> str:
        """
        Determine broad market regime using SPY price trend.

        Compares SPY's current 20-day EMA to its 50-day EMA using the
        last 60 daily bars.

        Returns
        -------
        str
            One of ``"bull"``, ``"bear"``, or ``"neutral"``.
        """
        now = datetime.now(tz=timezone.utc)
        if (
            self._spy_cache_ts is not None
            and now - self._spy_cache_ts < self._cache_ttl
            and "regime" in self._spy_cache
        ):
            return self._spy_cache["regime"]

        try:
            spy = yf.Ticker("SPY")
            hist = spy.history(period="90d", interval="1d")
            if hist.empty or len(hist) < 50:
                return "neutral"

            close = hist["Close"]
            ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
            ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
            ema20_prev = close.ewm(span=20, adjust=False).mean().iloc[-5]
            ema50_prev = close.ewm(span=50, adjust=False).mean().iloc[-5]

            if ema20 > ema50 and ema20_prev < ema50_prev:
                regime = "bull"  # golden cross
            elif ema20 < ema50 and ema20_prev > ema50_prev:
                regime = "bear"  # death cross
            elif ema20 > ema50 * 1.01:
                regime = "bull"
            elif ema20 < ema50 * 0.99:
                regime = "bear"
            else:
                regime = "neutral"

            self._spy_cache["regime"] = regime
            self._spy_cache_ts = now
            logger.debug("Market regime: %s (EMA20=%.2f, EMA50=%.2f)", regime, ema20, ema50)
            return regime
        except Exception as exc:
            logger.error("Market regime error: %s", exc)
            return "neutral"

    def get_vix(self) -> float:
        """
        Retrieve the current VIX level.

        Returns
        -------
        float
            VIX value; returns 20.0 as a neutral fallback on error.
        """
        now = datetime.now(tz=timezone.utc)
        if (
            self._spy_cache_ts is not None
            and now - self._spy_cache_ts < self._cache_ttl
            and "vix" in self._spy_cache
        ):
            return self._spy_cache["vix"]

        try:
            vix_tk = yf.Ticker("^VIX")
            hist = vix_tk.history(period="2d", interval="1d")
            if hist.empty:
                return 20.0
            vix_val = float(hist["Close"].iloc[-1])
            self._spy_cache["vix"] = vix_val
            return vix_val
        except Exception as exc:
            logger.error("VIX fetch error: %s", exc)
            return 20.0

    def get_sector_performance(self) -> dict[str, float]:
        """
        Compute 1-day return for each major sector ETF.

        Returns
        -------
        dict[str, float]
            Mapping of sector name -> 1-day percentage return.
        """
        sector_etfs = {
            "Technology": "XLK",
            "Healthcare": "XLV",
            "Financials": "XLF",
            "Consumer Discretionary": "XLY",
            "Consumer Staples": "XLP",
            "Energy": "XLE",
            "Industrials": "XLI",
            "Materials": "XLB",
            "Real Estate": "XLRE",
            "Utilities": "XLU",
            "Communication Services": "XLC",
        }
        result: dict[str, float] = {}
        tickers = list(sector_etfs.values())
        try:
            data = yf.download(
                tickers,
                period="5d",
                interval="1d",
                progress=False,
                auto_adjust=True,
            )
            closes = data["Close"] if "Close" in data else data
            for sector, etf in sector_etfs.items():
                try:
                    col = closes[etf].dropna()
                    if len(col) >= 2:
                        ret = (col.iloc[-1] - col.iloc[-2]) / col.iloc[-2] * 100
                        result[sector] = round(float(ret), 3)
                except Exception:
                    result[sector] = 0.0
        except Exception as exc:
            logger.error("Sector performance error: %s", exc)
            for sector in sector_etfs:
                result[sector] = 0.0
        return result

    # ------------------------------------------------------------------
    # Market hours
    # ------------------------------------------------------------------

    def is_market_open(self) -> bool:
        """
        Check whether the US stock market is currently open.

        Uses a simple time-based check (Mon-Fri, 09:30–16:00 ET).
        When an Alpaca trading client is available it is preferred.

        Returns
        -------
        bool
            True if market is open for regular trading.
        """
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo  # type: ignore

        et = ZoneInfo("America/New_York")
        now_et = datetime.now(tz=et)

        # Weekends
        if now_et.weekday() >= 5:
            return False

        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open <= now_et < market_close

    def minutes_to_close(self) -> int:
        """Return minutes remaining until market close (ET). Returns 0 if closed."""
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo  # type: ignore

        et = ZoneInfo("America/New_York")
        now_et = datetime.now(tz=et)
        if now_et.weekday() >= 5:
            return 0
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        if now_et >= market_close:
            return 0
        delta = market_close - now_et
        return int(delta.total_seconds() / 60)

    def minutes_since_open(self) -> int:
        """Return minutes elapsed since market open (ET). Returns 0 if not open."""
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo  # type: ignore

        et = ZoneInfo("America/New_York")
        now_et = datetime.now(tz=et)
        if now_et.weekday() >= 5:
            return 0
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        if now_et < market_open:
            return 0
        delta = now_et - market_open
        return int(delta.total_seconds() / 60)

    def get_single_symbol_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        limit: int = 200,
    ) -> pd.DataFrame:
        """
        Convenience wrapper to fetch bars for a single symbol and
        return a simple (non-multi-index) DataFrame.

        Returns
        -------
        pd.DataFrame
            Columns: ``open, high, low, close, volume`` indexed by timestamp.
        """
        df = self.get_bars([symbol], timeframe=timeframe, limit=limit)
        if df.empty:
            return pd.DataFrame()
        try:
            return df.xs(symbol, level="symbol")
        except KeyError:
            return df
