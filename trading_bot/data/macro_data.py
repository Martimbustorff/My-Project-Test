"""
Macro Data — free economic data from FRED (Federal Reserve) and
derived market-regime indicators.

No API key required for most endpoints. FRED key improves rate limits.
Install: pip install fredapi pandas requests

FRED data used:
  - DGS10       : 10-Year Treasury yield (risk-free rate)
  - T10Y2Y      : 10Y-2Y yield curve spread (recession signal)
  - VIXCLS      : CBOE VIX (fear index)
  - UMCSENT     : University of Michigan Consumer Sentiment
  - UNRATE      : Unemployment rate
  - CPIAUCSL    : CPI inflation
  - FEDFUNDS    : Fed funds rate
"""
import os
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Free: no key needed — just CSV download
_SERIES = {
    "treasury_10y":   "DGS10",
    "yield_curve":    "T10Y2Y",
    "vix":            "VIXCLS",
    "consumer_sent":  "UMCSENT",
    "unemployment":   "UNRATE",
    "inflation_cpi":  "CPIAUCSL",
    "fed_funds":      "FEDFUNDS",
}


def _fetch_fred_series(series_id: str, periods: int = 30) -> Optional[float]:
    """Fetch latest value of a FRED series (CSV, no key needed)."""
    try:
        url = f"{FRED_BASE}?id={series_id}"
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return None
        lines = resp.text.strip().split("\n")
        # Last line: DATE,VALUE — skip "." (missing data)
        for line in reversed(lines[1:]):
            parts = line.split(",")
            if len(parts) == 2 and parts[1].strip() != ".":
                return float(parts[1].strip())
    except Exception as e:
        logger.debug("FRED fetch failed for %s: %s", series_id, e)
    return None


def get_macro_context() -> dict:
    """
    Returns a dict of current macro indicators.
    All fetched from FRED (free, no key required).
    """
    data = {}
    for name, series_id in _SERIES.items():
        val = _fetch_fred_series(series_id)
        data[name] = val

    return data


def get_macro_regime(context: Optional[dict] = None) -> dict:
    """
    Classify current macro regime and return a score adjustment.

    Returns:
        regime: str  ("risk_on" | "neutral" | "risk_off")
        score_adjustment: float  (-0.15 to +0.15)
            Applied to consensus score — risk_on boosts longs, risk_off boosts shorts
        reasons: List[str]
    """
    if context is None:
        context = get_macro_context()

    score_adj = 0.0
    reasons = []

    # Yield curve: inverted = recession risk (bearish)
    yc = context.get("yield_curve")
    if yc is not None:
        if yc < -0.5:
            score_adj -= 0.10
            reasons.append(f"Yield curve inverted ({yc:+.2f}%) — recession risk elevated")
        elif yc < 0:
            score_adj -= 0.05
            reasons.append(f"Yield curve slightly inverted ({yc:+.2f}%)")
        elif yc > 1.0:
            score_adj += 0.05
            reasons.append(f"Yield curve healthy ({yc:+.2f}%) — growth environment")

    # VIX: fear gauge
    vix = context.get("vix")
    if vix is not None:
        if vix > 30:
            score_adj -= 0.10
            reasons.append(f"VIX at {vix:.1f} — high fear, elevated risk")
        elif vix > 20:
            score_adj -= 0.05
            reasons.append(f"VIX at {vix:.1f} — moderate uncertainty")
        elif vix < 15:
            score_adj += 0.05
            reasons.append(f"VIX at {vix:.1f} — low volatility, calm market")

    # Fed funds rate: high rates hurt growth stocks
    ff = context.get("fed_funds")
    if ff is not None:
        if ff > 5.0:
            score_adj -= 0.05
            reasons.append(f"Fed funds at {ff:.2f}% — restrictive policy")
        elif ff < 2.0:
            score_adj += 0.05
            reasons.append(f"Fed funds at {ff:.2f}% — accommodative policy")

    # Consumer sentiment
    cs = context.get("consumer_sent")
    if cs is not None:
        if cs < 60:
            score_adj -= 0.05
            reasons.append(f"Consumer sentiment weak ({cs:.1f})")
        elif cs > 80:
            score_adj += 0.05
            reasons.append(f"Consumer sentiment strong ({cs:.1f})")

    score_adj = max(-0.20, min(0.20, score_adj))

    if score_adj > 0.05:
        regime = "risk_on"
    elif score_adj < -0.05:
        regime = "risk_off"
    else:
        regime = "neutral"

    return {
        "regime": regime,
        "score_adjustment": round(score_adj, 3),
        "reasons": reasons,
        "raw": {k: v for k, v in context.items() if v is not None},
    }
