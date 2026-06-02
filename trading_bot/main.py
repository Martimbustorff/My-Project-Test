#!/usr/bin/env python3
"""
main.py
-------
Entry point for the automated trading bot.

Usage
-----
    python main.py              # paper trading (default, safe)
    python main.py --live       # live trading  (real money!)
    python main.py --once       # single scan cycle then exit (testing)
    python main.py --no-dash    # suppress Rich dashboard (plain logs)

Scheduler jobs
--------------
    Every  1 min  : trading_cycle()        – scan + execute
    Every  5 min  : portfolio_refresh()    – sync broker state + dashboard
    Every 60 min  : news_refresh()         – refresh news/sentiment cache
    Daily  9:25 ET: pre_market_setup()     – fundamentals + shortability
    Daily 16:05 ET: end_of_day_report()    – snapshot + summary
    Mon    8:00 ET: weekly_watchlist()      – growing-stock watchlist (≤3-month)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime

import pytz

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state (module-level so scheduler callbacks can access it)
# ---------------------------------------------------------------------------
_components: dict = {}
_recent_signals: dict = {}        # symbol -> Signal
_recent_trades: list = []         # list[ExecutionResult]
_circuit_broken: bool = False
_next_scan_in: int = 60           # seconds until next scan (for dashboard)
_use_dashboard: bool = True


# ---------------------------------------------------------------------------
# Component wiring
# ---------------------------------------------------------------------------

def build_components(paper: bool) -> dict:
    """Instantiate and wire every bot component."""
    from config.settings import Settings
    cfg = Settings()

    if not cfg.ALPACA_API_KEY or not cfg.ALPACA_SECRET_KEY:
        logger.critical(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env\n"
            "  Copy .env.example → .env and fill in your credentials.\n"
            "  Free paper-trading keys: https://alpaca.markets"
        )
        sys.exit(1)

    # ── Alpaca clients ────────────────────────────────────────────────────
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient

    trading_client = TradingClient(
        api_key=cfg.ALPACA_API_KEY,
        secret_key=cfg.ALPACA_SECRET_KEY,
        paper=paper,
    )
    data_client = StockHistoricalDataClient(
        api_key=cfg.ALPACA_API_KEY,
        secret_key=cfg.ALPACA_SECRET_KEY,
    )

    # ── Broker (execution layer) ──────────────────────────────────────────
    from execution.broker import AlpacaBroker
    broker = AlpacaBroker(
        api_key=cfg.ALPACA_API_KEY,
        secret_key=cfg.ALPACA_SECRET_KEY,
        paper=paper,
    )

    # ── Data fetchers ─────────────────────────────────────────────────────
    from data.market_data import MarketDataFetcher
    from data.news_fetcher import NewsFetcher
    mdf  = MarketDataFetcher(alpaca_client=data_client)
    news = NewsFetcher(api_key=cfg.NEWS_API_KEY)

    # ── Analysis ──────────────────────────────────────────────────────────
    from analysis.technical import TechnicalAnalyzer
    from analysis.sentiment import SentimentAnalyzer
    from analysis.signals   import SignalGenerator
    tech      = TechnicalAnalyzer()
    sentiment = SentimentAnalyzer()
    sig_gen   = SignalGenerator(settings=cfg)

    # ── Risk ──────────────────────────────────────────────────────────────
    from risk.risk_manager import RiskManager
    risk = RiskManager(settings=cfg)

    # ── Portfolio + logging ───────────────────────────────────────────────
    from portfolio.portfolio_manager import PortfolioManager
    from reporting.logger            import TradeLogger
    portfolio = PortfolioManager()
    tlog      = TradeLogger(db_path=cfg.DB_PATH)

    # ── Execution ─────────────────────────────────────────────────────────
    from execution.order_manager import OrderManager
    order_mgr = OrderManager(broker=broker, risk_manager=risk, trade_logger=tlog)

    # ── Strategy ──────────────────────────────────────────────────────────
    from strategy.combined_strategy import TradingStrategy
    strategy = TradingStrategy(
        market_data=mdf,
        news_fetcher=news,
        technical_analyzer=tech,
        sentiment_analyzer=sentiment,
        signal_generator=sig_gen,
        risk_manager=risk,
    )

    # ── Dashboard ─────────────────────────────────────────────────────────
    from reporting.dashboard import Dashboard
    dashboard = Dashboard()

    return dict(
        cfg=cfg,
        broker=broker,
        mdf=mdf,
        news=news,
        tech=tech,
        sentiment=sentiment,
        sig_gen=sig_gen,
        risk=risk,
        portfolio=portfolio,
        tlog=tlog,
        order_mgr=order_mgr,
        strategy=strategy,
        dashboard=dashboard,
    )


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------

def trading_cycle() -> None:
    """1-minute job: scan universe → filter → execute → manage positions."""
    global _recent_signals, _recent_trades, _circuit_broken, _next_scan_in

    c   = _components
    cfg = c["cfg"]

    # Market must be open
    if not c["mdf"].is_market_open():
        logger.debug("Market closed – skipping trading cycle")
        return

    # Circuit-breaker check
    daily_pnl = c["portfolio"].get_daily_pnl()
    pv        = c["portfolio"].get_portfolio_value()
    if c["risk"].check_daily_drawdown(daily_pnl, pv):
        if not _circuit_broken:
            logger.critical("CIRCUIT BREAKER ACTIVE – no new trades for the rest of today")
        _circuit_broken = True
        return
    _circuit_broken = False

    # Market context (VIX + regime)
    market_context = c["strategy"].get_market_context()

    # Full universe scan → {symbol: Signal}
    signals = c["strategy"].scan_universe(
        symbols=cfg.TRADING_UNIVERSE,
        portfolio_manager=c["portfolio"],
        market_context=market_context,
    )
    _recent_signals = signals

    # Persist all signals to DB
    for sig in signals.values():
        try:
            c["tlog"].log_signal(sig)
        except Exception:
            pass

    # Filter to actionable signals
    actionable = c["strategy"].filter_actionable_signals(
        signals, c["portfolio"], max_signals=5
    )

    # ATR map for position sizing
    atr_map = c["strategy"].get_atr_map()

    # Execute new entries/exits
    for sig in actionable:
        try:
            result = c["order_mgr"].execute_signal(sig, c["portfolio"], atr_map)
            if result and result.success:
                _recent_trades.append(result)
                _recent_trades = _recent_trades[-50:]
        except Exception as exc:
            logger.error("execute_signal error for %s: %s", sig.symbol, exc)

    # Manage existing open positions (trailing stops, hard stops, opposing signals)
    try:
        exits = c["order_mgr"].manage_existing_positions(
            signals, c["portfolio"], atr_map
        )
        _recent_trades.extend(exits)
        _recent_trades = _recent_trades[-50:]
    except Exception as exc:
        logger.error("manage_existing_positions error: %s", exc)

    _next_scan_in = cfg.SIGNAL_SCAN_INTERVAL_MINUTES * 60


def portfolio_refresh() -> None:
    """5-minute job: sync portfolio state from broker and update dashboard."""
    c = _components
    c["portfolio"].refresh(c["broker"])
    try:
        c["tlog"].log_portfolio_snapshot(c["portfolio"])
    except Exception:
        pass
    _update_dashboard()


def news_refresh() -> None:
    """Hourly job: refresh news + sentiment cache."""
    c = _components
    logger.info("Refreshing news/sentiment cache …")
    c["strategy"].refresh_news_cache(c["cfg"].TRADING_UNIVERSE)
    logger.info("News/sentiment cache refreshed.")


def pre_market_setup() -> None:
    """9:25 AM ET daily: refresh fundamentals and shortability cache."""
    c = _components
    logger.info("Pre-market setup: refreshing fundamentals …")
    c["strategy"].refresh_fundamentals_cache(c["cfg"].TRADING_UNIVERSE)
    logger.info("Pre-market setup complete.")


def end_of_day_report() -> None:
    """4:05 PM ET daily: log snapshot + print summary."""
    c = _components
    try:
        c["tlog"].log_portfolio_snapshot(c["portfolio"])
    except Exception:
        pass
    summary = c["portfolio"].get_performance_summary()
    logger.info(
        "END OF DAY | Value=$%s | Day P&L=%.2f%% | "
        "Longs=%d Shorts=%d | Unrealised P&L=$%s",
        f"{summary['portfolio_value']:,.2f}",
        summary["daily_pnl_pct"] * 100,
        summary["long_positions"],
        summary["short_positions"],
        f"{summary['total_unrealized_pnl']:,.2f}",
    )
    # Performance stats
    try:
        stats = c["tlog"].get_performance_stats()
        logger.info("Trade stats: %s", stats)
    except Exception:
        pass


def weekly_watchlist() -> None:
    """Weekly job (Mon 08:00 ET): generate the dynamic growing-stock watchlist."""
    cfg = _components["cfg"]
    logger.info("Generating weekly stock watchlist …")
    try:
        from watchlist.watchlist import WatchlistBuilder, save_watchlist
        from watchlist.scoring import GrowthGate
        from watchlist.report import to_markdown

        gate = GrowthGate(
            min_revenue_growth=cfg.WATCHLIST_MIN_REVENUE_GROWTH,
            require_positive_momentum=cfg.WATCHLIST_REQUIRE_MOMENTUM,
        )
        builder = WatchlistBuilder(
            regions=cfg.WATCHLIST_REGIONS,
            horizon_days=cfg.WATCHLIST_HORIZON_DAYS,
            top_n=cfg.WATCHLIST_TOP_N,
            weights=cfg.WATCHLIST_WEIGHTS,
            gate=gate,
        )
        wl = builder.build()
        json_path = save_watchlist(wl, cfg.WATCHLIST_OUTPUT_DIR)
        from pathlib import Path
        md_path = Path(cfg.WATCHLIST_OUTPUT_DIR) / f"watchlist_{wl.week_of}.md"
        md_path.write_text(to_markdown(wl), encoding="utf-8")
        logger.info(
            "Weekly watchlist ready: %d/%d qualified → %s",
            wl.qualified_count, wl.universe_size, json_path,
        )
    except Exception as exc:
        logger.error("weekly_watchlist error: %s", exc)


def _update_dashboard() -> None:
    if not _use_dashboard:
        return
    c = _components
    try:
        c["dashboard"].update(
            portfolio_manager=c["portfolio"],
            signals=_recent_signals,
            recent_trades=_recent_trades,
            market_open=c["mdf"].is_market_open(),
            next_scan_seconds=_next_scan_in,
        )
    except Exception as exc:
        logger.debug("Dashboard update error: %s", exc)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def _build_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron         import CronTrigger
    from apscheduler.triggers.interval     import IntervalTrigger

    et  = pytz.timezone("America/New_York")
    sch = BackgroundScheduler(timezone=et)

    cfg = _components["cfg"]

    sch.add_job(
        trading_cycle,
        IntervalTrigger(minutes=cfg.SIGNAL_SCAN_INTERVAL_MINUTES),
        id="trading_cycle",
        max_instances=1,
        coalesce=True,
    )
    sch.add_job(
        portfolio_refresh,
        IntervalTrigger(minutes=cfg.PORTFOLIO_REFRESH_INTERVAL_MINUTES),
        id="portfolio_refresh",
        max_instances=1,
        coalesce=True,
    )
    sch.add_job(
        news_refresh,
        IntervalTrigger(minutes=cfg.NEWS_REFRESH_INTERVAL_MINUTES),
        id="news_refresh",
        max_instances=1,
        coalesce=True,
    )
    sch.add_job(
        pre_market_setup,
        CronTrigger(hour=9, minute=25, timezone=et),
        id="pre_market_setup",
    )
    sch.add_job(
        end_of_day_report,
        CronTrigger(hour=16, minute=5, timezone=et),
        id="end_of_day_report",
    )
    sch.add_job(
        weekly_watchlist,
        CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=et),
        id="weekly_watchlist",
    )
    return sch


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global _components, _use_dashboard

    parser = argparse.ArgumentParser(
        description="Automated Stock Trading Bot powered by Alpaca"
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--paper", action="store_true", default=True,
        help="Paper trading mode (default – no real money)",
    )
    mode_group.add_argument(
        "--live", action="store_true", default=False,
        help="Live trading mode (REAL MONEY – use with caution)",
    )
    parser.add_argument(
        "--once", action="store_true", default=False,
        help="Run a single scan cycle then exit (useful for testing)",
    )
    parser.add_argument(
        "--no-dash", action="store_true", default=False,
        help="Disable the Rich live dashboard (plain log output)",
    )
    args = parser.parse_args()

    paper         = not args.live
    _use_dashboard = not args.no_dash

    # ── Logging ───────────────────────────────────────────────────────────
    from reporting.logger import setup_logging
    setup_logging(log_level="INFO")

    mode_label = "PAPER" if paper else "LIVE"
    logger.info("=" * 50)
    logger.info("  AUTOMATED TRADING BOT  [%s MODE]", mode_label)
    logger.info("=" * 50)

    if not paper:
        logger.warning("*** LIVE TRADING MODE — real money at risk! ***")
        logger.warning("Starting in 5 seconds … press Ctrl+C to abort.")
        time.sleep(5)

    # ── Build all components ──────────────────────────────────────────────
    logger.info("Initialising components …")
    _components = build_components(paper=paper)
    cfg = _components["cfg"]

    # ── Initial data refresh ──────────────────────────────────────────────
    logger.info("Syncing portfolio …")
    _components["portfolio"].refresh(_components["broker"])

    logger.info("Fetching initial news/sentiment …")
    _components["strategy"].refresh_news_cache(cfg.TRADING_UNIVERSE)

    logger.info("Fetching fundamentals …")
    _components["strategy"].refresh_fundamentals_cache(cfg.TRADING_UNIVERSE)

    # ── Single-shot mode ──────────────────────────────────────────────────
    if args.once:
        logger.info("--once flag set: running single trading cycle …")
        trading_cycle()
        summary = _components["portfolio"].get_performance_summary()
        logger.info("Portfolio: %s", summary)
        logger.info("Done. Exiting.")
        return

    # ── Scheduler ─────────────────────────────────────────────────────────
    scheduler = _build_scheduler()
    scheduler.start()
    logger.info(
        "Scheduler started with %d jobs. Bot is live. Press Ctrl+C to stop.",
        len(scheduler.get_jobs()),
    )

    # ── Dashboard live loop ───────────────────────────────────────────────
    dash = _components["dashboard"]
    try:
        if _use_dashboard:
            with dash.live_context():
                while True:
                    _update_dashboard()
                    time.sleep(5)
        else:
            while True:
                time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Bot stopped.")


if __name__ == "__main__":
    import os
    # Ensure the trading_bot directory is on sys.path when run directly
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
