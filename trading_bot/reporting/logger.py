"""
reporting/logger.py
-------------------
SQLite-backed trade and signal logger.  Also configures Python's
standard logging to write to both console and a rotating file.
"""
import logging
import logging.handlers
import sqlite3
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("TRADE_DB_PATH", "trading_bot.db")


def setup_logging(log_level: str = "INFO", log_file: str = "trading_bot.log") -> None:
    """Configure root logger with console + rotating file handlers."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(level)
    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)
    # Rotating file
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)


class TradeLogger:
    """
    Persists trade and signal history in a local SQLite database.

    Tables:
        trades              – executed orders
        signals             – generated signals (all, including HOLD)
        portfolio_snapshots – periodic portfolio state snapshots
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TEXT NOT NULL,
                    symbol          TEXT NOT NULL,
                    action          TEXT NOT NULL,
                    shares          INTEGER,
                    entry_price     REAL,
                    stop_price      REAL,
                    take_profit     REAL,
                    order_id        TEXT,
                    signal_score    REAL,
                    confidence      REAL,
                    reasoning       TEXT,
                    portfolio_value REAL
                );

                CREATE TABLE IF NOT EXISTS signals (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp        TEXT NOT NULL,
                    symbol           TEXT NOT NULL,
                    action           TEXT NOT NULL,
                    confidence       REAL,
                    combined_score   REAL,
                    technical_score  REAL,
                    sentiment_score  REAL,
                    momentum_score   REAL,
                    fundamental_score REAL,
                    current_price    REAL,
                    reasoning        TEXT
                );

                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TEXT NOT NULL,
                    portfolio_value REAL,
                    equity          REAL,
                    cash            REAL,
                    daily_pnl       REAL,
                    daily_pnl_pct   REAL,
                    unrealized_pnl  REAL,
                    long_positions  INTEGER,
                    short_positions INTEGER,
                    net_exposure    REAL,
                    gross_exposure  REAL
                );
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def log_signal(self, signal) -> None:
        """Log a Signal dataclass to the signals table."""
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO signals
                    (timestamp, symbol, action, confidence, combined_score,
                     technical_score, sentiment_score, momentum_score,
                     fundamental_score, current_price, reasoning)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        datetime.utcnow().isoformat(),
                        signal.symbol,
                        str(signal.action),
                        signal.confidence,
                        signal.combined_score,
                        signal.technical_score,
                        signal.sentiment_score,
                        signal.momentum_score,
                        signal.fundamental_score,
                        signal.current_price,
                        json.dumps(signal.reasoning),
                    ),
                )
        except Exception as e:
            logger.warning(f"Failed to log signal: {e}")

    def log_trade(self, order: dict, signal, portfolio_value: float) -> None:
        """Log an executed order + its originating signal."""
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO trades
                    (timestamp, symbol, action, shares, entry_price, order_id,
                     signal_score, confidence, reasoning, portfolio_value)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        datetime.utcnow().isoformat(),
                        order.get("symbol", ""),
                        order.get("side", ""),
                        int(order.get("qty", 0)),
                        float(order.get("filled_avg_price") or 0),
                        order.get("id", ""),
                        getattr(signal, "combined_score", None),
                        getattr(signal, "confidence", None),
                        json.dumps(getattr(signal, "reasoning", [])),
                        portfolio_value,
                    ),
                )
        except Exception as e:
            logger.warning(f"Failed to log trade: {e}")

    def log_portfolio_snapshot(self, portfolio_manager) -> None:
        """Persist a portfolio snapshot for performance tracking."""
        try:
            summary = portfolio_manager.get_performance_summary()
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO portfolio_snapshots
                    (timestamp, portfolio_value, equity, cash, daily_pnl,
                     daily_pnl_pct, unrealized_pnl, long_positions,
                     short_positions, net_exposure, gross_exposure)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        datetime.utcnow().isoformat(),
                        summary["portfolio_value"],
                        summary["equity"],
                        summary["cash"],
                        summary["daily_pnl"],
                        summary["daily_pnl_pct"],
                        summary["total_unrealized_pnl"],
                        summary["long_positions"],
                        summary["short_positions"],
                        summary["net_exposure_pct"],
                        summary["gross_exposure_pct"],
                    ),
                )
        except Exception as e:
            logger.warning(f"Failed to log snapshot: {e}")

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_trade_history(self, days: int = 30) -> pd.DataFrame:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._conn() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM trades WHERE timestamp >= ? ORDER BY timestamp DESC",
                conn, params=(since,)
            )
        return df

    def get_signal_history(self, days: int = 1) -> pd.DataFrame:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._conn() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM signals WHERE timestamp >= ? ORDER BY timestamp DESC",
                conn, params=(since,)
            )
        return df

    def get_portfolio_history(self, days: int = 30) -> pd.DataFrame:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._conn() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM portfolio_snapshots WHERE timestamp >= ? ORDER BY timestamp",
                conn, params=(since,)
            )
        return df

    def get_performance_stats(self) -> dict:
        """Compute win rate, avg return, total trades from DB."""
        try:
            df = self.get_trade_history(days=365)
            if df.empty:
                return {"total_trades": 0, "win_rate": 0.0, "avg_return": 0.0}
            # Filter to closing trades only (SELL, COVER, HARD_STOP*)
            closes = df[df["action"].isin(["SELL","COVER","HARD_STOP_LONG","HARD_STOP_SHORT","SIGNAL_EXIT_LONG","SIGNAL_EXIT_SHORT"])]
            total = len(closes)
            return {
                "total_trades": total,
                "total_all_actions": len(df),
                "symbols_traded": df["symbol"].nunique(),
            }
        except Exception as e:
            logger.warning(f"Could not compute stats: {e}")
            return {}
