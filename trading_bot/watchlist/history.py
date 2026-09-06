"""
watchlist/history.py
--------------------
Week-over-week memory for the watchlist.

Each run writes a JSON snapshot; the next run loads the previous one and
reports **what changed** — which names entered, which dropped out, and who moved
up or down the ranking. Without this a weekly report is a series of unrelated
photographs: you can see today's ranking but not that a holding has slid six
places in three weeks, which is usually the more actionable signal.

Pure module: comparison logic has no network dependency and only touches the
filesystem through :func:`find_previous_snapshot`.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .watchlist import WeeklyWatchlist

logger = logging.getLogger(__name__)

# <label>_<YYYY-MM-DD>.json
_SNAPSHOT_RE = re.compile(r"^(?P<label>.+)_(?P<date>\d{4}-\d{2}-\d{2})\.json$")


@dataclass
class RankMove:
    """A name that stayed in the list but changed position."""

    symbol: str
    previous_rank: int
    current_rank: int
    previous_score: Optional[float] = None
    current_score: Optional[float] = None

    @property
    def delta(self) -> int:
        """Positive = moved up the ranking (towards #1)."""
        return self.previous_rank - self.current_rank


@dataclass
class WatchlistDelta:
    """What changed between two watchlist snapshots."""

    previous_week_of: str
    current_week_of: str
    entered: list[str] = field(default_factory=list)
    exited: list[str] = field(default_factory=list)
    moves: list[RankMove] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.entered or self.exited or any(m.delta for m in self.moves))

    def biggest_moves(self, limit: int = 5) -> list[RankMove]:
        """Moves ordered by magnitude, largest first; unchanged ranks dropped."""
        moved = [m for m in self.moves if m.delta]
        return sorted(moved, key=lambda m: abs(m.delta), reverse=True)[:limit]


def _ranking_of(snapshot: dict | WeeklyWatchlist) -> dict[str, dict]:
    """
    Return ``{symbol: {rank, composite_score}}`` for a snapshot.

    Prefers the complete ``all_ranked`` record; falls back to ``top_overall``
    for snapshots written before that field existed.
    """
    if isinstance(snapshot, WeeklyWatchlist):
        rows = snapshot.all_ranked or [
            {"rank": r.rank, "symbol": r.symbol, "composite_score": r.composite_score}
            for r in snapshot.top_overall
        ]
    else:
        rows = snapshot.get("all_ranked") or snapshot.get("top_overall") or []

    out: dict[str, dict] = {}
    for row in rows:
        symbol = row.get("symbol")
        if symbol:
            out[symbol] = {
                "rank": row.get("rank"),
                "composite_score": row.get("composite_score"),
            }
    return out


def _week_of(snapshot: dict | WeeklyWatchlist) -> str:
    if isinstance(snapshot, WeeklyWatchlist):
        return snapshot.week_of
    return snapshot.get("week_of", "unknown")


def compare_watchlists(previous: dict, current: WeeklyWatchlist) -> WatchlistDelta:
    """Diff a previously-saved snapshot against the current watchlist."""
    prev_rank = _ranking_of(previous)
    curr_rank = _ranking_of(current)

    entered = sorted(set(curr_rank) - set(prev_rank))
    exited = sorted(set(prev_rank) - set(curr_rank))

    moves: list[RankMove] = []
    for symbol in sorted(set(prev_rank) & set(curr_rank)):
        before, after = prev_rank[symbol], curr_rank[symbol]
        if before["rank"] is None or after["rank"] is None:
            continue
        moves.append(
            RankMove(
                symbol=symbol,
                previous_rank=int(before["rank"]),
                current_rank=int(after["rank"]),
                previous_score=before.get("composite_score"),
                current_score=after.get("composite_score"),
            )
        )

    return WatchlistDelta(
        previous_week_of=_week_of(previous),
        current_week_of=_week_of(current),
        entered=entered,
        exited=exited,
        moves=moves,
    )


def find_previous_snapshot(out_dir: str | Path, label: str,
                           before_week_of: Optional[str] = None) -> Optional[Path]:
    """
    Return the most recent ``<label>_<date>.json`` snapshot in *out_dir*.

    When *before_week_of* is given, snapshots from that week or later are
    ignored, so a run does not compare against the file it is about to write.
    Returns None when there is no prior snapshot (the first run has no memory
    to build on, which is expected rather than an error).
    """
    directory = Path(out_dir)
    if not directory.is_dir():
        return None

    candidates: list[tuple[str, Path]] = []
    for path in directory.glob(f"{label}_*.json"):
        match = _SNAPSHOT_RE.match(path.name)
        if not match or match.group("label") != label:
            continue
        snapshot_date = match.group("date")
        if before_week_of and snapshot_date >= before_week_of:
            continue
        candidates.append((snapshot_date, path))

    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[0])[1]


def load_snapshot(path: str | Path) -> Optional[dict]:
    """Load a snapshot JSON, returning None when it is missing or unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read snapshot %s: %s", path, exc)
        return None


def delta_against_previous(current: WeeklyWatchlist, out_dir: str | Path,
                           label: str) -> Optional[WatchlistDelta]:
    """
    Convenience: find the previous snapshot for *label* and diff it against
    *current*.  Returns None when there is no usable prior snapshot.
    """
    path = find_previous_snapshot(out_dir, label, before_week_of=current.week_of)
    if path is None:
        logger.info("No previous %s snapshot in %s — no week-over-week diff.",
                    label, out_dir)
        return None
    previous = load_snapshot(path)
    if previous is None:
        return None
    logger.info("Comparing against %s", path)
    return compare_watchlists(previous, current)
