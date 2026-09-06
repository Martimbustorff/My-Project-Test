"""
research/packet.py
------------------
"Step 2 — gather the raw material" of the AI Hedge Fund Team workflow.

The guide's key principle is that **the AI is the analyst, not the database**:
every number an agent uses must come from something real that was handed to it.
This module assembles that real material for a ticker — key statistics and a
price-history CSV pulled from the provider — and, just as importantly, lists
what it could *not* get so the gap is visible rather than silently filled.

Anything unavailable is marked ``NOT AVAILABLE — verify manually``, exactly as
the agent rules require. Documents a machine cannot fetch (filings, dated
headlines, chart screenshots) are listed as manual inputs for the human.

This module owns the I/O; :mod:`research.stack` is the pure assembly step.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

NOT_AVAILABLE = "NOT AVAILABLE — verify manually"

# Raw material the workflow needs that no data feed can supply for you.
MANUAL_INPUTS: tuple[str, ...] = (
    "Latest earnings release and 10-K / 10-Q excerpts from the company's "
    "investor-relations page.",
    "Screenshots of the 6-month and 2-year price charts.",
    "The key-statistics page from a finance site (or your broker).",
    "Three to five recent news headlines, each with its date and link.",
)


@dataclass
class ResearchPacket:
    """The gathered raw material for one ticker."""

    symbol: str
    generated_at: str
    key_stats: dict[str, str] = field(default_factory=dict)
    price_history_csv: Optional[str] = None
    history_period: Optional[str] = None
    history_rows: int = 0
    manual_inputs: tuple[str, ...] = MANUAL_INPUTS
    fetch_errors: list[str] = field(default_factory=list)

    @property
    def has_price_history(self) -> bool:
        return bool(self.price_history_csv) and self.history_rows > 0

    @property
    def missing_stats(self) -> list[str]:
        """Stats the provider did not return, so the agents must not use them."""
        return [k for k, v in self.key_stats.items() if v == NOT_AVAILABLE]


def _fmt(value, suffix: str = "", pct: bool = False) -> str:
    """Format a value for the stats table, or mark it unavailable."""
    if value is None:
        return NOT_AVAILABLE
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if pct:
        return f"{number * 100:+.1f}%"
    if abs(number) >= 1_000_000_000:
        return f"{number / 1_000_000_000:,.2f}B{suffix}"
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:,.2f}M{suffix}"
    return f"{number:,.2f}{suffix}"


def build_packet(symbol: str, history_period: str = "2y") -> ResearchPacket:
    """
    Gather the machine-fetchable raw material for *symbol*.

    Key statistics come from the same screener the watchlist uses, so the two
    systems agree on the numbers. The price history is exported as CSV for the
    Quant Analyst, which the guide requires so it computes rather than imagines.
    Never fabricates: a field the provider does not return is recorded as
    ``NOT AVAILABLE — verify manually``.
    """
    symbol = symbol.strip().upper()
    packet = ResearchPacket(
        symbol=symbol,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        history_period=history_period,
    )

    # ── Key statistics, via the watchlist screener ───────────────────────
    try:
        from watchlist.screener import Screener
        from watchlist.universe import candidates_from_tickers

        candidate = candidates_from_tickers([symbol])[0]
        metrics = Screener().screen_one(candidate)
    except Exception as exc:
        logger.warning("Key-stats fetch failed for %s: %s", symbol, exc)
        packet.fetch_errors.append(f"key statistics: {exc}")
        metrics = None

    if metrics is None:
        packet.fetch_errors.append(
            f"No key statistics returned for {symbol}."
        )
        packet.key_stats = {
            label: NOT_AVAILABLE
            for label in (
                "Company name", "Exchange", "Currency", "Current price",
                "Market cap", "Analyst mean target", "Implied upside",
                "Revenue growth (YoY)", "Revenue CAGR", "Earnings growth",
                "Analyst recommendation (1=Strong Buy, 5=Strong Sell)",
                "Number of analysts", "3-month price change",
            )
        }
        return packet

    packet.key_stats = {
        "Company name": metrics.name or NOT_AVAILABLE,
        "Exchange": metrics.exchange or NOT_AVAILABLE,
        "Currency": metrics.currency or NOT_AVAILABLE,
        "Current price": _fmt(metrics.current_price),
        "Market cap": _fmt(metrics.market_cap),
        "Analyst mean target": _fmt(metrics.target_mean_price),
        "Implied upside": _fmt(metrics.upside_pct, pct=True),
        "Revenue growth (YoY)": _fmt(metrics.revenue_growth, pct=True),
        "Revenue CAGR": _fmt(metrics.revenue_cagr, pct=True),
        "Earnings growth": _fmt(metrics.earnings_growth, pct=True),
        "Analyst recommendation (1=Strong Buy, 5=Strong Sell)":
            _fmt(metrics.recommendation_mean),
        "Number of analysts": _fmt(metrics.num_analysts),
        "3-month price change": _fmt(metrics.price_change_3m, pct=True),
    }

    # ── Price history CSV for the Quant Analyst ──────────────────────────
    csv_text, rows = _fetch_history_csv(symbol, history_period)
    if csv_text is None:
        packet.fetch_errors.append(
            f"No price history returned for {symbol} ({history_period})."
        )
    packet.price_history_csv = csv_text
    packet.history_rows = rows
    return packet


def _fetch_history_csv(symbol: str, period: str) -> tuple[Optional[str], int]:
    """Return (csv_text, row_count) of daily closes, or (None, 0) on failure."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance is not installed — cannot export price history.")
        return None, 0

    try:
        hist = yf.Ticker(symbol).history(period=period, interval="1d")
        if hist is None or hist.empty:
            return None, 0
        columns = [c for c in ("Open", "High", "Low", "Close", "Volume")
                   if c in hist.columns]
        frame = hist[columns].dropna()
        frame.index = frame.index.strftime("%Y-%m-%d")
        frame.index.name = "Date"
        return frame.to_csv(), len(frame)
    except Exception as exc:
        logger.warning("History fetch failed for %s: %s", symbol, exc)
        return None, 0
