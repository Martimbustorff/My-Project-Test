from fastapi import APIRouter, Depends
from api.database import get_db
from api.auth_utils import get_current_user

router = APIRouter()

@router.get("/latest")
def latest_signals(limit: int = 50, user=Depends(get_current_user)):
    """Return the most recent signal for each symbol."""
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
    return [dict(r) for r in rows]

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
