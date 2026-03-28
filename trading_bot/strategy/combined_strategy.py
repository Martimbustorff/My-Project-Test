"""
strategy/combined_strategy.py
------------------------------
Top-level strategy that orchestrates the full signal generation pipeline
for every symbol in the trading universe:

    fetch bars → compute indicators → fetch news → sentiment → signal

Filters actionable signals for execution and provides market context.
"""

import logging
from typing import Optional

import pandas as pd
import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)

# Sector mapping for symbols (used for correlation / exposure checks)
SYMBOL_SECTOR = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "AMZN": "Consumer Discretionary", "NVDA": "Technology", "META": "Technology",
    "TSLA": "Consumer Discretionary", "BRK-B": "Financials", "JPM": "Financials",
    "V": "Financials", "UNH": "Healthcare", "JNJ": "Healthcare",
    "XOM": "Energy", "WMT": "Consumer Staples", "MA": "Financials",
    "PG": "Consumer Staples", "HD": "Consumer Discretionary", "CVX": "Energy",
    "LLY": "Healthcare", "MRK": "Healthcare", "ABBV": "Healthcare",
    "PFE": "Healthcare", "AVGO": "Technology", "COST": "Consumer Staples",
    "KO": "Consumer Staples", "PEP": "Consumer Staples", "TMO": "Healthcare",
    "CSCO": "Technology", "ACN": "Technology", "MCD": "Consumer Discretionary",
    "ABT": "Healthcare", "DHR": "Healthcare", "TXN": "Technology",
    "NEE": "Utilities", "WFC": "Financials", "BMY": "Healthcare",
    "CRM": "Technology", "QCOM": "Technology", "ORCL": "Technology",
    "AMD": "Technology", "INTC": "Technology", "HON": "Industrials",
    "UPS": "Industrials", "CAT": "Industrials", "BA": "Industrials",
    "GS": "Financials", "MS": "Financials", "AMGN": "Healthcare",
    "INTU": "Technology", "SBUX": "Consumer Discretionary",
}


