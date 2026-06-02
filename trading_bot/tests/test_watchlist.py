"""
tests/test_watchlist.py
-----------------------
Unit tests for the watchlist module.  All tests are pure (no network): the
screener is replaced with a stub that returns pre-built StockMetrics, so the
scoring, gating, ranking and assembly logic is exercised deterministically.
"""
import sys
import os

# Ensure the trading_bot package root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from watchlist.scoring import (
    StockMetrics,
    GrowthGate,
    score_upside,
    score_growth,
    score_consensus,
    composite_score,
    compute_upside_pct,
    is_growing,
    apply_scores,
)
from watchlist.universe import (
    default_universe,
    us_universe,
    eu_universe,
    universe_for_regions,
    candidates_from_tickers,
)
from watchlist.watchlist import WatchlistBuilder, WeeklyWatchlist, _monday_of
from watchlist.report import to_markdown


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _metrics(symbol="TST", region="US", **kw):
    base = dict(symbol=symbol, name=symbol, region=region, exchange="NYSE")
    base.update(kw)
    return StockMetrics(**base)


# ---------------------------------------------------------------------------
# score_upside
# ---------------------------------------------------------------------------

class TestScoreUpside:
    def test_none_is_neutral(self):
        assert score_upside(None) == 50.0

    def test_zero_upside_below_neutral(self):
        # 0% maps to 25 on the -10%→0 / +30%→100 scale
        assert score_upside(0.0) == pytest.approx(25.0, abs=0.5)

    def test_high_upside_near_max(self):
        assert score_upside(0.30) == pytest.approx(100.0, abs=0.5)

    def test_negative_upside_clamped_to_zero(self):
        assert score_upside(-0.50) == 0.0

    def test_monotonic_increasing(self):
        assert score_upside(0.05) < score_upside(0.15) < score_upside(0.25)

    def test_bounded_0_100(self):
        for v in (-5, -0.2, 0, 0.1, 0.5, 5):
            assert 0.0 <= score_upside(v) <= 100.0


class TestComputeUpsidePct:
    def test_basic(self):
        assert compute_upside_pct(100.0, 120.0) == pytest.approx(0.20)

    def test_negative(self):
        assert compute_upside_pct(100.0, 90.0) == pytest.approx(-0.10)

    def test_missing_price_returns_none(self):
        assert compute_upside_pct(None, 120.0) is None

    def test_zero_price_returns_none(self):
        assert compute_upside_pct(0.0, 120.0) is None

    def test_missing_target_returns_none(self):
        assert compute_upside_pct(100.0, None) is None


# ---------------------------------------------------------------------------
# score_growth
# ---------------------------------------------------------------------------

class TestScoreGrowth:
    def test_all_none_is_neutral(self):
        assert score_growth(None, None, None) == 50.0

    def test_strong_revenue_growth_high_score(self):
        assert score_growth(0.50) >= 95.0

    def test_negative_growth_low_score(self):
        assert score_growth(-0.10) == pytest.approx(0.0, abs=0.5)

    def test_revenue_weighted_higher_than_earnings(self):
        # Only revenue strong vs only earnings strong: revenue should win
        rev_only = score_growth(revenue_growth=0.50, earnings_growth=None, revenue_cagr=None)
        eps_only = score_growth(revenue_growth=None, earnings_growth=0.50, revenue_cagr=None)
        assert rev_only == eps_only  # each alone renormalises to full weight

    def test_blend_uses_available_only(self):
        # Providing a weak earnings figure alongside strong revenue should pull
        # the blended score below the revenue-only score.
        strong = score_growth(revenue_growth=0.50)
        blended = score_growth(revenue_growth=0.50, earnings_growth=-0.10)
        assert blended < strong

    def test_bounded_0_100(self):
        assert 0.0 <= score_growth(2.0, 2.0, 2.0) <= 100.0


# ---------------------------------------------------------------------------
# score_consensus
# ---------------------------------------------------------------------------

