"""
backtesting/backtest.py
-----------------------
Event-driven backtester that replays historical OHLCV data through the
same indicator + signal pipeline used in live trading, then computes a
full suite of performance metrics.

No lookahead bias: on each bar only data up to and including that bar
is used. Entries execute at the *next* bar's open (realistic fill).

Usage
-----
    from backtesting.backtest import Backtester, BacktestConfig
    from datetime import date

    cfg = BacktestConfig(
        symbols=["AAPL", "MSFT", "NVDA"],
        start_date=date(2023, 1, 1),
        end_date=date(2024, 1, 1),
        initial_capital=100_000.0,
    )
    bt = Backtester(cfg)
    results = bt.run()
    results.print_summary()
    results.plot_equity_curve()      # requires matplotlib
    df = results.to_dataframe()      # one row per closed trade
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BacktestConfig:
    symbols: list[str]
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    commission_per_trade: float = 0.0        # $ per trade (each leg)
    slippage_bps: float = 5.0                # basis points on entry
    max_position_size: float = 0.05          # fraction of portfolio
    stop_loss_pct: float = 0.05              # 5% hard stop
    take_profit_pct: float = 0.15            # 15% take-profit
    risk_per_trade: float = 0.01             # 1% of portfolio risked
    max_portfolio_heat: float = 0.20         # max total open risk
    timeframe: str = "1Day"
    signal_threshold: float = 0.35           # |score| needed to enter
    atr_period: int = 14
    atr_stop_multiplier: float = 1.5         # stop = entry ± ATR * multiplier
    max_positions: int = 10                  # max concurrent open positions


# ─────────────────────────────────────────────────────────────────────────────
# Trade record
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Trade:
    symbol: str
    side: str                    # "long" | "short"
    entry_date: date
    exit_date: Optional[date]
    entry_price: float
    exit_price: float
    shares: int
    pnl: float                   # net of commission + slippage
    pnl_pct: float
    exit_reason: str             # "stop_loss" | "take_profit" | "signal" | "end_of_backtest"
    stop_price: float
    take_profit_price: float
    commission: float
    slippage_cost: float

    @property
    def gross_pnl(self) -> float:
        if self.side == "long":
            return (self.exit_price - self.entry_price) * self.shares
        return (self.entry_price - self.exit_price) * self.shares

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0


# ─────────────────────────────────────────────────────────────────────────────
# Open position (internal)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _OpenPosition:
    symbol: str
    side: str
    entry_date: date
    entry_price: float
    shares: int
    stop_price: float
    take_profit_price: float
    commission: float
    slippage_cost: float


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BacktestResults:
    trades: list[Trade]
    equity_curve: pd.Series        # index=date, values=portfolio value
    daily_returns: pd.Series       # index=date, values=daily % return
    config: BacktestConfig

    # ── Metrics ──────────────────────────────────────────────────────────────

    def total_return(self) -> float:
        if self.equity_curve.empty:
            return 0.0
        return (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0]) - 1

    def annualised_return(self) -> float:
        if self.equity_curve.empty or len(self.equity_curve) < 2:
            return 0.0
        days = (self.equity_curve.index[-1] - self.equity_curve.index[0]).days
        if days <= 0:
            return 0.0
        return (1 + self.total_return()) ** (365.0 / days) - 1

    def sharpe_ratio(self, risk_free: float = 0.04) -> float:
        if self.daily_returns.empty or self.daily_returns.std() == 0:
            return 0.0
        excess = self.daily_returns - risk_free / 252
        return float(excess.mean() / excess.std() * math.sqrt(252))

    def max_drawdown(self) -> float:
        if self.equity_curve.empty:
            return 0.0
        roll_max = self.equity_curve.cummax()
        drawdown = (self.equity_curve - roll_max) / roll_max
        return float(drawdown.min())

    def win_rate(self) -> float:
        closed = [t for t in self.trades if t.exit_date is not None]
        if not closed:
            return 0.0
        return sum(1 for t in closed if t.is_winner) / len(closed)

    def profit_factor(self) -> float:
        gross_wins  = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_losses = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        if gross_losses == 0:
            return float("inf") if gross_wins > 0 else 0.0
        return gross_wins / gross_losses

    def avg_trade_pnl(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.pnl for t in self.trades) / len(self.trades)

    def avg_win(self) -> float:
        winners = [t.pnl for t in self.trades if t.pnl > 0]
        return sum(winners) / len(winners) if winners else 0.0

    def avg_loss(self) -> float:
        losers = [t.pnl for t in self.trades if t.pnl < 0]
        return sum(losers) / len(losers) if losers else 0.0

    def total_trades(self) -> int:
        return len(self.trades)

    def long_trades(self) -> int:
        return sum(1 for t in self.trades if t.side == "long")

    def short_trades(self) -> int:
        return sum(1 for t in self.trades if t.side == "short")

    def calmar_ratio(self) -> float:
        dd = self.max_drawdown()
        if dd == 0:
            return 0.0
        return self.annualised_return() / abs(dd)

    # ── Display ──────────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        try:
            from rich.console import Console
            from rich.table import Table
            from rich import box

            console = Console()
            table = Table(
                title="Backtest Results",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Metric",  style="bold", width=28)
            table.add_column("Value",   justify="right", width=18)

            def _pct(v: float) -> str:
                color = "green" if v >= 0 else "red"
                return f"[{color}]{v*100:+.2f}%[/{color}]"

            def _dollar(v: float) -> str:
                color = "green" if v >= 0 else "red"
                return f"[{color}]${v:,.2f}[/{color}]"

            cfg = self.config
            table.add_row("Period",
                f"{cfg.start_date} → {cfg.end_date}")
            table.add_row("Symbols",          ", ".join(cfg.symbols[:5]) + ("…" if len(cfg.symbols) > 5 else ""))
            table.add_row("Initial Capital",  f"${cfg.initial_capital:,.2f}")
            table.add_row("Final Capital",
                _dollar(self.equity_curve.iloc[-1] if not self.equity_curve.empty else cfg.initial_capital))
            table.add_row("Total Return",     _pct(self.total_return()))
            table.add_row("Annualised Return",_pct(self.annualised_return()))
            table.add_row("Sharpe Ratio",     f"{self.sharpe_ratio():.2f}")
            table.add_row("Calmar Ratio",     f"{self.calmar_ratio():.2f}")
            table.add_row("Max Drawdown",     _pct(self.max_drawdown()))
            table.add_row("Total Trades",     str(self.total_trades()))
            table.add_row("Long / Short",     f"{self.long_trades()} / {self.short_trades()}")
            table.add_row("Win Rate",         f"{self.win_rate()*100:.1f}%")
            table.add_row("Profit Factor",    f"{self.profit_factor():.2f}")
            table.add_row("Avg Trade P&L",    _dollar(self.avg_trade_pnl()))
            table.add_row("Avg Win",          _dollar(self.avg_win()))
            table.add_row("Avg Loss",         _dollar(self.avg_loss()))
            table.add_row("Commission (total)",
                f"${sum(t.commission for t in self.trades):,.2f}")
            table.add_row("Slippage (total)",
                f"${sum(t.slippage_cost for t in self.trades):,.2f}")

            console.print(table)

        except ImportError:
            # Fallback plain-text
            print("\n" + "=" * 50)
            print("  BACKTEST RESULTS")
            print("=" * 50)
            print(f"  Period         : {self.config.start_date} → {self.config.end_date}")
            print(f"  Total Return   : {self.total_return()*100:+.2f}%")
            print(f"  Ann. Return    : {self.annualised_return()*100:+.2f}%")
            print(f"  Sharpe Ratio   : {self.sharpe_ratio():.2f}")
            print(f"  Max Drawdown   : {self.max_drawdown()*100:.2f}%")
            print(f"  Win Rate       : {self.win_rate()*100:.1f}%")
            print(f"  Profit Factor  : {self.profit_factor():.2f}")
            print(f"  Total Trades   : {self.total_trades()}")
            print("=" * 50 + "\n")

    def plot_equity_curve(self) -> None:
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
            fig.suptitle(
                f"Backtest: {', '.join(self.config.symbols[:3])}{'…' if len(self.config.symbols) > 3 else ''} "
                f"({self.config.start_date} → {self.config.end_date})",
                fontsize=14,
            )

            # Equity curve
            ax1 = axes[0]
            ax1.plot(self.equity_curve.index, self.equity_curve.values, color="steelblue", lw=1.5)
            ax1.set_ylabel("Portfolio Value ($)")
            ax1.set_title(
                f"Equity Curve  |  Total Return: {self.total_return()*100:+.2f}%  "
                f"|  Sharpe: {self.sharpe_ratio():.2f}",
                fontsize=10,
            )
            ax1.grid(True, alpha=0.3)
            ax1.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
            )

            # Drawdown
            ax2 = axes[1]
            roll_max  = self.equity_curve.cummax()
            drawdown  = (self.equity_curve - roll_max) / roll_max * 100
            ax2.fill_between(drawdown.index, drawdown.values, 0, color="red", alpha=0.4)
            ax2.set_ylabel("Drawdown (%)")
            ax2.set_title(f"Drawdown  |  Max: {self.max_drawdown()*100:.2f}%", fontsize=10)
            ax2.grid(True, alpha=0.3)

            # Daily returns histogram
            ax3 = axes[2]
            returns_pct = self.daily_returns * 100
            ax3.hist(returns_pct.dropna(), bins=60, color="steelblue", alpha=0.7, edgecolor="white")
            ax3.axvline(0, color="black", lw=1, ls="--")
            ax3.set_xlabel("Daily Return (%)")
            ax3.set_ylabel("Frequency")
            ax3.set_title(
                f"Daily Returns  |  Win Rate: {self.win_rate()*100:.1f}%  "
                f"|  Profit Factor: {self.profit_factor():.2f}",
                fontsize=10,
            )
            ax3.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()

        except ImportError:
            print("matplotlib not installed — skipping plot. Run: pip install matplotlib")

    def to_dataframe(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame()
        rows = []
        for t in self.trades:
            rows.append({
                "symbol":          t.symbol,
                "side":            t.side,
                "entry_date":      t.entry_date,
                "exit_date":       t.exit_date,
                "entry_price":     t.entry_price,
                "exit_price":      t.exit_price,
                "shares":          t.shares,
                "pnl":             t.pnl,
                "pnl_pct":         t.pnl_pct,
                "exit_reason":     t.exit_reason,
                "stop_price":      t.stop_price,
                "take_profit":     t.take_profit_price,
                "commission":      t.commission,
                "slippage_cost":   t.slippage_cost,
                "gross_pnl":       t.gross_pnl,
                "is_winner":       t.is_winner,
            })
        return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Backtester
# ─────────────────────────────────────────────────────────────────────────────

class Backtester:
    """
    Event-driven backtester.

    Workflow per trading day *t*:
        1. Check open positions for stop/TP triggers using bar *t* high/low
        2. Compute indicators on history up to bar *t* (no lookahead)
        3. Score each symbol → signal
        4. If signal clears threshold and portfolio has capacity → queue entry
        5. Execute queued entries at bar *t+1* open (next-bar fill)
    """

    def __init__(
        self,
        config: BacktestConfig,
        technical_analyzer=None,
        signal_generator=None,
    ):
        self.cfg = config
        self._tech = technical_analyzer or self._default_analyzer()
        self._signal_generator = signal_generator  # optional live SignalGenerator; not used in offline backtest

    # ── Public ───────────────────────────────────────────────────────────────

    def run(self) -> BacktestResults:
        logger.info(
            "Starting backtest: %d symbols, %s → %s, capital=$%s",
            len(self.cfg.symbols),
            self.cfg.start_date, self.cfg.end_date,
            f"{self.cfg.initial_capital:,.0f}",
        )

        # Download all data up-front
        data = self._download_data()
        if not data:
            logger.error("No data downloaded — aborting backtest")
            return BacktestResults([], pd.Series(dtype=float), pd.Series(dtype=float), self.cfg)

        # Build unified date index
        all_dates = sorted(
            set().union(*[set(df.index.date) for df in data.values()])  # type: ignore[arg-type]
        )
        all_dates = [d for d in all_dates if self.cfg.start_date <= d <= self.cfg.end_date]

        # State
        cash: float = self.cfg.initial_capital
        open_positions: dict[str, _OpenPosition] = {}
        closed_trades:  list[Trade] = []
        equity_series:  dict[date, float] = {}
        pending_entries: list[tuple[str, str, float]] = []  # (symbol, side, score)

        _try_progress = True
        progress_ctx = None
        task_id = None

        try:
            from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
            progress_ctx = Progress(
                TextColumn("[cyan]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total} days"),
                TimeRemainingColumn(),
            )
            progress_ctx.start()
            task_id = progress_ctx.add_task("Backtesting…", total=len(all_dates))
        except ImportError:
            _try_progress = False

        for bar_date in all_dates:
            # 1. Check stops / take-profits for existing positions
            for sym, pos in list(open_positions.items()):
                sym_data = data.get(sym)
                if sym_data is None:
                    continue
                bar = self._get_bar(sym_data, bar_date)
                if bar is None:
                    continue

                closed_trade = self._check_exit_triggers(pos, bar, bar_date)
                if closed_trade:
                    cash += closed_trade.exit_price * closed_trade.shares - closed_trade.commission
                    if pos.side == "short":
                        # For shorts: received cash at entry, buy back to close
                        proceeds = pos.entry_price * pos.shares
                        buyback  = closed_trade.exit_price * pos.shares
                        cash = cash - proceeds - buyback + (2 * proceeds) + closed_trade.pnl
                        # Simplified: just add pnl to cash
                        cash = self._cash_after_close(cash, pos, closed_trade)
                    closed_trades.append(closed_trade)
                    del open_positions[sym]

            # 2. Execute yesterday's pending entries at today's open
            if pending_entries:
                for sym, side, score in pending_entries:
                    if sym in open_positions:
                        continue
                    if len(open_positions) >= self.cfg.max_positions:
                        break
                    sym_data = data.get(sym)
                    if sym_data is None:
                        continue
                    bar = self._get_bar(sym_data, bar_date)
                    if bar is None or bar.get("open", 0) <= 0:
                        continue

                    # Apply slippage to open price
                    slip_mult = 1 + self.cfg.slippage_bps / 10_000
                    entry_px  = bar["open"] * (slip_mult if side == "long" else 2 - slip_mult)

                    # Portfolio value for sizing
                    port_value = self._portfolio_value(cash, open_positions, data, bar_date)
                    atr = self._get_atr(sym_data, bar_date)

                    shares, stop_px, tp_px = self._size_position(
                        entry_px, atr, port_value, side
                    )
                    if shares < 1:
                        continue

                    cost       = entry_px * shares
                    commission = self.cfg.commission_per_trade
                    slippage_c = entry_px * shares * self.cfg.slippage_bps / 10_000

                    # Cash check (long only; shorts receive cash)
                    if side == "long" and cash < cost + commission:
                        continue

                    # Portfolio heat check
                    open_risk = abs(entry_px - stop_px) * shares
                    current_heat = self._current_heat(open_positions, data, bar_date, port_value)
                    if current_heat + open_risk / max(port_value, 1) > self.cfg.max_portfolio_heat:
                        continue

                    if side == "long":
                        cash -= cost + commission
                    else:
                        cash += cost - commission   # short: receive proceeds

                    open_positions[sym] = _OpenPosition(
                        symbol=sym, side=side,
                        entry_date=bar_date, entry_price=entry_px,
                        shares=shares, stop_price=stop_px,
                        take_profit_price=tp_px,
                        commission=commission, slippage_cost=slippage_c,
                    )

                pending_entries.clear()

            # 3. Score all symbols and queue new entries for tomorrow
            for sym in self.cfg.symbols:
                if sym in open_positions:
                    continue
                sym_data = data.get(sym)
                if sym_data is None:
                    continue
                history = self._history_up_to(sym_data, bar_date)
                if history.empty or len(history) < 30:
                    continue
                score = self._score_symbol(history)
                if abs(score) >= self.cfg.signal_threshold:
                    side = "long" if score > 0 else "short"
                    pending_entries.append((sym, side, score))

            # 4. Mark-to-market equity
            port_value = self._portfolio_value(cash, open_positions, data, bar_date)
            equity_series[bar_date] = port_value

            if progress_ctx and task_id is not None:
                progress_ctx.advance(task_id)

        if progress_ctx:
            progress_ctx.stop()

        # Close all remaining positions at last available price
        last_date = all_dates[-1] if all_dates else self.cfg.end_date
        for sym, pos in list(open_positions.items()):
            sym_data = data.get(sym)
            close_px = self._last_price(sym_data, last_date) if sym_data is not None else pos.entry_price
            trade = self._close_position(pos, close_px, last_date, "end_of_backtest")
            closed_trades.append(trade)

        # Build result series
        equity_curve   = pd.Series(equity_series).sort_index()
        daily_returns  = equity_curve.pct_change().dropna()

        logger.info(
            "Backtest complete: %d trades, total return=%.2f%%, Sharpe=%.2f",
            len(closed_trades),
            (equity_curve.iloc[-1] / self.cfg.initial_capital - 1) * 100 if not equity_curve.empty else 0,
            BacktestResults(closed_trades, equity_curve, daily_returns, self.cfg).sharpe_ratio(),
        )

        return BacktestResults(
            trades=closed_trades,
            equity_curve=equity_curve,
            daily_returns=daily_returns,
            config=self.cfg,
        )

    # ── Data helpers ─────────────────────────────────────────────────────────

    def _download_data(self) -> dict[str, pd.DataFrame]:
        import yfinance as yf
        data: dict[str, pd.DataFrame] = {}
        start = self.cfg.start_date.strftime("%Y-%m-%d")
        # Add 60-day buffer for indicator warmup
        import datetime as dt
        buf_start = (self.cfg.start_date - dt.timedelta(days=90)).strftime("%Y-%m-%d")
        end   = self.cfg.end_date.strftime("%Y-%m-%d")

        logger.info("Downloading data for %d symbols via yfinance…", len(self.cfg.symbols))
        for sym in self.cfg.symbols:
            try:
                df = yf.download(sym, start=buf_start, end=end, progress=False, auto_adjust=True)
                if df.empty:
                    logger.warning("No data for %s", sym)
                    continue
                df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]
                df.index = pd.to_datetime(df.index).date
                data[sym] = df
                logger.debug("Downloaded %d bars for %s", len(df), sym)
            except Exception as exc:
                logger.warning("Download failed for %s: %s", sym, exc)
        return data

    def _get_bar(self, df: pd.DataFrame, bar_date: date) -> Optional[dict]:
        try:
            row = df.loc[bar_date]
            return row.to_dict() if hasattr(row, "to_dict") else dict(row)
        except KeyError:
            return None

    def _history_up_to(self, df: pd.DataFrame, bar_date: date) -> pd.DataFrame:
        return df[df.index <= bar_date]

    def _last_price(self, df: pd.DataFrame, bar_date: date) -> float:
        hist = self._history_up_to(df, bar_date)
        if hist.empty:
            return 0.0
        return float(hist["close"].iloc[-1])

    # ── Indicators & scoring ─────────────────────────────────────────────────

    def _apply_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply technical indicators using pandas-ta.

        Called on the full per-symbol DataFrame before the main loop so that
        all derived columns (RSI, MACD, BBands, ATR, SMAs) are available for
        slicing on each bar without re-computing every day.
        """
        try:
            import pandas_ta as ta  # noqa: F401
        except ImportError:
            raise ImportError(
                "pandas-ta is required for backtesting.  "
                "Install it with:  pip install pandas-ta"
            )
        df = df.copy()
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.sma(length=50,  append=True)
        df.ta.sma(length=200, append=True)
        return df

    def _compute_signal_score(self, df: pd.DataFrame) -> float:
        """Simple multi-factor score from -1 to +1.

        Factors (equal weight):
          1. RSI  – oversold (+) / overbought (-)
          2. MACD histogram direction  (+/-)
          3. Price vs SMA50 / SMA200  (trend)
          4. Bollinger Band position   (mean-reversion)
          5. 5-day rate-of-change momentum

        Delegates to :meth:`_score_symbol` which holds the full implementation.
        """
        return self._score_symbol(df)

    def _calculate_shares(
        self,
        price: float,
        atr: float,
        portfolio_value: float,
        side: str,
    ) -> tuple[int, float, float]:
        """Returns (shares, stop_price, take_profit_price).

        ATR-based fixed-fractional sizing that mirrors the live RiskManager:
        - Stop distance = max(ATR * atr_stop_multiplier, price * stop_loss_pct)
        - Dollar risk   = portfolio_value * risk_per_trade
        - Hard cap      = portfolio_value * max_position_size

        Delegates to :meth:`_size_position` which holds the full implementation.
        """
        return self._size_position(price, atr, portfolio_value, side)

    @staticmethod
    def _default_analyzer():
        """Return a minimal analyzer that applies pandas-ta."""
        class _MinimalTA:
            def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
                try:
                    import pandas_ta as ta
                    df = df.copy()
                    df.ta.rsi(length=14, append=True)
                    df.ta.macd(fast=12, slow=26, signal=9, append=True)
                    df.ta.bbands(length=20, std=2, append=True)
                    df.ta.atr(length=14, append=True)
                    df.ta.sma(length=50,  append=True)
                    df.ta.sma(length=200, append=True)
                    return df
                except Exception:
                    return df
        return _MinimalTA()

    def _score_symbol(self, history: pd.DataFrame) -> float:
        """
        Multi-factor score from -1 to +1.
        Uses: RSI, MACD, Bollinger position, SMA crossover, momentum.
        """
        try:
            df = self._tech.compute_indicators(history.copy())
            if df.empty:
                return 0.0

            scores: list[float] = []

            # ── RSI ──────────────────────────────────────────────────────
            rsi_col = next((c for c in df.columns if c.lower().startswith("rsi")), None)
            if rsi_col and not df[rsi_col].dropna().empty:
                rsi = float(df[rsi_col].dropna().iloc[-1])
                # RSI 30→bullish, 70→bearish; normalise to -1..+1
                scores.append(np.clip((50 - rsi) / 20 * -1, -1, 1))

            # ── MACD histogram ───────────────────────────────────────────
            macd_h = next((c for c in df.columns if "macdh" in c.lower() or "histogram" in c.lower()), None)
            if macd_h and not df[macd_h].dropna().empty:
                h = df[macd_h].dropna()
                val = float(h.iloc[-1])
                rng = float(h.abs().quantile(0.95)) or 1.0
                scores.append(np.clip(val / rng, -1, 1))

            # ── Bollinger Band position ───────────────────────────────────
            bbl = next((c for c in df.columns if "bbl" in c.lower()), None)
            bbu = next((c for c in df.columns if "bbu" in c.lower()), None)
            if bbl and bbu and "close" in df.columns:
                close = float(df["close"].dropna().iloc[-1])
                lo    = float(df[bbl].dropna().iloc[-1])
                hi    = float(df[bbu].dropna().iloc[-1])
                band  = hi - lo
                if band > 0:
                    # Position within band: 0=at lower, 1=at upper → shift to -1..+1
                    pos = (close - lo) / band
                    scores.append(np.clip((pos - 0.5) * -2, -1, 1))

            # ── SMA crossover (50 vs 200) ─────────────────────────────────
            sma50  = next((c for c in df.columns if "sma_50"  in c.lower() or c.lower() == "sma_50"), None)
            sma200 = next((c for c in df.columns if "sma_200" in c.lower() or c.lower() == "sma_200"), None)
            if sma50 and sma200:
                s50  = df[sma50].dropna()
                s200 = df[sma200].dropna()
                if not s50.empty and not s200.empty:
                    scores.append(1.0 if float(s50.iloc[-1]) > float(s200.iloc[-1]) else -1.0)

            # ── Momentum (5-day rate of change) ───────────────────────────
            if "close" in df.columns and len(df) >= 6:
                close = df["close"].dropna()
                roc5 = (float(close.iloc[-1]) / float(close.iloc[-6]) - 1)
                scores.append(np.clip(roc5 * 10, -1, 1))

            if not scores:
                return 0.0
            return float(np.clip(np.mean(scores), -1, 1))

        except Exception as exc:
            logger.debug("Scoring error: %s", exc)
            return 0.0

    def _get_atr(self, df: pd.DataFrame, bar_date: date) -> float:
        hist = self._history_up_to(df, bar_date)
        atr_col = next((c for c in hist.columns if c.lower().startswith("atr")), None)
        if atr_col:
            series = hist[atr_col].dropna()
            if not series.empty:
                return float(series.iloc[-1])
        # Manual ATR fallback
        if len(hist) >= 2 and "high" in hist.columns and "low" in hist.columns:
            high = hist["high"].values[-self.cfg.atr_period:]
            low  = hist["low"].values[-self.cfg.atr_period:]
            tr   = high - low
            return float(tr.mean()) if len(tr) > 0 else 0.0
        return 0.0

    # ── Position management ───────────────────────────────────────────────────

    def _size_position(
        self,
        entry_price: float,
        atr: float,
        portfolio_value: float,
        side: str,
    ) -> tuple[int, float, float]:
        """Returns (shares, stop_price, take_profit_price)."""
        stop_dist = max(
            atr * self.cfg.atr_stop_multiplier,
            entry_price * self.cfg.stop_loss_pct,
        )
        if side == "long":
            stop_px = entry_price - stop_dist
            tp_px   = entry_price + max(stop_dist * 2, entry_price * self.cfg.take_profit_pct)
        else:
            stop_px = entry_price + stop_dist
            tp_px   = entry_price - max(stop_dist * 2, entry_price * self.cfg.take_profit_pct)

        risk_dollars = portfolio_value * self.cfg.risk_per_trade
        risk_per_share = max(abs(entry_price - stop_px), 0.01)
        raw_shares = risk_dollars / risk_per_share

        max_dollars = portfolio_value * self.cfg.max_position_size
        shares = max(1, int(min(raw_shares, max_dollars / max(entry_price, 0.01))))

        return shares, round(stop_px, 2), round(tp_px, 2)

    def _check_exit_triggers(
        self,
        pos: _OpenPosition,
        bar: dict,
        bar_date: date,
    ) -> Optional[Trade]:
        """Check if stop-loss or take-profit was triggered on this bar."""
        high = bar.get("high", bar.get("close", pos.entry_price))
        low  = bar.get("low",  bar.get("close", pos.entry_price))
        close = bar.get("close", pos.entry_price)

        if pos.side == "long":
            if low <= pos.stop_price:
                return self._close_position(pos, pos.stop_price, bar_date, "stop_loss")
            if high >= pos.take_profit_price:
                return self._close_position(pos, pos.take_profit_price, bar_date, "take_profit")
        else:  # short
            if high >= pos.stop_price:
                return self._close_position(pos, pos.stop_price, bar_date, "stop_loss")
            if low <= pos.take_profit_price:
                return self._close_position(pos, pos.take_profit_price, bar_date, "take_profit")

        return None

    def _close_position(
        self,
        pos: _OpenPosition,
        exit_price: float,
        exit_date: date,
        reason: str,
    ) -> Trade:
        commission = self.cfg.commission_per_trade
        if pos.side == "long":
            gross_pnl = (exit_price - pos.entry_price) * pos.shares
        else:
            gross_pnl = (pos.entry_price - exit_price) * pos.shares
        net_pnl = gross_pnl - commission - pos.commission - pos.slippage_cost
        pnl_pct = net_pnl / (pos.entry_price * pos.shares) if pos.entry_price * pos.shares != 0 else 0.0

        return Trade(
            symbol=pos.symbol, side=pos.side,
            entry_date=pos.entry_date, exit_date=exit_date,
            entry_price=pos.entry_price, exit_price=exit_price,
            shares=pos.shares, pnl=net_pnl, pnl_pct=pnl_pct,
            exit_reason=reason,
            stop_price=pos.stop_price, take_profit_price=pos.take_profit_price,
            commission=pos.commission + commission,
            slippage_cost=pos.slippage_cost,
        )

    @staticmethod
    def _cash_after_close(cash: float, pos: _OpenPosition, trade: Trade) -> float:
        """Reconcile cash after closing (handles both long and short)."""
        if pos.side == "long":
            return cash + trade.exit_price * pos.shares - trade.commission
        else:
            # Covered short: pay back at exit_price
            return cash - trade.exit_price * pos.shares - trade.commission

    def _portfolio_value(
        self,
        cash: float,
        open_positions: dict[str, _OpenPosition],
        data: dict[str, pd.DataFrame],
        bar_date: date,
    ) -> float:
        value = cash
        for sym, pos in open_positions.items():
            price = self._last_price(data.get(sym, pd.DataFrame()), bar_date)
            if price <= 0:
                price = pos.entry_price
            if pos.side == "long":
                value += price * pos.shares
            else:
                value += (pos.entry_price - price) * pos.shares  # short P&L
        return value

    def _current_heat(
        self,
        open_positions: dict[str, _OpenPosition],
        data: dict[str, pd.DataFrame],
        bar_date: date,
        portfolio_value: float,
    ) -> float:
        """Total open risk as fraction of portfolio value."""
        total_risk = 0.0
        for sym, pos in open_positions.items():
            price = self._last_price(data.get(sym, pd.DataFrame()), bar_date)
            if price <= 0:
                price = pos.entry_price
            risk = abs(price - pos.stop_price) * pos.shares
            total_risk += risk
        return total_risk / max(portfolio_value, 1)
