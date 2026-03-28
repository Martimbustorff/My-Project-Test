"""
portfolio/portfolio_manager.py
------------------------------
Maintains a live mirror of the broker portfolio state.
Provides P&L tracking, exposure metrics, and performance statistics.
"""
import logging
from typing import Optional
from datetime import datetime, date
import pandas as pd

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Caches and exposes portfolio state synced from the broker.

    Call refresh(broker) periodically to sync. All read methods
    work off the cached state for speed.
    """

    def __init__(self):
        self._positions: dict[str, dict] = {}    # symbol -> position dict
        self._portfolio_value: float = 0.0
        self._cash: float = 0.0
        self._buying_power: float = 0.0
        self._equity: float = 0.0
        self._day_start_value: float = 0.0       # set once per day
        self._last_refresh: Optional[datetime] = None
        self._today: Optional[date] = None

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def refresh(self, broker) -> None:
        """Sync all state from broker. Call every 1-5 minutes."""
        try:
            acct = broker.get_account()
            self._equity         = acct["equity"]
            self._portfolio_value = acct["portfolio_value"]
            self._cash           = acct["cash"]
            self._buying_power   = acct["buying_power"]

            # Track day-start value (reset daily)
            today = date.today()
            if self._today != today or self._day_start_value == 0.0:
                self._day_start_value = self._portfolio_value
                self._today = today

            # Refresh positions
            raw_positions = broker.get_positions()
            self._positions = {p["symbol"]: p for p in raw_positions}

            self._last_refresh = datetime.utcnow()
            logger.debug(
                f"Portfolio refreshed: value=${self._portfolio_value:,.2f}, "
                f"positions={len(self._positions)}"
            )
        except Exception as e:
            logger.error(f"Portfolio refresh failed: {e}")

    # ------------------------------------------------------------------
    # Position queries
    # ------------------------------------------------------------------

    def get_position(self, symbol: str) -> Optional[dict]:
        return self._positions.get(symbol)

    def get_all_positions(self) -> dict[str, dict]:
        return dict(self._positions)

    def is_long(self, symbol: str) -> bool:
        pos = self._positions.get(symbol)
        return pos is not None and pos["qty"] > 0

    def is_short(self, symbol: str) -> bool:
        pos = self._positions.get(symbol)
        return pos is not None and pos["qty"] < 0

    def has_position(self, symbol: str) -> bool:
        return symbol in self._positions

    def get_position_side(self, symbol: str) -> Optional[str]:
        pos = self._positions.get(symbol)
        if pos is None:
            return None
        return "long" if pos["qty"] > 0 else "short"

    def get_unrealized_pnl(self, symbol: str) -> float:
        pos = self._positions.get(symbol)
        return pos["unrealized_pl"] if pos else 0.0

    def count_long_positions(self) -> int:
        return sum(1 for p in self._positions.values() if p["qty"] > 0)

    def count_short_positions(self) -> int:
        return sum(1 for p in self._positions.values() if p["qty"] < 0)

    def get_symbols(self) -> list[str]:
        return list(self._positions.keys())

    # ------------------------------------------------------------------
    # Portfolio metrics
    # ------------------------------------------------------------------

    def get_portfolio_value(self) -> float:
        return self._portfolio_value

    def get_equity(self) -> float:
        return self._equity

    def get_cash(self) -> float:
        return self._cash

    def get_buying_power(self) -> float:
        return self._buying_power

    def get_daily_pnl(self) -> float:
        """Unrealised daily P&L vs day-start value."""
        return self._portfolio_value - self._day_start_value

    def get_daily_pnl_pct(self) -> float:
        if self._day_start_value == 0:
            return 0.0
        return self.get_daily_pnl() / self._day_start_value

    def get_total_unrealized_pnl(self) -> float:
        return sum(p["unrealized_pl"] for p in self._positions.values())

    def get_exposure(self) -> dict:
        """Return long/short/net exposure as fraction of portfolio value."""
        pv = max(self._portfolio_value, 1)
        long_mv  = sum(p["market_value"] for p in self._positions.values() if p["qty"] > 0)
        short_mv = sum(abs(p["market_value"]) for p in self._positions.values() if p["qty"] < 0)
        return {
            "long_exposure":  long_mv  / pv,
            "short_exposure": short_mv / pv,
            "net_exposure":   (long_mv - short_mv) / pv,
            "gross_exposure": (long_mv + short_mv) / pv,
            "long_dollar":    long_mv,
            "short_dollar":   short_mv,
        }

    def get_largest_positions(self, n: int = 5) -> list[dict]:
        """Return top N positions by absolute market value."""
        sorted_pos = sorted(
            self._positions.values(),
            key=lambda p: abs(p.get("market_value", 0)),
            reverse=True,
        )
        return sorted_pos[:n]

    def get_performance_summary(self) -> dict:
        """Return a summary dict suitable for logging/display."""
        exp = self.get_exposure()
        return {
            "portfolio_value":     self._portfolio_value,
            "equity":              self._equity,
            "cash":                self._cash,
            "buying_power":        self._buying_power,
            "daily_pnl":           self.get_daily_pnl(),
            "daily_pnl_pct":       self.get_daily_pnl_pct(),
            "total_unrealized_pnl":self.get_total_unrealized_pnl(),
            "long_positions":      self.count_long_positions(),
            "short_positions":     self.count_short_positions(),
            "net_exposure_pct":    exp["net_exposure"],
            "gross_exposure_pct":  exp["gross_exposure"],
            "last_refresh":        str(self._last_refresh),
        }

    def positions_to_dataframe(self) -> pd.DataFrame:
        """Return positions as a DataFrame for display / analysis."""
        if not self._positions:
            return pd.DataFrame()
        rows = list(self._positions.values())
        df = pd.DataFrame(rows)
        df["pnl_pct"] = df["unrealized_plpc"] * 100
        return df[["symbol","side","qty","avg_entry_price","current_price",
                   "market_value","unrealized_pl","pnl_pct"]]