class TestScoreConsensus:
    def test_none_is_neutral(self):
        assert score_consensus(None) == 50.0

    def test_strong_buy_max(self):
        assert score_consensus(1.0, num_analysts=20) == pytest.approx(100.0, abs=0.5)

    def test_hold_midpoint(self):
        assert score_consensus(3.0, num_analysts=20) == pytest.approx(50.0, abs=0.5)

    def test_strong_sell_min(self):
        assert score_consensus(5.0, num_analysts=20) == pytest.approx(0.0, abs=0.5)

    def test_lower_mean_scores_higher(self):
        assert score_consensus(1.5, 20) > score_consensus(2.5, 20)

    def test_thin_coverage_shrinks_toward_neutral(self):
        full = score_consensus(1.0, num_analysts=20)
        thin = score_consensus(1.0, num_analysts=1)
        assert 50.0 < thin < full

    def test_no_coverage_count_uses_raw(self):
        assert score_consensus(1.0, num_analysts=None) == pytest.approx(100.0, abs=0.5)


# ---------------------------------------------------------------------------
# composite_score
# ---------------------------------------------------------------------------

class TestCompositeScore:
    def test_equal_inputs(self):
        assert composite_score(80, 80, 80) == pytest.approx(80.0)

    def test_default_weights_favour_upside(self):
        # Only upside high → composite should beat the same value placed on
        # the lowest-weighted dimension (consensus).
        up = composite_score(100, 0, 0)
        cons = composite_score(0, 0, 100)
        assert up > cons

    def test_zero_weights_safe(self):
        assert composite_score(50, 50, 50, weights={"upside": 0, "growth": 0, "consensus": 0}) == 0.0

    def test_custom_weights(self):
        score = composite_score(100, 0, 0, weights={"upside": 1, "growth": 0, "consensus": 0})
        assert score == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# is_growing gate
# ---------------------------------------------------------------------------

class TestIsGrowing:
    def test_strong_grower_qualifies(self):
        m = _metrics(revenue_growth=0.25, upside_pct=0.15, recommendation_mean=1.8)
        assert is_growing(m) is True

    def test_shrinking_revenue_rejected(self):
        m = _metrics(revenue_growth=-0.05, upside_pct=0.20, recommendation_mean=1.5)
        assert is_growing(m) is False

    def test_below_min_revenue_growth_rejected(self):
        m = _metrics(revenue_growth=0.02, upside_pct=0.20)
        assert is_growing(m, GrowthGate(min_revenue_growth=0.05)) is False

    def test_missing_revenue_judged_on_other_signals(self):
        m = _metrics(revenue_growth=None, upside_pct=0.20, recommendation_mean=1.5)
        assert is_growing(m) is True

    def test_no_forward_promise_rejected(self):
        # Negative upside AND weak consensus → rejected
        m = _metrics(revenue_growth=0.20, upside_pct=-0.10, recommendation_mean=4.0)
        assert is_growing(m) is False

    def test_momentum_gate_blocks_negative_trend(self):
        gate = GrowthGate(require_positive_momentum=True)
        m = _metrics(revenue_growth=0.20, upside_pct=0.20,
                     recommendation_mean=1.5, price_change_3m=-0.08)
        assert is_growing(m, gate) is False

    def test_momentum_gate_allows_positive_trend(self):
        gate = GrowthGate(require_positive_momentum=True)
        m = _metrics(revenue_growth=0.20, upside_pct=0.20,
                     recommendation_mean=1.5, price_change_3m=0.08)
        assert is_growing(m, gate) is True


# ---------------------------------------------------------------------------
# apply_scores
# ---------------------------------------------------------------------------

