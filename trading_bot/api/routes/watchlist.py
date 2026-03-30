"""Watchlist endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.database import get_db
from api.auth_utils import get_current_user

router = APIRouter()


class AddWatchlistRequest(BaseModel):
    symbol: str


@router.get("/")
def list_watchlist(user=Depends(get_current_user)):
    """Return watchlist with latest analysis_cache data for each symbol."""
    user_id = user.get("user_id", 1)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,)
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        symbol = item["symbol"]
        try:
            with get_db() as conn:
                cache = conn.execute(
                    "SELECT * FROM analysis_cache WHERE symbol = ?", (symbol,)
                ).fetchone()
            if cache:
                item.update(dict(cache))
        except Exception:
            pass
        result.append(item)

    return result


@router.post("/")
def add_to_watchlist(req: AddWatchlistRequest, user=Depends(get_current_user)):
    """Add a symbol to the watchlist."""
    user_id = user.get("user_id", 1)
    symbol = req.symbol.upper()
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO watchlist (user_id, symbol) VALUES (?, ?)",
                (user_id, symbol)
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM watchlist WHERE user_id=? AND symbol=?",
                (user_id, symbol)
            ).fetchone()
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{symbol}")
def remove_from_watchlist(symbol: str, user=Depends(get_current_user)):
    """Remove a symbol from the watchlist."""
    user_id = user.get("user_id", 1)
    symbol = symbol.upper()
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM watchlist WHERE user_id=? AND symbol=?", (user_id, symbol)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Symbol not in watchlist")
        conn.execute(
            "DELETE FROM watchlist WHERE user_id=? AND symbol=?", (user_id, symbol)
        )
        conn.commit()
    return {"success": True, "symbol": symbol}
