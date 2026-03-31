"""
Portfolio Optimizer — uses PyPortfolioOpt (free, open source) to suggest
optimal position sizing based on the consensus signals.

Also implements a simplified Almgren-Chriss market impact model for
estimating the cost of entering/exiting positions.

Install: pip install PyPortfolioOpt

References:
  - PyPortfolioOpt: https://pyportfolioopt.readthedocs.io/
  - Almgren & Chriss (2000): "Optimal execution of portfolio transactions"
"""
import logging
from typing import List, Dict, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Portfolio Optimization (PyPortfolioOpt) ───────────────────────────────

def optimize_portfolio(
    symbols: List[str],
    scores: Dict[str, float],   # consensus scores per symbol
    total_capital: float = 10_000.0,
    risk_aversion: float = 1.0,  # 0 = max return, higher = more conservative
) -> Dict[str, dict]:
    """
    Given a list of symbols and their consensus scores, compute optimal
    capital allocation using mean-variance optimization.

    Returns dict of {symbol: {weight, dollar_amount, rationale}}
    Falls back to score-proportional weighting if PyPortfolioOpt fails.
    """
    if len(symbols) < 2:
        # Single position: allocate up to 10% of capital
        sym = symbols[0] if symbols else None
        if not sym:
            return {}
        return {
            sym: {
                "weight": 0.10,
                "dollar_amount": total_capital * 0.10,
                "rationale": "Single position — 10% cap applied",
            }
        }

    # Fetch historical returns
    try:
        import yfinance as yf
        prices = yf.download(
            symbols, period="1y", auto_adjust=True, progress=False
        )["Close"]
        if isinstance(prices, pd.Series):
            prices = prices.to_frame(symbols[0])
        prices = prices.dropna(how="all", axis=1)
        available = [s for s in symbols if s in prices.columns]
        prices = prices[available]

        if len(available) < 2:
            raise ValueError("Not enough price data")

        returns = prices.pct_change().dropna()

    except Exception as e:
        logger.warning("Could not fetch prices for optimization: %s", e)
        return _score_proportional(symbols, scores, total_capital)

    # Try PyPortfolioOpt
    try:
        from pypfopt import EfficientFrontier, risk_models, expected_returns, objective_functions

        mu = expected_returns.mean_historical_return(prices)
        S = risk_models.sample_cov(prices)

        # Tilt expected returns toward consensus scores
        score_boost = pd.Series({s: scores.get(s, 0.0) * 0.05 for s in available})
        mu = mu + score_boost.reindex(mu.index).fillna(0)

        ef = EfficientFrontier(mu, S, weight_bounds=(0, 0.20))  # max 20% per position
        ef.add_objective(objective_functions.L2_reg, gamma=risk_aversion)
        ef.max_sharpe()
        weights = ef.clean_weights()

        result = {}
        for sym, w in weights.items():
            if w > 0.01:  # ignore tiny allocations
                result[sym] = {
                    "weight": round(w, 4),
                    "dollar_amount": round(total_capital * w, 2),
                    "rationale": f"Mean-variance optimal (score={scores.get(sym, 0):+.2f})",
                }
        return result

    except ImportError:
        logger.info("PyPortfolioOpt not installed — using score-proportional weighting")
        return _score_proportional(available, scores, total_capital)
    except Exception as e:
        logger.warning("Optimization failed: %s — using score-proportional fallback", e)
        return _score_proportional(available, scores, total_capital)


def _score_proportional(
    symbols: List[str],
    scores: Dict[str, float],
    total_capital: float,
) -> Dict[str, dict]:
    """Fallback: weight by normalized absolute consensus score."""
    pos_scores = {s: max(0, scores.get(s, 0)) for s in symbols}
    total = sum(pos_scores.values()) or 1.0
    result = {}
    for sym, score in pos_scores.items():
        w = min(score / total, 0.20)  # 20% cap
        result[sym] = {
            "weight": round(w, 4),
            "dollar_amount": round(total_capital * w, 2),
            "rationale": f"Score-proportional (score={score:+.2f})",
        }
    return result