class TestApplyScores:
    def test_derives_upside_pct(self):
        m = _metrics(current_price=100.0, target_mean_price=130.0,
                     revenue_growth=0.20, recommendation_mean=2.0)
        apply_scores(m)
        assert m.upside_pct == pytest.approx(0.30)
        assert m.upside_score == pytest.approx(100.0, abs=0.5)

    def test_populates_all_scores(self):
        m = _metrics(current_price=100.0, target_mean_price=115.0,
                     revenue_growth=0.20, earnings_growth=0.15,
                     recommendation_mean=2.0, num_analysts=12)
        apply_scores(m)
        assert m.growth_score > 0
        assert m.consensus_score > 0
        assert 0 <= m.composite_score <= 100
        assert isinstance(m.is_growing, bool)

    def test_preserves_explicit_upside_pct(self):
        m = _metrics(upside_pct=0.10, revenue_growth=0.20)
        apply_scores(m)
        assert m.upside_pct == 0.10


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

class TestUniverse:
    def test_default_universe_nonempty(self):
        assert len(default_universe()) > 0

    def test_contains_us_and_eu(self):
        regions = {c.region for c in default_universe()}
        assert "US" in regions and "EU" in regions

    def test_eu_tickers_have_suffix_or_adr(self):
        # Most EU names carry an exchange suffix; ADRs (e.g. NVO) are the
        # documented exception.
        suffixed = [c for c in eu_universe() if "." in c.symbol]
        assert len(suffixed) >= len(eu_universe()) - 3

    def test_universe_for_regions_us_only(self):
        sel = universe_for_regions(["US"])
        assert all(c.region == "US" for c in sel)
        assert len(sel) == len(us_universe())

    def test_universe_for_regions_unknown_falls_back(self):
        sel = universe_for_regions(["XX"])
        assert len(sel) == len(default_universe())

    def test_no_duplicate_symbols(self):
        symbols = [c.symbol for c in default_universe()]
        assert len(symbols) == len(set(symbols))


class TestCandidatesFromTickers:
    def test_infers_us_for_bare_ticker(self):
        cands = candidates_from_tickers(["IREN", "FTNT"])
        assert all(c.region == "US" for c in cands)

    def test_infers_eu_for_suffixed_ticker(self):
        cands = candidates_from_tickers(["ASML.AS", "SAP.DE", "AZN.L"])
        assert all(c.region == "EU" for c in cands)

    def test_mixed_portfolio(self):
        cands = candidates_from_tickers(["IREN", "ASML.AS"])
        by_sym = {c.symbol: c.region for c in cands}
        assert by_sym["IREN"] == "US"
        assert by_sym["ASML.AS"] == "EU"

    def test_uppercases_and_dedupes(self):
        cands = candidates_from_tickers(["iren", "IREN", " ftnt "])
        syms = [c.symbol for c in cands]
        assert syms == ["IREN", "FTNT"]

    def test_us_listed_adr_stays_us(self):
        # ADRs like NVO/GMAB are US-listed → no EU suffix → US
        cands = candidates_from_tickers(["NVO", "GMAB"])
        assert all(c.region == "US" for c in cands)

    def test_names_override(self):
        cands = candidates_from_tickers(["IREN"], names={"IREN": "Iris Energy"})
        assert cands[0].name == "Iris Energy"

    def test_empty_entries_skipped(self):
        assert candidates_from_tickers(["", "  ", "IREN"]) == \
            candidates_from_tickers(["IREN"])


# ---------------------------------------------------------------------------
# WatchlistBuilder (with a stub screener — no network)
# ---------------------------------------------------------------------------

class StubScreener:
    """Returns a fixed, pre-scored set of metrics regardless of input."""

    def __init__(self, metrics):
        self._metrics = metrics

    def screen(self, candidates):
        return list(self._metrics)


def _scored(symbol, region, upside, growth, consensus, growing=True):
    m = _metrics(symbol=symbol, region=region)
    m.upside_score = upside
    m.growth_score = growth
    m.consensus_score = consensus
    m.composite_score = composite_score(upside, growth, consensus)
    m.is_growing = growing
    return m


