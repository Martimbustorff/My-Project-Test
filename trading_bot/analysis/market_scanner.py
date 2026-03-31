"""
Market Scanner — scans a universe of ~100 stocks using the ConsensusEngine.
Results are cached in SQLite. Call run_scan() to trigger a fresh scan.
"""
from __future__ import annotations

import logging
import sqlite3
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "trading_bot.db")

SCAN_UNIVERSE = [
    # ── Mega caps ────────────────────────────────────────────────────────────
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "BRK-B",
    # ── High-growth tech ─────────────────────────────────────────────────────
    "AMD", "ADBE", "CRM", "NOW", "SNOW", "PLTR", "SHOP", "NET", "DDOG",
    "ZS", "CRWD", "PANW", "MDB", "GTLB", "HUBS", "ZM", "OKTA", "BILL",
    # ── Semis / hardware ─────────────────────────────────────────────────────
    "INTC", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC", "MRVL", "ON",
    "TSM", "ASML", "SMCI", "WOLF", "SWKS",
    # ── Legacy tech / infra ──────────────────────────────────────────────────
    "ORCL", "IBM", "CSCO", "HPE", "DELL", "ACN", "INFY",
    # ── Financials ───────────────────────────────────────────────────────────
    "JPM", "V", "MA", "GS", "MS", "BAC", "WFC", "AXP", "BLK", "SCHW",
    "COF", "SQ", "PYPL", "NU", "SOFI",
    # ── Healthcare / biotech ─────────────────────────────────────────────────
    "UNH", "LLY", "JNJ", "ABBV", "MRK", "TMO", "DHR", "AMGN", "GILD",
    "REGN", "VRTX", "MRNA", "BIIB", "ISRG", "BSX", "SYK", "ELV", "HUM",
    # ── Consumer discretionary ───────────────────────────────────────────────
    "WMT", "COST", "HD", "TGT", "MCD", "SBUX", "NKE", "LULU", "ROST",
    "TJX", "AMZN", "BKNG", "ABNB", "MAR", "HLT",
    # ── Consumer staples ─────────────────────────────────────────────────────
    "PG", "KO", "PEP", "PM", "MO", "MDLZ", "CL", "EL",
    # ── Energy ───────────────────────────────────────────────────────────────
    "XOM", "CVX", "COP", "SLB", "MPC", "PSX", "VLO", "EOG", "PXD",
    # ── Industrials / defence ────────────────────────────────────────────────
    "CAT", "DE", "HON", "UNP", "BA", "RTX", "LMT", "GE", "MMM", "FDX",
    # ── Media / entertainment ────────────────────────────────────────────────
    "NFLX", "DIS", "CMCSA", "T", "VZ", "CHTR", "PARA",
    # ── Real estate / utilities ──────────────────────────────────────────────
    "NEE", "DUK", "AMT", "PLD", "EQIX",
    # ── Sector / thematic ETFs ───────────────────────────────────────────────
    "SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "XLK", "XLF",
    "XLE", "XLV", "XLY", "ARKK", "SOXX",
    # ── Crypto ───────────────────────────────────────────────────────────────
    "BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "AVAX-USD",
]


class MarketScanner:
    def __init__(self):
        from analysis.consensus_engine import ConsensusEngine
        self.engine = ConsensusEngine()
        self._scanning = False
        self._progress = 0
        self._total = len(SCAN_UNIVERSE)
        self._last_scan: Optional[str] = None

    def run_scan(self, symbols: Optional[list] = None) -> dict:
        """
        Run full consensus scan over the universe.
        Returns {top_longs, top_shorts, symbols_scanned, scanned_at}.
        """
        universe = symbols or SCAN_UNIVERSE
        self._scanning = True
        self._progress = 0
        self._total = len(universe)
        results = []

        def _analyze(sym: str):
            try:
                result = self.engine.analyze(sym)
                return result
            except Exception as e:
                logger.debug("Scan skip %s: %s", sym, e)
                return None

        # Use a thread pool — yfinance I/O is the bottleneck
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_analyze, sym): sym for sym in universe}
            for future in as_completed(futures):
                self._progress += 1
                res = future.result()
                if res is not None:
                    results.append(res)

        # Sort into longs and shorts
        # BUY / STRONG BUY first, then near-signals (score >= 0.10) as "WATCH"
        top_longs = sorted(
            [r for r in results if r.consensus_score >= 0.10],
            key=lambda r: r.consensus_score,
            reverse=True,
        )[:20]

        # SELL / STRONG SELL first, then near-shorts (score <= -0.10)
        top_shorts = sorted(
            [r for r in results if r.consensus_score <= -0.10],
            key=lambda r: r.consensus_score,
        )[:12]

        def _summary(r) -> dict:
            agents_agree = len(r.bull_agents) if r.consensus_score >= 0 else len(r.bear_agents)
            return {
                "symbol": r.symbol,
                "price": r.price,
                "change_pct": r.change_pct,
                "consensus_score": round(r.consensus_score, 3),
                "recommendation": r.recommendation,
                "direction": r.direction,
                "confidence": round(r.confidence, 3),
                "agreement_pct": round(r.agreement_pct, 1),
                "agents_agree": agents_agree,
                "key_reasons": r.key_reasons[:2],
                "bull_agents": r.bull_agents,
                "bear_agents": r.bear_agents,
            }

        scanned_at = datetime.now(timezone.utc).isoformat()
        self._last_scan = scanned_at
        self._scanning = False

        output = {
            "top_longs": [_summary(r) for r in top_longs],
            "top_shorts": [_summary(r) for r in top_shorts],
            "symbols_scanned": len(results),
            "scanned_at": scanned_at,
        }

        # Persist to DB
        try:
            import json
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scanner_results (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    scanned_at      TEXT DEFAULT (datetime('now')),
                    top_longs_json  TEXT,
                    top_shorts_json TEXT,
                    symbols_scanned INTEGER
                )
            """)
            conn.execute(
                "INSERT INTO scanner_results (scanned_at, top_longs_json, top_shorts_json, symbols_scanned) VALUES (?,?,?,?)",
                (scanned_at, json.dumps(output["top_longs"]), json.dumps(output["top_shorts"]), output["symbols_scanned"])
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to persist scan results: %s", e)

        return output

    def get_top_opportunities(self, limit: int = 15) -> dict:
        """Read latest scan from DB cache."""
        import json
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM scanner_results ORDER BY id DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if not row:
                return {"top_longs": [], "top_shorts": [], "last_scan": None}
            r = dict(row)
            return {
                "top_longs": json.loads(r.get("top_longs_json") or "[]")[:limit],
                "top_shorts": json.loads(r.get("top_shorts_json") or "[]")[:limit],
                "last_scan": r.get("scanned_at"),
                "symbols_scanned": r.get("symbols_scanned", 0),
            }
        except Exception as e:
            logger.error("get_top_opportunities error: %s", e)
            return {"top_longs": [], "top_shorts": [], "last_scan": None}

    def get_status(self) -> dict:
        return {
            "scanning": self._scanning,
            "progress": self._progress,
            "total": self._total,
            "last_scan": self._last_scan,
        }
