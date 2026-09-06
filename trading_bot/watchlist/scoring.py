"""
watchlist/scoring.py
--------------------
Pure scoring logic for the weekly watchlist.  **No network access** – every
function here operates on plain numbers or a :class:`StockMetrics` instance, so
the whole module is trivially unit-testable.

Three independent dimensions are scored on a 0–100 scale:

* ``upside_score``    – analyst price-target upside vs. current price.
* ``growth_score``    – revenue / earnings growth history.
* ``consensus_score`` – aggregated analyst buy/hold/sell recommendation.

A weighted ``composite_score`` blends the three, and :func:`is_growing`
applies the "growing stock" gate used to qualify a name for the watchlist.

All scoring functions are deliberately monotonic and clamped to [0, 100] so a
missing input degrades to a neutral score rather than crashing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _lerp(value: float, in_lo: float, in_hi: float,
          out_lo: float = 0.0, out_hi: float = 100.0) -> float:
    """Linearly map *value* from [in_lo, in_hi] onto [out_lo, out_hi], clamped."""
    if in_hi == in_lo:
        return out_lo
    frac = (value - in_lo) / (in_hi - in_lo)
    return _clip(out_lo + frac * (out_hi - out_lo), min(out_lo, out_hi), max(out_lo, out_hi))


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class StockMetrics:
    """
    All metrics gathered for a single candidate, plus the derived scores.

    Raw inputs are ``Optional`` because any individual field may be missing
    from the data provider.  Growth/return fields are expressed as fractions
    (``0.25`` == +25%), prices in the security's native currency.
    """

    symbol: str
    name: str
    region: str
    exchange: str
    currency: str = "USD"

    # ── valuation / price ────────────────────────────────────────────────
    market_cap: Optional[float] = None
    current_price: Optional[float] = None

    # ── analyst price targets (→ upside) ─────────────────────────────────
    target_mean_price: Optional[float] = None
    target_high_price: Optional[float] = None
    target_low_price: Optional[float] = None
    upside_pct: Optional[float] = None          # fraction vs current price

    # ── growth history ───────────────────────────────────────────────────
    revenue_growth: Optional[float] = None      # most-recent YoY, fraction
    earnings_growth: Optional[float] = None      # most-recent YoY, fraction
    revenue_cagr: Optional[float] = None         # multi-year CAGR, fraction

    # ── analyst consensus ────────────────────────────────────────────────
    recommendation_mean: Optional[float] = None  # 1=Strong Buy … 5=Strong Sell
    recommendation_key: Optional[str] = None
    num_analysts: Optional[int] = None

    # ── short-horizon trend (≤3 months) ──────────────────────────────────
    price_change_3m: Optional[float] = None      # fraction over ~3 months
    above_50d_ma: Optional[bool] = None

    # ── conviction override (manual, user-set) ───────────────────────────
    high_conviction: bool = False

    # ── derived scores (0–100) ───────────────────────────────────────────
    upside_score: float = 0.0
    growth_score: float = 0.0
    consensus_score: float = 0.0
    composite_score: float = 0.0
    is_growing: bool = False
    notes: list[str] = field(default_factory=list)

    # ── data-quality flags ───────────────────────────────────────────────
    # True when the dimension had NO underlying data and its score is just the
    # neutral 50 fallback. Without these, a missing input is indistinguishable
    # from a genuine middling reading — an unverified number masquerading as a
    # signal, which is exactly what a ranking must never hide.
    upside_estimated: bool = False
    growth_estimated: bool = False
    consensus_estimated: bool = False

    @property
    def data_coverage(self) -> int:
        """How many of the three dimensions are backed by real data (0–3)."""
        return 3 - sum(
            (self.upside_estimated, self.growth_estimated, self.consensus_estimated)
        )

    @property
    def missing_dimensions(self) -> list[str]:
        """Names of the dimensions whose score is only a neutral fallback."""
        pairs = (
            ("upside", self.upside_estimated),
            ("growth", self.growth_estimated),
            ("consensus", self.consensus_estimated),
        )
        return [name for name, missing in pairs if missing]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["data_coverage"] = self.data_coverage
        data["missing_dimensions"] = self.missing_dimensions
        return data


# ---------------------------------------------------------------------------
# Dimension 1 — analyst upside
# ---------------------------------------------------------------------------

# Below this many covering analysts, a price target is treated as
# lower-confidence and its upside score is shrunk toward neutral.
MIN_TARGET_ANALYSTS = 5


def score_upside(
    upside_pct: Optional[float],
    num_analysts: Optional[int] = None,
    high_conviction: bool = False,
    min_analysts: int = MIN_TARGET_ANALYSTS,
) -> float:
    """
    Score the analyst price-target upside on a 0–100 scale.

    Mapping (linear, clamped):
        -10% upside →   0
          0% upside →  25
        +30% upside → 100

    **Thin-coverage handling:** a huge upside backed by only one or two
    analysts is unreliable (e.g. a single bullish target on a micro-cap), so
    when fewer than *min_analysts* cover the name the score is shrunk toward the
    neutral 50 midpoint, proportionally to coverage. This stops sparsely-covered
    names from dominating the ranking on the strength of a single estimate.

    *high_conviction* bypasses the shrink entirely — a manual override for names
    the user has independently judged to be high-conviction disruptors (no data
    source can certify "future greatness", so this is a deliberate human call).

    A missing/None upside returns a neutral 50.
    """
    if upside_pct is None:
        return 50.0
    base = _lerp(upside_pct, -0.10, 0.30, 0.0, 100.0)
    if (
        not high_conviction
        and num_analysts is not None
        and num_analysts < min_analysts
    ):
        coverage = _clip(num_analysts / min_analysts, 0.0, 1.0)
        base = 50.0 + (base - 50.0) * coverage
    return round(base, 2)


def compute_upside_pct(current_price: Optional[float],
                       target_mean_price: Optional[float]) -> Optional[float]:
    """Return ``(target / price) - 1`` as a fraction, or None if not derivable."""
    if not current_price or not target_mean_price or current_price <= 0:
        return None
    return (target_mean_price / current_price) - 1.0


# ---------------------------------------------------------------------------
# Dimension 2 — financial growth history
# ---------------------------------------------------------------------------

def _growth_component(value: Optional[float]) -> Optional[float]:
    """
    Map a single growth fraction onto 0–100.

        -10% →   0
          0% →  30
        +25% →  90
        +50% → 100
    """
    if value is None:
        return None
    return _lerp(value, -0.10, 0.50, 0.0, 100.0)


def score_growth(revenue_growth: Optional[float],
                 earnings_growth: Optional[float] = None,
                 revenue_cagr: Optional[float] = None) -> float:
    """
    Blend available growth metrics into a 0–100 growth score.

    Revenue growth is weighted highest (it is the most consistently reported
    and least noisy of the three), then multi-year CAGR, then the more volatile
    earnings-growth figure.  Only the components that are present contribute,
    and the weights are renormalised accordingly.  Returns a neutral 50 when no
    growth data is available at all.
    """
    parts = [
        (_growth_component(revenue_growth), 0.5),
        (_growth_component(revenue_cagr),   0.3),
        (_growth_component(earnings_growth), 0.2),
    ]
    present = [(s, w) for s, w in parts if s is not None]
    if not present:
        return 50.0
    total_w = sum(w for _, w in present)
    score = sum(s * w for s, w in present) / total_w
    return round(score, 2)


# ---------------------------------------------------------------------------
# Dimension 3 — analyst consensus
# ---------------------------------------------------------------------------

def score_consensus(recommendation_mean: Optional[float],
                    num_analysts: Optional[int] = None) -> float:
    """
    Score the analyst consensus on a 0–100 scale.

    yfinance/IBES style ``recommendation_mean`` runs 1 (Strong Buy) → 5
    (Strong Sell), so we invert it:

        1.0 (Strong Buy)  → 100
        3.0 (Hold)        →  50
        5.0 (Strong Sell) →   0

    Thin coverage is treated as lower-confidence: with fewer than 5 covering
    analysts the score is shrunk toward the neutral 50 midpoint proportionally
    to coverage, so a single bullish analyst cannot dominate the ranking.
    A missing recommendation returns a neutral 50.
    """
    if recommendation_mean is None:
        return 50.0
    base = _lerp(recommendation_mean, 5.0, 1.0, 0.0, 100.0)
    if num_analysts is not None and num_analysts < 5:
        coverage = _clip(num_analysts / 5.0, 0.0, 1.0)
        base = 50.0 + (base - 50.0) * coverage
    return round(base, 2)


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "upside": 0.40,
    "growth": 0.35,
    "consensus": 0.25,
}


def composite_score(upside_score: float,
                    growth_score: float,
                    consensus_score: float,
                    weights: Optional[dict] = None) -> float:
    """Weighted blend of the three dimension scores (0–100)."""
    w = weights or DEFAULT_WEIGHTS
    total = w["upside"] + w["growth"] + w["consensus"]
    if total <= 0:
        return 0.0
    score = (
        upside_score * w["upside"]
        + growth_score * w["growth"]
        + consensus_score * w["consensus"]
    ) / total
    return round(score, 2)


# ---------------------------------------------------------------------------
# "Growing stock" gate
# ---------------------------------------------------------------------------

@dataclass
class GrowthGate:
    """Thresholds that qualify a candidate as a 'growing' stock."""

    min_revenue_growth: float = 0.05    # ≥ +5% YoY revenue
    min_upside_pct: float = 0.0         # analysts see at least flat upside
    max_recommendation_mean: float = 3.0  # consensus no worse than Hold
    require_positive_momentum: bool = False  # ≤3-month trend must be positive


def is_growing(metrics: StockMetrics, gate: Optional[GrowthGate] = None) -> bool:
    """
    Decide whether *metrics* qualifies as a growing stock for the watchlist.

    A name qualifies when it shows genuine top-line growth **and** forward
    promise (analyst upside or a constructive consensus).  Each rule is skipped
    when its underlying data is missing rather than failing the candidate, so
    sparsely-covered names are judged on what is known.  Momentum is an
    optional gate (off by default) for callers who want to require a positive
    ≤3-month trend.
    """
    gate = gate or GrowthGate()

    # Top-line growth is the core requirement.
    if metrics.revenue_growth is not None and metrics.revenue_growth < gate.min_revenue_growth:
        return False

    # Forward promise: at least one of upside / consensus must be constructive.
    upside_ok = (
        metrics.upside_pct is None
        or metrics.upside_pct >= gate.min_upside_pct
    )
    consensus_ok = (
        metrics.recommendation_mean is None
        or metrics.recommendation_mean <= gate.max_recommendation_mean
    )
    if not (upside_ok or consensus_ok):
        return False

    if gate.require_positive_momentum:
        if metrics.price_change_3m is not None and metrics.price_change_3m <= 0:
            return False

    return True


# ---------------------------------------------------------------------------
# Convenience: score an entire StockMetrics in place
# ---------------------------------------------------------------------------

def apply_scores(metrics: StockMetrics,
                 weights: Optional[dict] = None,
                 gate: Optional[GrowthGate] = None) -> StockMetrics:
    """
    Populate the derived score fields on *metrics* and return it.

    Computes ``upside_pct`` from price/target when it was not supplied, then
    fills ``upside_score``, ``growth_score``, ``consensus_score``,
    ``composite_score`` and the ``is_growing`` flag.
    """
    if metrics.upside_pct is None:
        metrics.upside_pct = compute_upside_pct(
            metrics.current_price, metrics.target_mean_price
        )

    # Record which dimensions have no underlying data *before* scoring, so a
    # neutral 50 fallback is never mistaken for a real reading downstream.
    metrics.upside_estimated = metrics.upside_pct is None
    metrics.growth_estimated = (
        metrics.revenue_growth is None
        and metrics.revenue_cagr is None
        and metrics.earnings_growth is None
    )
    metrics.consensus_estimated = metrics.recommendation_mean is None

    metrics.upside_score = score_upside(
        metrics.upside_pct,
        num_analysts=metrics.num_analysts,
        high_conviction=metrics.high_conviction,
    )
    metrics.growth_score = score_growth(
        metrics.revenue_growth, metrics.earnings_growth, metrics.revenue_cagr
    )
    metrics.consensus_score = score_consensus(
        metrics.recommendation_mean, metrics.num_analysts
    )
    metrics.composite_score = composite_score(
        metrics.upside_score,
        metrics.growth_score,
        metrics.consensus_score,
        weights,
    )
    metrics.is_growing = is_growing(metrics, gate)
    return metrics
