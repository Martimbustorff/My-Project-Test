from fastapi import APIRouter, Depends
from api.database import get_db
from api.auth_utils import get_current_user

router = APIRouter()

@router.get("/history")
def trade_history(limit: int = 100, user=Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]

@router.get("/stats")
def trade_stats(user=Depends(get_current_user)):
    """Aggregate trade performance statistics."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as n FROM trades").fetchone()["n"]
        by_action = conn.execute(
            "SELECT action, COUNT(*) as count FROM trades GROUP BY action"
        ).fetchall()
        recent = conn.execute(
            """SELECT * FROM trades
               WHERE timestamp >= datetime('now', '-7 days')
               ORDER BY timestamp DESC"""
        ).fetchall()
    return {
        "total_trades": total,
        "by_action": [dict(r) for r in by_action],
        "recent_7d": [dict(r) for r in recent],
    }
