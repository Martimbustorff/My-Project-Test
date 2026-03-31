"""
Insights endpoints — portfolio optimization and macro regime data.
"""
from fastapi import APIRouter, Depends
from api.database import get_db
from api.auth_utils import get_current_user
import json

router = APIRouter()


@router.get("/macro")
def macro_context():
    """Current macro regime from FRED data."""
    try:
        from data.macro_data import get_macro_regime
        return get_macro_regime()
    except Exception as e:
        return {"regime": "unknown", "score_adjustment": 0.0, "reasons": [], "error": str(e)}


@router.get("/optimize")
def optimize_positions(user=Depends(get_current_user)):
    """
    Run portfolio optimization on the user's current positions
    using PyPortfolioOpt + Almgren-Chriss sizing.
    """
    user_id = user.get("user_id", 1)

    # Get user positions
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM user_portfolio WHERE user_id = ?", (user_id,)
        ).fetchall()

    if not rows:
        return {"positions": [], "message": "No positions to optimize"}

    positions = [dict(r) for r in rows]
    symbols = [p["symbol"] for p in positions]

    # Get consensus scores from cache
    scores = {}
    with get_db() as conn:
        for sym in symbols:
            row = conn.execute(
                "SELECT consensus_score FROM analysis_cache WHERE symbol = ?", (sym,)
            ).fetchone()
            scores[sym] = float(row["consensus_score"]) if row else 0.0

    # Total portfolio value estimate
    total_cost = sum(p["quantity"] * p["avg_cost"] for p in positions)

    try:
        from analysis.portfolio_optimizer import optimize_portfolio, get_position_recommendation
        import yfinance as yf

        # Fetch current prices
        price_map = {}
        for sym in symbols:
            try:
                price_map[sym] = yf.Ticker(sym).fast_info.last_price or 0.0
            except Exception:
                price_map[sym] = 0.0

        # Run optimization
        allocation = optimize_portfolio(symbols, scores, total_cost)

        # Per-position recommendations
        recommendations = []
        for pos in positions:
            sym = pos["symbol"]
            current_val = pos["quantity"] * (price_map.get(sym) or pos["avg_cost"])
            rec = get_position_recommendation(
                symbol=sym,
                consensus_score=scores.get(sym, 0.0),
                confidence=0.6,
                portfolio_value=total_cost,
                current_position_value=current_val,
                price=price_map.get(sym) or pos["avg_cost"],
            )
            rec["current_allocation_pct"] = round(current_val / total_cost * 100, 1) if total_cost else 0
            rec["optimal_allocation"] = allocation.get(sym, {})
            recommendations.append(rec)

        return {
            "total_portfolio_value": round(total_cost, 2),
            "positions": recommendations,
            "method": "PyPortfolioOpt + Almgren-Chriss",
        }

    except Exception as e:
        return {"error": str(e), "positions": [], "total_portfolio_value": total_cost}
