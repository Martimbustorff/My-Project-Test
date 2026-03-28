from fastapi import APIRouter, Depends
from api.database import get_db
from api.auth_utils import get_current_user

router = APIRouter()

@router.get("/summary")
def portfolio_summary(user=Depends(get_current_user)):
    """Return the most recent portfolio snapshot."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    if not row:
        return {
            "portfolio_value": 0, "equity": 0, "cash": 0,
            "daily_pnl": 0, "daily_pnl_pct": 0,
            "long_positions": 0, "short_positions": 0,
            "net_exposure_pct": 0, "gross_exposure_pct": 0,
            "unrealized_pnl": 0, "last_updated": None
        }
    return dict(row)

@router.get("/equity-curve")
def equity_curve(days: int = 30, user=Depends(get_current_user)):
    """Return equity curve data points for charting."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT timestamp, portfolio_value as value
               FROM portfolio_snapshots
               WHERE timestamp >= datetime('now', ?)
               ORDER BY timestamp ASC""",
            (f"-{days} days",)
        ).fetchall()
    return [dict(r) for r in rows]

@router.get("/positions")
def positions(user=Depends(get_current_user)):
    """Return all data from latest snapshot including per-position P&L from trades."""
    # Since we don't store live position data in DB separately,
    # return the latest snapshot metrics and recent trade summary
    with get_db() as conn:
        snapshot = conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        # Get currently open positions by finding BUY/SHORT without matching SELL/COVER
        open_trades = conn.execute("""
            SELECT symbol,
                   MAX(CASE WHEN action IN ('BUY','SHORT') THEN action END) as side,
                   MAX(CASE WHEN action IN ('BUY','SHORT') THEN entry_price END) as entry_price,
                   MAX(CASE WHEN action IN ('BUY','SHORT') THEN shares END) as shares,
                   MAX(timestamp) as last_update
            FROM trades
            GROUP BY symbol
            HAVING MAX(CASE WHEN action IN ('BUY','SHORT') THEN 1 ELSE 0 END) >
                   MAX(CASE WHEN action IN ('SELL','COVER','HARD_STOP_LONG','HARD_STOP_SHORT','SIGNAL_EXIT_LONG','SIGNAL_EXIT_SHORT') THEN 1 ELSE 0 END)
        """).fetchall()
    return {
        "snapshot": dict(snapshot) if snapshot else {},
        "positions": [dict(r) for r in open_trades]
    }

@router.get("/history")
def portfolio_history(days: int = 30, user=Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM portfolio_snapshots
               WHERE timestamp >= datetime('now', ?)
               ORDER BY timestamp ASC""",
            (f"-{days} days",)
        ).fetchall()
    return [dict(r) for r in rows]
