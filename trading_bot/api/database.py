"""Shared SQLite connection for the API."""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "trading_bot.db")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT UNIQUE NOT NULL,
                password   TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol              TEXT NOT NULL,
                timestamp           TEXT DEFAULT (datetime('now')),
                action              TEXT,
                confidence          REAL,
                technical_score     REAL,
                sentiment_score     REAL,
                momentum_score      REAL,
                fundamental_score   REAL,
                price               REAL,
                notes               TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT NOT NULL,
                timestamp   TEXT DEFAULT (datetime('now')),
                action      TEXT,
                quantity    REAL,
                price       REAL,
                value       REAL,
                pnl         REAL,
                notes       TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp         TEXT DEFAULT (datetime('now')),
                portfolio_value   REAL,
                cash              REAL,
                unrealized_pnl    REAL,
                daily_pnl         REAL,
                daily_pnl_pct     REAL,
                long_count        INTEGER,
                short_count       INTEGER,
                net_exposure_pct  REAL,
                positions_json    TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id        TEXT UNIQUE NOT NULL,
                timestamp     TEXT DEFAULT (datetime('now')),
                status        TEXT DEFAULT 'pending',
                config_json   TEXT,
                results_json  TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_portfolio (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL DEFAULT 1,
                symbol      TEXT NOT NULL,
                quantity    REAL NOT NULL,
                avg_cost    REAL NOT NULL,
                direction   TEXT NOT NULL DEFAULT 'LONG',
                added_at    TEXT DEFAULT (datetime('now')),
                notes       TEXT,
                UNIQUE(user_id, symbol, direction)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL DEFAULT 1,
                symbol    TEXT NOT NULL,
                added_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, symbol)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_cache (
                symbol        TEXT PRIMARY KEY,
                analyzed_at   TEXT,
                price         REAL,
                change_pct    REAL,
                consensus_score REAL,
                recommendation TEXT,
                direction     TEXT,
                confidence    REAL,
                agreement_pct REAL,
                details_json  TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scanner_results (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                scanned_at      TEXT DEFAULT (datetime('now')),
                top_longs_json  TEXT,
                top_shorts_json TEXT,
                symbols_scanned INTEGER
            )
        """)
        conn.commit()

# Keep old name as alias for backward compatibility
def init_users_table():
    init_db()
