"""
risk/risk_manager.py
--------------------
Position sizing, stop-loss computation, portfolio heat checks,
daily drawdown circuit-breaker, and correlation guard.
"""
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class SizingResult:
    shares: int
    dollar_risk: float
    stop_price: float
    take_profit_price: float
    max_loss: float

class RiskManager:
    """
    All risk management logic for the trading bot.

    Key rules:
    - Risk at most 1% of portfolio per trade (fixed-fractional).
    - Hard cap: no single position > MAX_POSITION_SIZE of portfolio.
    - Portfolio heat (total open risk) capped at MAX_PORTFOLIO_HEAT.
    - Daily drawdown circuit-breaker: halt if day P&L < -MAX_DAILY_DRAWDOWN * portfolio.
    - Correlation guard: skip if too many correlated positions already open.
    - ATR-based stops for volatility-adjusted sizing.
    - Max MAX_SHORT_POSITIONS short positions at any time.
    """

    def __init__(self, settings=None):
        from config.settings import Settings
        self.cfg = settings or Settings()

    def calculate_position_size(
        self,
        symbol: str,
        current_price: float,
        portfolio_value: float,
        atr: float,
        side: str = "long",   # "long" | "short"
        confidence: float = 0.5,
    ) -> SizingResult:
        """
        Fixed-fractional sizing: risk 1% of portfolio per trade.
        Stop is placed at 1.5x ATR from entry (or cfg.STOP_LOSS_PCT minimum).

        confidence scales position size linearly between 50%-100% of computed size.
        """
        # ATR-based stop distance
        atr_stop_distance = max(atr * 1.5, current_price * self.cfg.STOP_LOSS_PCT)
        stop_price = (
            current_price - atr_stop_distance if side == "long"
            else current_price + atr_stop_distance
        )

        # Dollar risk per share
        risk_per_share = abs(current_price - stop_price)
        if risk_per_share < 0.01:
            risk_per_share = current_price * self.cfg.STOP_LOSS_PCT

        # Total dollar risk allowed
        base_risk_dollars = portfolio_value * 0.01  # 1% risk
        adjusted_risk_dollars = base_risk_dollars * (0.5 + 0.5 * confidence)

        # Raw share count
        raw_shares = adjusted_risk_dollars / risk_per_share

        # Hard cap by max position size
        max_dollars = portfolio_value * self.cfg.MAX_POSITION_SIZE
        capped_shares = min(raw_shares, max_dollars / current_price)

        shares = max(1, int(capped_shares))

        # Take profit: 2:1 reward/risk minimum (or cfg.TAKE_PROFIT_PCT)
        tp_distance = max(risk_per_share * 2, current_price * self.cfg.TAKE_PROFIT_PCT)
        take_profit_price = (
            current_price + tp_distance if side == "long"
            else current_price - tp_distance
        )

        dollar_risk = shares * risk_per_share
        max_loss = shares * risk_per_share

        logger.debug(
            f"{symbol}: size={shares} shares, entry={current_price:.2f}, "
            f"stop={stop_price:.2f}, tp={take_profit_price:.2f}, "
            f"risk=${dollar_risk:.2f}"
        )

        return SizingResult(
            shares=shares,
            dollar_risk=dollar_risk,
            stop_price=round(stop_price, 2),
            take_profit_price=round(take_profit_price, 2),
            max_loss=max_loss,
        )

    def check_portfolio_heat(
        self,
        positions: list[dict],
        portfolio_value: float,
        proposed_dollar_risk: float,
    ) -> bool:
        """
        Returns True if adding *proposed_dollar_risk* keeps total heat
        under MAX_PORTFOLIO_HEAT.
        positions: list of dicts with keys 'unrealized_pl', 'market_value'
        """
        current_heat = sum(
            abs(float(p.get("unrealized_pl", 0))) for p in positions
        ) / max(portfolio_value, 1)

        new_heat = current_heat + proposed_dollar_risk / max(portfolio_value, 1)
        ok = new_heat <= self.cfg.MAX_PORTFOLIO_HEAT
        if not ok:
            logger.warning(
                f"Portfolio heat {new_heat:.1%} would exceed "
                f"{self.cfg.MAX_PORTFOLIO_HEAT:.1%} limit"
            )
        return ok

    def check_short_capacity(self, positions: list[dict]) -> bool:
        """Returns True if we can open another short position."""
        short_count = sum(1 for p in positions if float(p.get("qty", 0)) < 0)
        ok = short_count < self.cfg.MAX_SHORT_POSITIONS
        if not ok:
            logger.warning(f"Max short positions ({self.cfg.MAX_SHORT_POSITIONS}) reached")
        return ok

    def check_daily_drawdown(
        self,
        daily_pnl: float,
        portfolio_value: float,
    ) -> bool:
        """
        Returns True (HALT trading) if daily P&L exceeds the max drawdown limit.
        """
        drawdown_pct = abs(min(daily_pnl, 0)) / max(portfolio_value, 1)
        halt = drawdown_pct >= self.cfg.MAX_DAILY_DRAWDOWN
        if halt:
            logger.critical(
                f"CIRCUIT BREAKER: daily drawdown {drawdown_pct:.1%} >= "
                f"{self.cfg.MAX_DAILY_DRAWDOWN:.1%}. Halting trading."
            )
        return halt

    def is_correlated(
        self,
        symbol: str,
        existing_symbols: list[str],
        sector_map: dict[str, str],
        max_per_sector: int = 3,
    ) -> bool:
        """
        Returns True if adding *symbol* would exceed max_per_sector in the same sector.
        sector_map: {symbol: sector_name}
        """
        target_sector = sector_map.get(symbol, "Unknown")
        if target_sector == "Unknown":
            return False
        count = sum(
            1 for s in existing_symbols
            if sector_map.get(s, "") == target_sector
        )
        over = count >= max_per_sector
        if over:
            logger.info(
                f"Skipping {symbol}: already {count} positions in {target_sector}"
            )
        return over

    def get_trailing_stop(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        current_price: float,
        atr: float,
    ) -> float:
        """
        Compute a trailing stop price.
        For longs:  max(entry_stop, current_price - 2*ATR)
        For shorts: min(entry_stop, current_price + 2*ATR)
        """
        trail_distance = atr * 2
        if side == "long":
            initial_stop = entry_price * (1 - self.cfg.STOP_LOSS_PCT)
            return max(initial_stop, current_price - trail_distance)
        else:
            initial_stop = entry_price * (1 + self.cfg.STOP_LOSS_PCT)
            return min(initial_stop, current_price + trail_distance)

    def should_force_exit(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        current_price: float,
    ) -> tuple[bool, str]:
        """
        Hard stop-loss check (backup for bracket orders that may slip).
        Returns (should_exit, reason).
        """
        if side == "long":
            loss_pct = (entry_price - current_price) / entry_price
            if loss_pct >= self.cfg.STOP_LOSS_PCT * 1.5:
                return True, f"Hard stop: loss {loss_pct:.1%} on {symbol}"
        else:
            loss_pct = (current_price - entry_price) / entry_price
            if loss_pct >= self.cfg.STOP_LOSS_PCT * 1.5:
                return True, f"Hard stop: loss {loss_pct:.1%} on short {symbol}"
        return False, ""