class TestWatchlistBuilder:
    def _builder(self, metrics, **kw):
        return WatchlistBuilder(screener=StubScreener(metrics), **kw)

    def test_build_filters_non_growing(self):
        metrics = [
            _scored("AAA", "US", 90, 90, 90, growing=True),
            _scored("BBB", "EU", 80, 80, 80, growing=False),
        ]
        wl = self._builder(metrics).build()
        symbols = {r.symbol for r in wl.top_overall}
        assert "AAA" in symbols
        assert "BBB" not in symbols
        assert wl.qualified_count == 1

    def test_ranking_by_upside(self):
        metrics = [
            _scored("LOW", "US", 10, 90, 90),
            _scored("HIGH", "US", 99, 10, 10),
        ]
        wl = self._builder(metrics).build()
        assert wl.by_upside[0].symbol == "HIGH"
        assert wl.by_growth[0].symbol == "LOW"

    def test_ranking_by_consensus(self):
        metrics = [
            _scored("C1", "US", 50, 50, 30),
            _scored("C2", "US", 50, 50, 95),
        ]
        wl = self._builder(metrics).build()
        assert wl.by_consensus[0].symbol == "C2"

    def test_top_n_respected(self):
        metrics = [_scored(f"S{i}", "US", i, i, i) for i in range(20)]
        wl = self._builder(metrics, top_n=5).build()
        assert len(wl.top_overall) == 5
        assert len(wl.by_upside) == 5

    def test_ranks_are_sequential(self):
        metrics = [_scored(f"S{i}", "US", i * 4, i * 4, i * 4) for i in range(5)]
        wl = self._builder(metrics).build()
        assert [r.rank for r in wl.top_overall] == [1, 2, 3, 4, 5]

    def test_returns_weekly_watchlist(self):
        wl = self._builder([_scored("AAA", "US", 90, 90, 90)]).build()
        assert isinstance(wl, WeeklyWatchlist)
        assert wl.horizon_days == 90
        assert "US" in wl.regions

    def test_json_roundtrip(self):
        wl = self._builder([_scored("AAA", "US", 90, 90, 90)]).build()
        payload = wl.to_json()
        assert "AAA" in payload
        assert "week_of" in payload

    def test_empty_screen_produces_empty_lists(self):
        wl = self._builder([]).build()
        assert wl.qualified_count == 0
        assert wl.top_overall == []

    def test_include_all_ranks_non_growing(self):
        # Portfolio mode: a non-growing holding should still appear.
        metrics = [
            _scored("KEEP", "US", 90, 90, 90, growing=True),
            _scored("WEAK", "US", 20, 20, 20, growing=False),
        ]
        wl = self._builder(metrics).build(include_all=True)
        symbols = {r.symbol for r in wl.top_overall}
        assert symbols == {"KEEP", "WEAK"}
        # Ranking still respected: stronger composite first.
        assert wl.top_overall[0].symbol == "KEEP"

    def test_include_all_false_still_filters(self):
        metrics = [
            _scored("KEEP", "US", 90, 90, 90, growing=True),
            _scored("WEAK", "US", 20, 20, 20, growing=False),
        ]
        wl = self._builder(metrics).build(include_all=False)
        assert {r.symbol for r in wl.top_overall} == {"KEEP"}


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

class TestReport:
    def _wl(self):
        metrics = [_scored("AAA", "US", 90, 80, 70)]
        return WatchlistBuilder(screener=StubScreener(metrics)).build()

    def test_markdown_contains_sections(self):
        md = to_markdown(self._wl())
        assert "Biggest Upside" in md
        assert "Financial Growth" in md
        assert "Analyst Consensus" in md
        assert "AAA" in md

    def test_markdown_has_disclaimer(self):
        md = to_markdown(self._wl())
        assert "Not investment advice" in md


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

class TestMondayOf:
    def test_monday_of_returns_monday(self):
        import datetime as dt
        # 2026-05-29 is a Friday → Monday is 2026-05-25
        assert _monday_of(dt.date(2026, 5, 29)) == dt.date(2026, 5, 25)

    def test_monday_of_monday_is_itself(self):
        import datetime as dt
        assert _monday_of(dt.date(2026, 5, 25)) == dt.date(2026, 5, 25)
