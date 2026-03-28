"""
reporting/dashboard.py
----------------------
Rich terminal live dashboard displaying:
  - Account value, daily P&L, buying power, market status
  - Current positions table
  - Latest signals with confidence scores
  - Recent trades log
  - Footer with last update time and next scan countdown

Refreshes every 5 seconds using Rich Live.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class Dashboard:
    """
    Terminal dashboard using Rich Live display.

    Renders a comprehensive view of bot activity that refreshes automatically.

    Parameters
    ----------
    refresh_interval : float
        Seconds between automatic renders (default: 5.0).
    """

    def __init__(self, refresh_interval: float = 5.0):
        self._refresh_interval = refresh_interval
        self._live = None
        self._running = False
        self._next_scan_in: int = 60  # seconds until next scan

        try:
            from rich.live import Live  # type: ignore
            from rich.layout import Layout  # type: ignore
            self._rich_available = True
        except ImportError:
            logger.warning("Rich not installed; dashboard will use plain text output.")
            self._rich_available = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def render(
        self,
        portfolio_manager,
        signals: dict,
        recent_trades: list[dict],
        market_status: dict,
        next_scan_in: int = 60,
    ):
        """
        Build and return a Rich Layout object (or print plain text fallback).

        Parameters
        ----------
        portfolio_manager : PortfolioManager
            Current portfolio state.
        signals : dict
            Mapping of ``symbol -> Signal`` from the latest scan.
        recent_trades : list[dict]
            Most recent trade records from the database.
        market_status : dict
            Keys: ``is_open``, ``vix``, ``market_regime``, ``timestamp``.
        next_scan_in : int
            Seconds until the next trading cycle.

        Returns
        -------
        Rich Layout object (or None if Rich not available).
        """
        self._next_scan_in = next_scan_in

        if not self._rich_available:
            self._render_plain(portfolio_manager, signals, recent_trades, market_status)
            return None

        try:
            return self._build_layout(portfolio_manager, signals, recent_trades, market_status)
        except Exception as exc:
            logger.error("Dashboard render error: %s", exc)
            return None

    def start_live(
        self,
        portfolio_manager,
        signals: dict,
        recent_trades: list[dict],
        market_status: dict,
    ) -> None:
        """
        Start a Rich Live display session.

        Call :meth:`stop_live` to stop.
        """
        if not self._rich_available:
            return

        try:
            from rich.live import Live  # type: ignore

            layout = self._build_layout(portfolio_manager, signals, recent_trades, market_status)
            self._live = Live(
                layout,
                refresh_per_second=1 / self._refresh_interval,
                screen=False,
            )
            self._live.start()
            self._running = True
            logger.info("Dashboard Live display started.")
        except Exception as exc:
            logger.error("start_live error: %s", exc)

    def update_live(
        self,
        portfolio_manager,
        signals: dict,
        recent_trades: list[dict],
        market_status: dict,
        next_scan_in: int = 60,
    ) -> None:
        """Update the Live display with fresh data."""
        if not self._running or self._live is None:
            return
        try:
            layout = self._build_layout(
                portfolio_manager, signals, recent_trades, market_status, next_scan_in
            )
            self._live.update(layout)
        except Exception as exc:
            logger.debug("update_live error: %s", exc)

    def stop_live(self) -> None:
        """Stop the Rich Live display."""
        if self._live and self._running:
            try:
                self._live.stop()
            except Exception:
                pass
            self._running = False

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def _build_layout(
        self,
        portfolio_manager,
        signals: dict,
        recent_trades: list[dict],
        market_status: dict,
        next_scan_in: int = 60,
    ):
        """Build and return a Rich Layout."""
        from rich.layout import Layout  # type: ignore
        from rich.panel import Panel  # type: ignore
        from rich.table import Table  # type: ignore
        from rich.text import Text  # type: ignore
        from rich.columns import Columns  # type: ignore
        from rich import box  # type: ignore

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=7),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3),
        )
        layout["main"].split_row(
            Layout(name="positions", ratio=3),
            Layout(name="signals", ratio=2),
        )
        layout["main"].split_column(
            Layout(name="middle"),
            Layout(name="trades", size=12),
        )

        # ---- Header panel ----
        layout["header"].update(
            Panel(
                self._build_header_text(portfolio_manager, market_status),
                title="[bold cyan]Trading Bot Dashboard[/bold cyan]",
                border_style="cyan",
            )
        )

        # ---- Positions table ----
        layout["positions"].update(
            Panel(
                self._build_positions_table(portfolio_manager),
                title="[bold green]Open Positions[/bold green]",
                border_style="green",
            )
        )

        # ---- Signals panel ----
        layout["signals"].update(
            Panel(
                self._build_signals_table(signals),
                title="[bold yellow]Latest Signals[/bold yellow]",
                border_style="yellow",
            )
        )

        # ---- Recent trades ----
        layout["trades"].update(
            Panel(
                self._build_trades_table(recent_trades),
                title="[bold magenta]Recent Trades[/bold magenta]",
                border_style="magenta",
            )
        )

        # ---- Footer ----
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        footer_text = Text(
            f"Last update: {now}  |  Next scan in: {next_scan_in}s  |  "
            f"Press Ctrl+C to exit",
            justify="center",
            style="dim",
        )
        layout["footer"].update(Panel(footer_text, border_style="dim"))

        return layout

    def _build_header_text(self, portfolio_manager, market_status: dict):
        """Build the header panel content."""
        from rich.table import Table  # type: ignore
        from rich import box  # type: ignore

        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Label", style="bold")
        table.add_column("Value")

        try:
            summary = portfolio_manager.get_performance_summary()
            pv = summary.get("portfolio_value", 0)
            daily_pnl = summary.get("daily_pnl", 0)
            total_pnl = summary.get("total_pnl", 0)
            bp = summary.get("buying_power", 0)
            total_ret = summary.get("total_return_pct", 0)

            # Color-code P&L
            daily_color = "green" if daily_pnl >= 0 else "red"
            total_color = "green" if total_pnl >= 0 else "red"
            daily_sign = "+" if daily_pnl >= 0 else ""
            total_sign = "+" if total_pnl >= 0 else ""

            is_open = market_status.get("is_open", False)
            regime = market_status.get("market_regime", "unknown")
            vix = market_status.get("vix", 0.0)
            mode = market_status.get("mode", "paper")

            market_color = "green" if is_open else "red"
            market_label = "OPEN" if is_open else "CLOSED"
            regime_color = {"bull": "green", "bear": "red", "neutral": "yellow"}.get(regime, "white")

            table.add_row(
                "Portfolio Value",
                f"[bold white]${pv:,.2f}[/bold white]",
            )
            table.add_row(
                "Daily P&L",
                f"[{daily_color}]{daily_sign}${daily_pnl:,.2f} ({daily_sign}{total_ret:.2f}%)[/{daily_color}]",
            )
            table.add_row(
                "Total P&L",
                f"[{total_color}]{total_sign}${total_pnl:,.2f}[/{total_color}]",
            )
            table.add_row(
                "Buying Power",
                f"${bp:,.2f}",
            )
            table.add_row(
                "Market",
                f"[{market_color}]{market_label}[/{market_color}]  "
                f"Regime: [{regime_color}]{regime.upper()}[/{regime_color}]  "
                f"VIX: {vix:.1f}  Mode: [bold]{mode.upper()}[/bold]",
            )
        except Exception as exc:
            table.add_row("Error", f"[red]{exc}[/red]")

        return table

    def _build_positions_table(self, portfolio_manager):
        """Build the positions table."""
        from rich.table import Table  # type: ignore
        from rich import box  # type: ignore

        table = Table(
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold white",
            padding=(0, 1),
        )
        table.add_column("Symbol", style="bold cyan", width=8)
        table.add_column("Side", width=6)
        table.add_column("Qty", justify="right", width=8)
        table.add_column("Entry", justify="right", width=10)
        table.add_column("Current", justify="right", width=10)
        table.add_column("P&L $", justify="right", width=10)
        table.add_column("P&L %", justify="right", width=8)

        try:
            positions = portfolio_manager.get_all_positions()
            if not positions:
                table.add_row("[dim]No open positions[/dim]", "", "", "", "", "", "")
                return table

            # Sort by absolute P&L descending
            sorted_pos = sorted(
                positions.values(),
                key=lambda p: abs(float(p.get("unrealized_pl", 0))),
                reverse=True,
            )

            for pos in sorted_pos:
                pnl = float(pos.get("unrealized_pl", 0))
                pnl_pct = float(pos.get("unrealized_plpc", 0)) * 100
                side = pos.get("side", "long")
                side_color = "green" if side == "long" else "red"
                pnl_color = "green" if pnl >= 0 else "red"
                pnl_sign = "+" if pnl >= 0 else ""

                table.add_row(
                    pos.get("symbol", ""),
                    f"[{side_color}]{side.upper()}[/{side_color}]",
                    f"{abs(float(pos.get('qty', 0))):.0f}",
                    f"${float(pos.get('avg_entry_price', 0)):.2f}",
                    f"${float(pos.get('current_price', 0)):.2f}",
                    f"[{pnl_color}]{pnl_sign}${pnl:,.2f}[/{pnl_color}]",
                    f"[{pnl_color}]{pnl_sign}{pnl_pct:.2f}%[/{pnl_color}]",
                )
        except Exception as exc:
            table.add_row(f"[red]Error: {exc}[/red]", "", "", "", "", "", "")

        return table

    def _build_signals_table(self, signals: dict):
        """Build the signals panel."""
        from rich.table import Table  # type: ignore
        from rich import box  # type: ignore

        table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style="bold white",
            padding=(0, 1),
        )
        table.add_column("Symbol", style="bold cyan", width=8)
        table.add_column("Action", width=7)
        table.add_column("Score", justify="right", width=7)
        table.add_column("Conf", justify="right", width=6)

        if not signals:
            table.add_row("[dim]No signals yet[/dim]", "", "", "")
            return table

        # Sort by absolute combined_score descending
        sorted_signals = sorted(
            signals.values(),
            key=lambda s: abs(getattr(s, "combined_score", 0)),
            reverse=True,
        )[:15]  # Show top 15

        for sig in sorted_signals:
            action = (
                sig.action.value
                if hasattr(sig.action, "value")
                else str(sig.action)
            )
            score = getattr(sig, "combined_score", 0.0)
            conf = getattr(sig, "confidence", 0.0)

            action_color = {
                "BUY": "green",
                "SELL": "red",
                "SHORT": "magenta",
                "COVER": "cyan",
                "HOLD": "dim",
            }.get(action, "white")

            score_color = "green" if score > 0 else ("red" if score < 0 else "white")
            sign = "+" if score > 0 else ""

            table.add_row(
                getattr(sig, "symbol", ""),
                f"[{action_color}]{action}[/{action_color}]",
                f"[{score_color}]{sign}{score:.2f}[/{score_color}]",
                f"{conf:.2f}",
            )

        return table

    def _build_trades_table(self, recent_trades: list[dict]):
        """Build the recent trades table."""
        from rich.table import Table  # type: ignore
        from rich import box  # type: ignore

        table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style="bold white",
            padding=(0, 1),
        )
        table.add_column("Time", width=10)
        table.add_column("Symbol", style="bold cyan", width=8)
        table.add_column("Action", width=7)
        table.add_column("Qty", justify="right", width=6)
        table.add_column("Price", justify="right", width=10)
        table.add_column("Status", width=10)

        if not recent_trades:
            table.add_row("[dim]No trades yet[/dim]", "", "", "", "", "")
            return table

        for trade in recent_trades[:10]:
            ts = str(trade.get("timestamp", ""))[:10]
            action = str(trade.get("action", ""))
            action_color = {
                "BUY": "green", "SELL": "red",
                "SHORT": "magenta", "COVER": "cyan",
            }.get(action.upper(), "white")
            price = float(trade.get("filled_avg_price", 0) or 0)
            status = str(trade.get("status", ""))
            status_color = "green" if status in ("filled", "partially_filled") else "yellow"

            table.add_row(
                ts,
                str(trade.get("symbol", "")),
                f"[{action_color}]{action}[/{action_color}]",
                f"{float(trade.get('qty', 0) or 0):.0f}",
                f"${price:.2f}" if price else "—",
                f"[{status_color}]{status}[/{status_color}]",
            )

        return table

    # ------------------------------------------------------------------
    # Plain-text fallback
    # ------------------------------------------------------------------

    def _render_plain(
        self,
        portfolio_manager,
        signals: dict,
        recent_trades: list[dict],
        market_status: dict,
    ) -> None:
        """Simple plain-text dashboard for environments without Rich."""
        try:
            summary = portfolio_manager.get_performance_summary()
            pv = summary.get("portfolio_value", 0)
            daily = summary.get("daily_pnl", 0)
            sign = "+" if daily >= 0 else ""
            is_open = market_status.get("is_open", False)
            now = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")

            print(f"\n{'='*60}")
            print(f"  Trading Bot  |  {now} UTC  |  Market: {'OPEN' if is_open else 'CLOSED'}")
            print(f"  Portfolio: ${pv:,.2f}  |  Daily P&L: {sign}${daily:,.2f}")
            print(f"{'='*60}")

            positions = portfolio_manager.get_all_positions()
            if positions:
                print("\nPositions:")
                for sym, pos in positions.items():
                    pnl = float(pos.get("unrealized_pl", 0))
                    print(f"  {sym:6s}  {pos.get('side','long'):5s}  "
                          f"{float(pos.get('qty',0)):.0f} shares  "
                          f"P&L: ${pnl:+,.2f}")

            top_signals = sorted(
                signals.values(),
                key=lambda s: abs(getattr(s, "combined_score", 0)),
                reverse=True,
            )[:5]
            if top_signals:
                print("\nTop Signals:")
                for sig in top_signals:
                    action = sig.action.value if hasattr(sig.action, "value") else str(sig.action)
                    score = getattr(sig, "combined_score", 0)
                    print(f"  {getattr(sig,'symbol',''):6s}  {action:5s}  score={score:+.2f}")

            print()
        except Exception as exc:
            logger.error("_render_plain error: %s", exc)

    def print_startup_banner(self, mode: str = "paper") -> None:
        """Print a startup banner to the terminal."""
        if self._rich_available:
            try:
                from rich.console import Console  # type: ignore
                from rich.panel import Panel  # type: ignore
                from rich.text import Text  # type: ignore

                console = Console()
                text = Text.assemble(
                    ("Automated Trading Bot\n", "bold cyan"),
                    (f"Mode: {mode.upper()}\n", "bold yellow" if mode == "paper" else "bold red"),
                    ("Powered by Alpaca + FinBERT + pandas-ta", "dim"),
                )
                console.print(Panel(text, border_style="cyan"))
            except Exception:
                pass
        else:
            print(f"\n=== Automated Trading Bot (mode={mode.upper()}) ===\n")
