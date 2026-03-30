import json
from fastapi import APIRouter, Depends
from api.database import get_db
from api.auth_utils import get_current_user

router = APIRouter()

@router.get("/latest")
def latest_signals(limit: int = 50, user=Depends(get_current_user)):
    """Return the most recent signal for each symbol.

    Falls back to analysis_cache rows when the signals table is empty,
    so the signals tab shows real data even before the bot has run.
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT s.*
               FROM signals s
               INNER JOIN (
                   SELECT symbol, MAX(timestamp) as max_ts
                   FROM signals
                   GROUP BY symbol
               ) latest ON s.symbol = latest.symbol AND s.timestamp = latest.max_ts
               ORDER BY s.confidence DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()

    if rows:
        return [dict(r) for r in rows]

    # Signals table is empty — fall back to analysis_cache
    try:
        with get_db() as conn:
            cache_rows = conn.execute(
                "SELECT * FROM analysis_cache ORDER BY analyzed_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
    except Exception:
        cache_rows = []

    result = []
    for r in cache_rows:
        c = dict(r)
        # Map analysis_cache fields to the expected signal shape
        rec = c.get("recommendation", "HOLD") or "HOLD"
        action = rec.upper()
        # Try to pull extra detail out of details_json
        details = {}
        try:
            details = json.loads(c.get("details_json") or "{}")
        except Exception:
            pass
        result.append({
            "symbol": c.get("symbol"),
            "timestamp": c.get("analyzed_at"),
            "action": action,
            "confidence": c.get("confidence"),
            "consensus_score": c.get("consensus_score"),
            "recommendation": c.get("recommendation"),
            "direction": c.get("direction"),
            "agreement_pct": c.get("agreement_pct"),
            "technical_score": details.get("technical_score"),
            "sentiment_score": details.get("sentiment_score"),
            "momentum_score": details.get("momentum_score"),
            "fundamental_score": details.get("fundamental_score"),
            "price": c.get("price"),
        })
    return result

@router.get("/history")
def signal_history(symbol: str = None, hours: int = 24, user=Depends(get_current_user)):
    with get_db() as conn:
        if symbol:
            rows = conn.execute(
                """SELECT * FROM signals
                   WHERE symbol = ? AND timestamp >= datetime('now', ?)
                   ORDER BY timestamp DESC LIMIT 200""",
                (symbol, f"-{hours} hours")
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM signals
                   WHERE timestamp >= datetime('now', ?)
                   ORDER BY timestamp DESC LIMIT 200""",
                (f"-{hours} hours",)
            ).fetchall()
    return [dict(r) for r in rows]

@router.get("/actionable")
def actionable_signals(user=Depends(get_current_user)):
    """Return only BUY/SELL/SHORT/COVER signals from the last scan."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM signals
               WHERE action NOT IN ('HOLD', 'Action.HOLD')
               AND timestamp >= datetime('now', '-10 minutes')
               ORDER BY confidence DESC LIMIT 20"""
        ).fetchall()
    return [dict(r) for r in rows]
