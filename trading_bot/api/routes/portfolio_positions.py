"""Manual portfolio positions — eToro holdings entered by the user."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.database import get_db
from api.auth_utils import get_current_user

router = APIRouter()


class AddPositionRequest(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    direction: str = "LONG"
    notes: Optional[str] = None


class UpdatePositionRequest(BaseModel):
    quantity: Optional[float] = None
    avg_cost: Optional[float] = None


def _fetch_price(symbol: str) -> Optional[float]:
    try:
        import yfinance as yf
        price = yf.Ticker(symbol).fast_info.last_price
        if price and price > 0:
            return float(price)
    except Exception:
        pass
    return None


@router.get("/")
def list_positions(user=Depends(get_current_user)):
    """Return all positions with live prices and P&L."""
    user_id = user.get("user_id", 1)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM user_portfolio WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,)
        ).fetchall()

    positions = []
    for row in rows:
        pos = dict(row)
        symbol = pos["symbol"]
        current_price = _fetch_price(symbol)

        if current_price is not None:
            pos["current_price"] = current_price
            pos["current_value"] = pos["quantity"] * current_price
            if pos["direction"] == "SHORT":
                pos["pnl"] = (pos["avg_cost"] - current_price) * pos["quantity"]
            else:
                pos["pnl"] = (current_price - pos["avg_cost"]) * pos["quantity"]
            cost_basis = pos["avg_cost"] * pos["quantity"]
            pos["pnl_pct"] = (pos["pnl"] / cost_basis * 100) if cost_basis else 0.0
        else:
            pos["current_price"] = None
            pos["current_value"] = None
            pos["pnl"] = None
            pos["pnl_pct"] = None

        # Attach latest analysis cache if available
        try:
            with get_db() as conn:
                cache = conn.execute(
                    "SELECT recommendation, consensus_score FROM analysis_cache WHERE symbol = ?",
                    (symbol,)
                ).fetchone()
            if cache:
                pos["recommendation"] = cache["recommendation"]
                pos["consensus_score"] = cache["consensus_score"]
            else:
                pos["recommendation"] = None
                pos["consensus_score"] = None
        except Exception:
            pos["recommendation"] = None
            pos["consensus_score"] = None

        positions.append(pos)

    return positions


@router.post("/")
def add_position(req: AddPositionRequest, user=Depends(get_current_user)):
    """Add a new manual position."""
    user_id = user.get("user_id", 1)
    direction = req.direction.upper()
    if direction not in ("LONG", "SHORT"):
        raise HTTPException(status_code=400, detail="direction must be LONG or SHORT")
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO user_portfolio (user_id, symbol, quantity, avg_cost, direction, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, req.symbol.upper(), req.quantity, req.avg_cost, direction, req.notes)
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM user_portfolio WHERE user_id=? AND symbol=? AND direction=?",
                (user_id, req.symbol.upper(), direction)
            ).fetchone()
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{position_id}")
def update_position(position_id: int, req: UpdatePositionRequest, user=Depends(get_current_user)):
    """Update quantity and/or avg_cost for a position."""
    user_id = user.get("user_id", 1)
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM user_portfolio WHERE id=? AND user_id=?", (position_id, user_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Position not found")

        quantity = req.quantity if req.quantity is not None else row["quantity"]
        avg_cost = req.avg_cost if req.avg_cost is not None else row["avg_cost"]

        conn.execute(
            "UPDATE user_portfolio SET quantity=?, avg_cost=? WHERE id=? AND user_id=?",
            (quantity, avg_cost, position_id, user_id)
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM user_portfolio WHERE id=?", (position_id,)
        ).fetchone()
    return dict(updated)


@router.delete("/{position_id}")
def delete_position(position_id: int, user=Depends(get_current_user)):
    """Remove a position."""
    user_id = user.get("user_id", 1)
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM user_portfolio WHERE id=? AND user_id=?", (position_id, user_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Position not found")
        conn.execute("DELETE FROM user_portfolio WHERE id=? AND user_id=?", (position_id, user_id))
        conn.commit()
    return {"success": True, "id": position_id}


@router.get("/summary")
def portfolio_summary(user=Depends(get_current_user)):
    """Return aggregate portfolio totals."""
    user_id = user.get("user_id", 1)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM user_portfolio WHERE user_id = ?", (user_id,)
        ).fetchall()

    total_cost = 0.0
    total_value = 0.0
    total_pnl = 0.0
    count = len(rows)

    for row in rows:
        pos = dict(row)
        cost_basis = pos["avg_cost"] * pos["quantity"]
        total_cost += cost_basis

        current_price = _fetch_price(pos["symbol"])
        if current_price is not None:
            value = pos["quantity"] * current_price
            total_value += value
            if pos["direction"] == "SHORT":
                pnl = (pos["avg_cost"] - current_price) * pos["quantity"]
            else:
                pnl = (current_price - pos["avg_cost"]) * pos["quantity"]
            total_pnl += pnl
        else:
            total_value += cost_basis

    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0

    return {
        "position_count": count,
        "total_cost": total_cost,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
    }
