"""
watchlist/watchlist.py
----------------------
Orchestrates the weekly watchlist: screen the universe, keep the growing names,
and rank them across the three requested dimensions.

    biggest upside        → ranked by ``upside_score``
    financial growth      → ranked by ``growth_score``
    analyst consensus     → ranked by ``consensus_score``
    (overall pick)        → ranked by ``composite_score``

The result is a :class:`WeeklyWatchlist` that can be serialised to JSON (for
week-over-week persistence) and rendered to Markdown / terminal by
:mod:`watchlist.report`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

from .scoring import StockMetrics, GrowthGate
from .screener import Screener
from .universe import default_universe, universe_for_regions, Candidate

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """A single ranked watchlist entry (a thin view over StockMetrics)."""

    rank: int
    symbol: str
    name: str
    region: str
    exchange: str
    composite_score: float
    upside_score: float
    growth_score: float
    consensus_score: float
    upside_pct: Optional[float]
    revenue_growth: Optional[float]
    recommendation_key: Optional[str]
    price_change_3m: Optional[float]
    current_price: Optional[float]
    target_mean_price: Optional[float]
    currency: str

    @classmethod
    def from_metrics(cls, rank: int, m: StockMetrics) -> "Recommendation":
        return cls(
            rank=rank,
            symbol=m.symbol,
            name=m.name,
            region=m.region,
            exchange=m.exchange,
            composite_score=m.composite_score,
            upside_score=m.upside_score,
            growth_score=m.growth_score,
            consensus_score=m.consensus_score,
            upside_pct=m.upside_pct,
            revenue_growth=m.revenue_growth,
            recommendation_key=m.recommendation_key,
            price_change_3m=m.price_change_3m,
            current_price=m.current_price,
            target_mean_price=m.target_mean_price,
            currency=m.currency,
        )


@dataclass
class WeeklyWatchlist:
    """A full weekly watchlist snapshot."""

    generated_at: str
    week_of: str
    horizon_days: int
    regions: list[str]
    universe_size: int
    qualified_count: int
    top_overall: list[Recommendation] = field(default_factory=list)
    by_upside: list[Recommendation] = field(default_factory=list)
    by_growth: list[Recommendation] = field(default_factory=list)
    by_consensus: list[Recommendation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


def _rank(metrics: list[StockMetrics], key: str, top_n: int) -> list[Recommendation]:
    """Sort *metrics* by attribute *key* (desc) and wrap the top N as Recommendations."""
    ordered = sorted(metrics, key=lambda m: getattr(m, key), reverse=True)[:top_n]
    return [Recommendation.from_metrics(i + 1, m) for i, m in enumerate(ordered)]


class WatchlistBuilder:
    """
    Build a :class:`WeeklyWatchlist` from the candidate universe.

    Parameters
    ----------
    regions : list[str]
        Which regions to include, e.g. ``["US", "EU"]`` (the default).
    horizon_days : int
        Target holding horizon for the recommendations (default 90 = ~3 months).
    top_n : int
        How many names to surface in each ranked list.
    weights : dict, optional
        Composite-score weights (see :data:`scoring.DEFAULT_WEIGHTS`).
    gate : GrowthGate, optional
        Thresholds for qualifying a growing stock.
    screener : Screener, optional
        Inject a custom/mock screener (used in tests).
    """

    def __init__(
        self,
        regions: Optional[list[str]] = None,
        horizon_days: int = 90,
        top_n: int = 10,
        weights: Optional[dict] = None,
        gate: Optional[GrowthGate] = None,
        screener: Optional[Screener] = None,
    ):
        self.regions = [r.upper() for r in (regions or ["US", "EU"])]
        self.horizon_days = horizon_days
        self.top_n = top_n
        self._screener = screener or Screener(weights=weights, gate=gate)

    # ------------------------------------------------------------------

    def candidates(self) -> list[Candidate]:
        """The candidate list for the configured regions."""
        return universe_for_regions(self.regions)

    def build(self, candidates: Optional[list[Candidate]] = None) -> WeeklyWatchlist:
        """
        Screen the universe and assemble the ranked weekly watchlist.

        Only candidates that pass the growing-stock gate are ranked.
        """
        cands = candidates if candidates is not None else self.candidates()
        logger.info("Screening %d candidates across %s …", len(cands), self.regions)

        scored = self._screener.screen(cands)
        growing = [m for m in scored if m.is_growing]
        logger.info("%d of %d screened names qualified as growing.",
                    len(growing), len(scored))

        return self.assemble(growing, universe_size=len(cands))

    def assemble(self, growing: list[StockMetrics], universe_size: int) -> WeeklyWatchlist:
        """Rank an already-screened list of growing names into a watchlist."""
        now = datetime.now(timezone.utc)
        return WeeklyWatchlist(
            generated_at=now.isoformat(timespec="seconds"),
            week_of=_monday_of(now.date()).isoformat(),
            horizon_days=self.horizon_days,
            regions=self.regions,
            universe_size=universe_size,
            qualified_count=len(growing),
            top_overall=_rank(growing, "composite_score", self.top_n),
            by_upside=_rank(growing, "upside_score", self.top_n),
            by_growth=_rank(growing, "growth_score", self.top_n),
            by_consensus=_rank(growing, "consensus_score", self.top_n),
        )


def _monday_of(d: date) -> date:
    """Return the Monday of the ISO week containing *d*."""
    return date.fromordinal(d.toordinal() - d.weekday())


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def save_watchlist(watchlist: WeeklyWatchlist, out_dir: str | Path) -> Path:
    """
    Write *watchlist* to ``<out_dir>/watchlist_<week_of>.json`` and return the
    path.  Creates the directory if needed.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"watchlist_{watchlist.week_of}.json"
    path.write_text(watchlist.to_json(), encoding="utf-8")
    logger.info("Watchlist written to %s", path)
    return path


def load_watchlist(path: str | Path) -> dict:
    """Load a previously-saved watchlist JSON as a plain dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