# ── Almgren-Chriss Market Impact Model ──────────────────────────────────

def estimate_market_impact(
    symbol: str,
    shares: float,
    avg_daily_volume: float,  # shares/day
    volatility: float,        # daily vol as decimal (e.g. 0.02 = 2%)
    price: float,
    urgency: float = 0.5,     # 0 = slow (VWAP), 1 = immediate
) -> dict:
    """
    Simplified Almgren-Chriss (2000) market impact estimate.

    Models the cost of executing `shares` shares given market microstructure.
    Returns expected implementation shortfall as % of trade value.

    Parameters based on typical US equity market parameters.
    """
    if avg_daily_volume <= 0 or price <= 0:
        return {"impact_pct": 0.0, "impact_dollars": 0.0, "rationale": "Insufficient data"}

    # Participation rate (% of daily volume)
    participation = shares / avg_daily_volume

    # Temporary impact (linear in participation rate)
    # Typical eta (temporary impact) ≈ 0.1 for liquid stocks
    eta = 0.1
    temp_impact = eta * participation * volatility

    # Permanent impact (square-root model)
    # Typical gamma ≈ 0.05
    gamma = 0.05
    perm_impact = gamma * np.sqrt(participation) * volatility

    # Urgency adjustment: faster = more impact
    total_impact_pct = (temp_impact * urgency + perm_impact) * 100

    # Cap at reasonable levels
    total_impact_pct = min(total_impact_pct, 5.0)
    trade_value = shares * price
    impact_dollars = trade_value * total_impact_pct / 100

    urgency_label = "immediate" if urgency > 0.7 else "VWAP" if urgency < 0.3 else "mixed"

    return {
        "impact_pct": round(total_impact_pct, 4),
        "impact_dollars": round(impact_dollars, 2),
        "participation_rate": round(participation * 100, 2),
        "execution_style": urgency_label,
        "rationale": (
            f"Almgren-Chriss model: {participation*100:.1f}% daily volume, "
            f"{urgency_label} execution → {total_impact_pct:.3f}% slippage estimate"
        ),
    }


def get_position_recommendation(
    symbol: str,
    consensus_score: float,
    confidence: float,
    portfolio_value: float,
    current_position_value: float = 0.0,
    avg_daily_volume: float = 1_000_000,
    volatility: float = 0.02,
    price: float = 100.0,
) -> dict:
    """
    Full position recommendation combining:
    1. Optimal allocation % (from consensus score + confidence)
    2. Market impact estimate (Almgren-Chriss)
    3. Risk-adjusted position size

    Returns actionable sizing guidance.
    """
    # Base allocation: score * confidence → max 15% of portfolio
    raw_allocation = abs(consensus_score) * confidence
    target_pct = min(raw_allocation * 0.15, 0.15)  # cap at 15%
    target_value = portfolio_value * target_pct
    target_shares = int(target_value / price) if price > 0 else 0

    # Market impact
    impact = estimate_market_impact(
        symbol, target_shares, avg_daily_volume, volatility, price, urgency=0.3
    )

    # Net expected value after impact
    gross_value = target_shares * price
    net_value = gross_value - impact["impact_dollars"]

    action = "BUY" if consensus_score > 0 else "SHORT"
    change_needed = target_value - current_position_value

    return {
        "symbol": symbol,
        "action": action,
        "target_allocation_pct": round(target_pct * 100, 1),
        "target_value": round(target_value, 2),
        "target_shares": target_shares,
        "current_value": round(current_position_value, 2),
        "change_needed": round(change_needed, 2),
        "market_impact": impact,
        "net_value_after_impact": round(net_value, 2),
        "rationale": (
            f"{action} {target_shares} shares (${target_value:,.0f} = {target_pct*100:.1f}% of portfolio). "
            f"Est. execution cost: ${impact['impact_dollars']:.2f} ({impact['impact_pct']:.3f}%)"
        ),
    }