class TradingStrategy:
    """
    Multi-factor trading strategy combining technical analysis, sentiment,
    momentum, and fundamental scoring.

    Parameters
    ----------
    market_data : MarketDataFetcher
    news_fetcher : NewsFetcher
    technical_analyzer : TechnicalAnalyzer
    sentiment_analyzer : SentimentAnalyzer
    signal_generator : SignalGenerator
    risk_manager : RiskManager
    """

    def __init__(
        self,
        market_data,
        news_fetcher,
        technical_analyzer,
        sentiment_analyzer,
        signal_generator,
        risk_manager,
    ):
        self._market_data = market_data
        self._news_fetcher = news_fetcher
        self._technical = technical_analyzer
        self._sentiment = sentiment_analyzer
        self._signal_gen = signal_generator
        self._risk = risk_manager

        # Caches to avoid redundant network calls within a single cycle
        self._news_cache: dict[str, list[dict]] = {}
        self._sentiment_cache: dict[str, float] = {}
        self._fundamentals_cache: dict[str, dict] = {}
        self._atr_cache: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Main scan
    # ------------------------------------------------------------------

    def scan_universe(
        self,
        symbols: list[str],
        portfolio_manager,
        market_context: Optional[dict] = None,
    ) -> dict:
        """
        Generate signals for all symbols in *symbols*.

        Parameters
        ----------
        symbols : list[str]
            Tickers to scan.
        portfolio_manager : PortfolioManager
            Current portfolio state (for position checks).
        market_context : dict, optional
            Pre-fetched market context dict.  Fetched fresh if None.

        Returns
        -------
        dict
            Mapping of ``symbol -> Signal`` for all scanned symbols.
        """
        if market_context is None:
            market_context = self.get_market_context()

        market_regime = market_context.get("market_regime", "neutral")
        vix = market_context.get("vix", 20.0)

        signals: dict = {}
        positions = portfolio_manager.get_all_positions()

        logger.info("Scanning %d symbols (regime=%s, VIX=%.1f)…", len(symbols), market_regime, vix)

        # Batch fetch bars for all symbols at once
        bars_map = self._fetch_bars_batch(symbols)

        for symbol in symbols:
            try:
                signal = self._generate_signal_for_symbol(
                    symbol=symbol,
                    bars_map=bars_map,
                    positions=positions,
                    market_regime=market_regime,
                    vix=vix,
                )
                if signal:
                    signals[symbol] = signal
                    # Cache ATR
                    if symbol in bars_map:
                        df = bars_map[symbol]
                        if not df.empty and "atr" in df.columns:
                            atr_val = df["atr"].dropna()
                            if not atr_val.empty:
                                self._atr_cache[symbol] = float(atr_val.iloc[-1])
            except Exception as exc:
                logger.error("scan_universe error for %s: %s", symbol, exc, exc_info=False)

        actionable = sum(1 for s in signals.values() if str(getattr(s, "action", "HOLD")) not in ("HOLD", "Action.HOLD"))
        logger.info("Scan complete: %d signals, %d actionable.", len(signals), actionable)
        return signals

    def _generate_signal_for_symbol(
        self,
        symbol: str,
        bars_map: dict,
        positions: dict,
        market_regime: str,
        vix: float,
    ):
        """Generate a signal for a single symbol."""
        # ---- Price data & indicators ----
        df = bars_map.get(symbol, pd.DataFrame())
        if df.empty:
            logger.debug("No bars for %s, skipping.", symbol)
            return None

        # Standardise columns
        df.columns = [c.lower() for c in df.columns]
        df = self._technical.compute_indicators(df)

        # Extract ATR for position sizing
        atr = 0.0
        if "atr" in df.columns:
            atr_series = df["atr"].dropna()
            if not atr_series.empty:
                atr = float(atr_series.iloc[-1])

        # ---- Technical score ----
        tech_score = self._technical.get_technical_signal(df)

        # ---- News & Sentiment ----
        news = self._get_cached_news(symbol)
        sentiment_score = self._get_cached_sentiment(symbol, news)

        # ---- Fundamentals ----
        fundamentals = self._get_cached_fundamentals(symbol)

        # ---- Current position ----
        pos = positions.get(symbol, {})
        is_long = pos.get("side") == "long" and float(pos.get("qty", 0)) > 0
        is_short = pos.get("side") == "short" and float(pos.get("qty", 0)) < 0

        # ---- Check shortability ----
        is_shortable = True
        try:
            is_shortable = self._market_data._client is None or True  # Default to True; broker checks at execution
        except Exception:
            is_shortable = True

        # ---- Generate signal ----
        signal = self._signal_gen.generate_signal(
            symbol=symbol,
            price_df=df,
            technical_score=tech_score,
            sentiment_score=sentiment_score,
            news_items=news,
            fundamentals=fundamentals,
            market_regime=market_regime,
            vix=vix,
            is_long=is_long,
            is_short=is_short,
            is_shortable=is_shortable,
        )

        # Log signal
        action_str = signal.action.value if hasattr(signal.action, "value") else str(signal.action)
        if action_str != "HOLD":
            logger.info(
                "Signal %s: %s (score=%.2f, conf=%.2f)",
                symbol, action_str,
                getattr(signal, "combined_score", 0),
                getattr(signal, "confidence", 0),
            )

        return signal

    # ------------------------------------------------------------------
    # Signal filtering
    # ------------------------------------------------------------------

    def filter_actionable_signals(
        self,
        signals: dict,
        portfolio_manager,
        max_signals: int = 10,
    ) -> list:
        """
        Filter and rank signals, returning only those worth acting on.

        Rules applied:
        1. Exclude HOLD signals
        2. Exclude symbols that already have an open position (unless SELL/COVER)
        3. Correlation filter: limit signals per sector
        4. Sort by confidence descending
        5. Return top *max_signals*

        Parameters
        ----------
        signals : dict
            ``symbol -> Signal`` mapping from :meth:`scan_universe`.
        portfolio_manager : PortfolioManager
            Current portfolio state.
        max_signals : int
            Maximum number of signals to return.

        Returns
        -------
        list[Signal]
            Filtered, ranked list of actionable signals.
        """
        from analysis.signals import Action

        positions = portfolio_manager.get_all_positions()
        sector_count: dict[str, int] = {}
        MAX_PER_SECTOR = 3

        actionable = []

        for symbol, signal in signals.items():
            action_val = signal.action.value if hasattr(signal.action, "value") else str(signal.action)

            # Skip HOLD
            if action_val == "HOLD":
                continue

            # SELL / COVER: always include (position management)
            if action_val in ("SELL", "COVER"):
                actionable.append(signal)
                continue

            # Skip if already positioned in the same direction
            pos = positions.get(symbol)
            if pos:
                side = pos.get("side", "")
                if action_val == "BUY" and side == "long":
                    continue
                if action_val == "SHORT" and side == "short":
                    continue

            # Sector concentration check
            sector = SYMBOL_SECTOR.get(symbol, "Unknown")
            sector_count[sector] = sector_count.get(sector, 0)
            if sector_count[sector] >= MAX_PER_SECTOR:
                logger.debug(
                    "Skipping %s (%s): sector already has %d signals",
                    symbol, sector, sector_count[sector],
                )
                continue

            sector_count[sector] += 1
            actionable.append(signal)

        # Sort by confidence descending
        actionable.sort(key=lambda s: getattr(s, "confidence", 0), reverse=True)

        # Prioritise exits over entries
        exits = [s for s in actionable if (s.action.value if hasattr(s.action, "value") else str(s.action)) in ("SELL", "COVER")]
        entries = [s for s in actionable if (s.action.value if hasattr(s.action, "value") else str(s.action)) not in ("SELL", "COVER")]

        result = exits + entries[:max(0, max_signals - len(exits))]
        return result[:max_signals]

    def get_atr_map(self) -> dict[str, float]:
        """Return the cached ATR map for use by the order manager."""
        return dict(self._atr_cache)

    # ------------------------------------------------------------------
    # Market context
    # ------------------------------------------------------------------

    def get_market_context(self) -> dict:
        """
        Fetch and return a market context snapshot.

        Returns
        -------
        dict
            Keys: ``market_regime``, ``vix``, ``sector_performance``,
            ``is_market_open``, ``timestamp``.
        """
        from datetime import datetime, timezone

        context = {
            "market_regime": "neutral",
            "vix": 20.0,
            "sector_performance": {},
            "is_market_open": False,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

        try:
            context["market_regime"] = self._market_data.get_market_regime()
        except Exception as exc:
            logger.warning("Market regime fetch error: %s", exc)

        try:
            context["vix"] = self._market_data.get_vix()
        except Exception as exc:
            logger.warning("VIX fetch error: %s", exc)

        try:
            context["sector_performance"] = self._market_data.get_sector_performance()
        except Exception as exc:
            logger.warning("Sector performance fetch error: %s", exc)

        try:
            context["is_market_open"] = self._market_data.is_market_open()
        except Exception as exc:
            logger.warning("Market open check error: %s", exc)

        return context

    # ------------------------------------------------------------------
    # News / sentiment cache management
    # ------------------------------------------------------------------

    def refresh_news_cache(self, symbols: list[str]) -> None:
        """
        Pre-fetch and cache news for all symbols.
        Call this on the hourly news refresh schedule.
        """
        logger.info("Refreshing news cache for %d symbols…", len(symbols))
        for symbol in symbols:
            try:
                news = self._news_fetcher.fetch_news(symbol, days_back=settings.NEWS_DAYS_BACK)
                self._news_cache[symbol] = news
                if news:
                    score = self._sentiment.get_symbol_sentiment(symbol, news)
                    self._sentiment_cache[symbol] = score
                    logger.debug("Cached news/sentiment for %s (articles=%d, score=%.2f)", symbol, len(news), score)
            except Exception as exc:
                logger.warning("News cache refresh error for %s: %s", symbol, exc)

    def refresh_fundamentals_cache(self, symbols: list[str]) -> None:
        """Pre-fetch and cache fundamental data for all symbols (daily)."""
        logger.info("Refreshing fundamentals cache for %d symbols…", len(symbols))
        for symbol in symbols:
            try:
                fundamentals = self._market_data.get_fundamentals(symbol)
                self._fundamentals_cache[symbol] = fundamentals
            except Exception as exc:
                logger.warning("Fundamentals cache error for %s: %s", symbol, exc)

    def clear_caches(self) -> None:
        """Clear all in-memory caches."""
        self._news_cache.clear()
        self._sentiment_cache.clear()
        self._fundamentals_cache.clear()
        self._atr_cache.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_bars_batch(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV bars for a batch of symbols."""
        bars_map: dict[str, pd.DataFrame] = {}

        # Try Alpaca batch fetch first
        try:
            if self._market_data._client is not None:
                raw = self._market_data.get_bars(symbols, timeframe="1Day", limit=settings.BARS_LIMIT)
                if not raw.empty:
                    # Unstack by symbol
                    for sym in symbols:
                        try:
                            df = raw.xs(sym, level="symbol") if "symbol" in raw.index.names else raw
                            bars_map[sym] = df
                        except (KeyError, TypeError):
                            pass
                    if bars_map:
                        return bars_map
        except Exception as exc:
            logger.debug("Batch Alpaca bars failed: %s; falling back to per-symbol", exc)

        # Per-symbol yfinance fallback
        for sym in symbols:
            try:
                df = self._market_data.get_single_symbol_bars(sym, timeframe="1Day", limit=settings.BARS_LIMIT)
                if not df.empty:
                    bars_map[sym] = df
            except Exception as exc:
                logger.warning("Bars fetch error for %s: %s", sym, exc)

        return bars_map

    def _get_cached_news(self, symbol: str) -> list[dict]:
        """Return cached news, or fetch fresh if not cached."""
        if symbol in self._news_cache:
            return self._news_cache[symbol]
        try:
            news = self._news_fetcher.fetch_news(symbol, days_back=settings.NEWS_DAYS_BACK)
            self._news_cache[symbol] = news
            return news
        except Exception as exc:
            logger.warning("News fetch error for %s: %s", symbol, exc)
            return []

    def _get_cached_sentiment(self, symbol: str, news: list[dict]) -> float:
        """Return cached sentiment score, or compute fresh."""
        if symbol in self._sentiment_cache:
            return self._sentiment_cache[symbol]
        try:
            score = self._sentiment.get_symbol_sentiment(symbol, news)
            self._sentiment_cache[symbol] = score
            return score
        except Exception as exc:
            logger.warning("Sentiment error for %s: %s", symbol, exc)
            return 0.0

    def _get_cached_fundamentals(self, symbol: str) -> dict:
        """Return cached fundamentals, or fetch fresh."""
        if symbol in self._fundamentals_cache:
            return self._fundamentals_cache[symbol]
        try:
            fundamentals = self._market_data.get_fundamentals(symbol)
            self._fundamentals_cache[symbol] = fundamentals
            return fundamentals
        except Exception as exc:
            logger.warning("Fundamentals error for %s: %s", symbol, exc)
            return {}
