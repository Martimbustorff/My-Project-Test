"""
tests/test_signals.py
---------------------
Unit tests for analysis/signals.py: SignalGenerator, Signal, and Action.
"""
import sys
import os

# Ensure the trading_bot package root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch

from analysis.signals import Action, Signal, SignalGenerator


# ---------------------------------------------------------------------------
# Mock Settings (avoids importing real Settings which loads env vars / dotenv)
# ---------------------------------------------------------------------------

class MockSettings:
    TECHNICAL_WEIGHT = 0.35
    SENTIMENT_WEIGHT = 0.30
    MOMENTUM_WEIGHT = 0.20
    FUNDAMENTAL_WEIGHT = 0.15
    STOP_LOSS_PCT = 0.05
    TAKE_PROFIT_PCT = 0.15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_df(n: int = 30, trend: str = "up") -> pd.DataFrame:
    """Create a simple OHLCV DataFrame with *n* rows."""
    if trend == "up":
        close = np.linspace(100, 120, n)
    elif trend == "down":
        close = np.linspace(120, 100, n)
    else:
        close = np.full(n, 100.0)
    return pd.DataFrame({"close": close, "volume": np.full(n, 1_000_000)})


def _make_generator() -> SignalGenerator:
    """Return a SignalGenerator wired to MockSettings."""
    gen = SignalGenerator.__new__(SignalGenerator)
    gen.cfg = MockSettings()
    return gen


def _call_generate(
    gen: SignalGenerator,
    *,
    symbol: str = "AAPL",
    price_df: pd.DataFrame | None = None,
    technical_score: float = 0.5,
    sentiment_score: float = 0.5,
    fundamentals: dict | None = None,
    market_regime: str = "neutral",
    vix: float = 20.0,
    is_long: bool = False,
    is_short: bool = False,
    is_shortable: bool = True,
) -> Signal:
    if price_df is None:
        price_df = _make_price_df()
    if fundamentals is None:
        fundamentals = {}
    return gen.generate_signal(
        symbol=symbol,
        price_df=price_df,
        technical_score=technical_score,
        sentiment_score=sentiment_score,
        news_items=[],
        fundamentals=fundamentals,
        market_regime=market_regime,
        vix=vix,
        is_long=is_long,
        is_short=is_short,
        is_shortable=is_shortable,
    )


# ---------------------------------------------------------------------------
# Action enum
# ---------------------------------------------------------------------------

class TestActionEnum:
    def test_buy_value(self):
        assert Action.BUY == "BUY"
        assert Action.BUY.value == "BUY"

    def test_sell_value(self):
        assert Action.SELL == "SELL"

    def test_short_value(self):
        assert Action.SHORT == "SHORT"

    def test_cover_value(self):
        assert Action.COVER == "COVER"

    def test_hold_value(self):
        assert Action.HOLD == "HOLD"

    def test_all_five_members(self):
        assert len(Action) == 5


# ---------------------------------------------------------------------------
# generate_signal: BUY
# ---------------------------------------------------------------------------

class TestGenerateSignalBuy:
    def test_buy_when_combined_above_threshold(self):
        """combined > 0.35 → BUY (no existing position)."""
        gen = _make_generator()
        # technical=1.0, sentiment=1.0 → combined ≈ 0.35*1 + 0.30*1 + momentum + fund
        # Use high tech/sent to ensure combined well above 0.35
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig = _call_generate(gen, technical_score=1.0, sentiment_score=1.0)
        assert sig.action == Action.BUY

    def test_buy_signal_has_positive_confidence(self):
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig = _call_generate(gen, technical_score=1.0, sentiment_score=1.0)
        assert sig.confidence > 0

    def test_buy_signal_symbol_matches(self):
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig = _call_generate(gen, symbol="TSLA", technical_score=1.0, sentiment_score=1.0)
        assert sig.symbol == "TSLA"


# ---------------------------------------------------------------------------
# generate_signal: HOLD during blackout
# ---------------------------------------------------------------------------

class TestGenerateSignalBlackout:
    def test_hold_during_blackout(self):
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=True):
            sig = _call_generate(gen, technical_score=1.0, sentiment_score=1.0)
        assert sig.action == Action.HOLD

    def test_blackout_confidence_is_zero(self):
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=True):
            sig = _call_generate(gen, technical_score=1.0, sentiment_score=1.0)
        assert sig.confidence == 0.0

    def test_blackout_reasoning_mentions_blackout(self):
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=True):
            sig = _call_generate(gen, technical_score=1.0, sentiment_score=1.0)
        assert any("blackout" in r.lower() for r in sig.reasoning)


# ---------------------------------------------------------------------------
# generate_signal: SELL
# ---------------------------------------------------------------------------

class TestGenerateSignalSell:
    def test_sell_when_long_and_combined_below_negative_threshold(self):
        """is_long=True, combined < -0.20 → SELL."""
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig = _call_generate(
                gen,
                technical_score=-1.0,
                sentiment_score=-1.0,
                price_df=_make_price_df(trend="down"),
                is_long=True,
            )
        assert sig.action == Action.SELL

    def test_no_sell_when_not_long(self):
        """Without an existing long, a negative combined score should not produce SELL."""
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig = _call_generate(
                gen,
                technical_score=-1.0,
                sentiment_score=-1.0,
                price_df=_make_price_df(trend="down"),
                is_long=False,
                is_shortable=False,  # prevent SHORT
            )
        # Should be SHORT or HOLD, not SELL
        assert sig.action != Action.SELL


# ---------------------------------------------------------------------------
# generate_signal: SHORT
# ---------------------------------------------------------------------------

class TestGenerateSignalShort:
    def test_short_when_combined_below_negative_threshold_and_shortable(self):
        """combined < -0.35 and is_shortable=True → SHORT."""
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig = _call_generate(
                gen,
                technical_score=-1.0,
                sentiment_score=-1.0,
                price_df=_make_price_df(trend="down"),
                is_shortable=True,
                market_regime="neutral",
            )
        assert sig.action == Action.SHORT

    def test_no_short_when_not_shortable(self):
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig = _call_generate(
                gen,
                technical_score=-1.0,
                sentiment_score=-1.0,
                price_df=_make_price_df(trend="down"),
                is_shortable=False,
            )
        assert sig.action != Action.SHORT

    def test_no_short_in_bull_regime(self):
        """In a bull regime, combined < -0.35 should NOT trigger a short."""
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig = _call_generate(
                gen,
                technical_score=-1.0,
                sentiment_score=-1.0,
                price_df=_make_price_df(trend="down"),
                is_shortable=True,
                market_regime="bull",
            )
        assert sig.action != Action.SHORT


# ---------------------------------------------------------------------------
# generate_signal: COVER
# ---------------------------------------------------------------------------

class TestGenerateSignalCover:
    def test_cover_when_short_and_combined_above_threshold(self):
        """is_short=True, combined > 0.20 → COVER."""
        gen = _make_generator()
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig = _call_generate(
                gen,
                technical_score=1.0,
                sentiment_score=1.0,
                is_short=True,
            )
        assert sig.action == Action.COVER


# ---------------------------------------------------------------------------
# VIX dampening
# ---------------------------------------------------------------------------

class TestVixDampening:
    def test_vix_above_40_halves_combined_score(self):
        """A borderline BUY (combined just above 0.35) should become HOLD when VIX > 40."""
        gen = _make_generator()

        # First establish what the combined score is without VIX dampening
        # by constructing inputs that yield a combined slightly above 0.35.
        # technical=0.5, sentiment=0.5, flat price (momentum~0), empty fund:
        # combined ≈ 0.35*0.5 + 0.30*0.5 + 0 + 0 = 0.175 + 0.15 = 0.325
        # That's a HOLD normally. Increase technical/sentiment more carefully.
        # Use technical=0.6, sentiment=0.6:
        # combined ≈ 0.35*0.6 + 0.30*0.6 = 0.21 + 0.18 = 0.39 → BUY
        # After VIX dampening: 0.39 * 0.5 = 0.195 → HOLD
        flat_df = _make_price_df(trend="flat")
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig_no_vix = _call_generate(
                gen,
                technical_score=0.6,
                sentiment_score=0.6,
                price_df=flat_df,
                vix=20.0,
            )
            sig_high_vix = _call_generate(
                gen,
                technical_score=0.6,
                sentiment_score=0.6,
                price_df=flat_df,
                vix=45.0,
            )

        assert sig_no_vix.action == Action.BUY
        assert sig_high_vix.action == Action.HOLD

    def test_vix_dampening_reduces_combined_score(self):
        """combined_score with VIX>40 should be roughly half the normal value."""
        gen = _make_generator()
        flat_df = _make_price_df(trend="flat")
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig_normal = _call_generate(
                gen,
                technical_score=1.0,
                sentiment_score=1.0,
                price_df=flat_df,
                vix=20.0,
            )
            sig_damped = _call_generate(
                gen,
                technical_score=1.0,
                sentiment_score=1.0,
                price_df=flat_df,
                vix=50.0,
            )
        assert sig_damped.combined_score < sig_normal.combined_score


# ---------------------------------------------------------------------------
# Bear regime dampening
# ---------------------------------------------------------------------------

class TestBearRegimeDampening:
    def test_bear_regime_dampens_long_signal(self):
        """In a bear regime, a positive combined score is multiplied by 0.7."""
        gen = _make_generator()
        flat_df = _make_price_df(trend="flat")
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig_neutral = _call_generate(
                gen,
                technical_score=1.0,
                sentiment_score=1.0,
                price_df=flat_df,
                market_regime="neutral",
                vix=20.0,
            )
            sig_bear = _call_generate(
                gen,
                technical_score=1.0,
                sentiment_score=1.0,
                price_df=flat_df,
                market_regime="bear",
                vix=20.0,
            )
        # Bear-regime combined score should be lower (dampened)
        assert sig_bear.combined_score < sig_neutral.combined_score

    def test_bear_regime_can_suppress_buy(self):
        """A borderline BUY in neutral may become HOLD in a bear regime."""
        gen = _make_generator()
        flat_df = _make_price_df(trend="flat")
        # Use technical=0.6, sentiment=0.6 → combined ≈ 0.39 (BUY in neutral)
        # In bear regime: 0.39 * 0.7 = 0.273 → HOLD
        with patch.object(SignalGenerator, "_in_blackout_window", return_value=False):
            sig_neutral = _call_generate(
                gen,
                technical_score=0.6,
                sentiment_score=0.6,
                price_df=flat_df,
                market_regime="neutral",
            )
            sig_bear = _call_generate(
                gen,
                technical_score=0.6,
                sentiment_score=0.6,
                price_df=flat_df,
                market_regime="bear",
            )
        assert sig_neutral.action == Action.BUY
        assert sig_bear.action == Action.HOLD


# ---------------------------------------------------------------------------
# _momentum_score
# ---------------------------------------------------------------------------

class TestMomentumScore:
    def test_empty_dataframe_returns_zero(self):
        gen = _make_generator()
        score = gen._momentum_score(pd.DataFrame(), [])
        assert score == 0.0

    def test_none_returns_zero(self):
        gen = _make_generator()
        score = gen._momentum_score(None, [])
        assert score == 0.0

    def test_too_few_rows_returns_zero(self):
        gen = _make_generator()
        df = pd.DataFrame({"close": [100.0, 101.0, 102.0]})  # < 21 rows
        score = gen._momentum_score(df, [])
        assert score == 0.0

    def test_uptrend_returns_positive_score(self):
        gen = _make_generator()
        df = _make_price_df(n=30, trend="up")
        reasoning = []
        score = gen._momentum_score(df, reasoning)
        assert score > 0.0
        assert len(reasoning) == 1  # one reasoning entry added

    def test_downtrend_returns_negative_score(self):
        gen = _make_generator()
        df = _make_price_df(n=30, trend="down")
        score = gen._momentum_score(df, [])
        assert score < 0.0

    def test_missing_close_column_returns_zero(self):
        gen = _make_generator()
        df = pd.DataFrame({"volume": np.ones(30)})
        score = gen._momentum_score(df, [])
        assert score == 0.0


# ---------------------------------------------------------------------------
# _fundamental_score
# ---------------------------------------------------------------------------

class TestFundamentalScore:
    def test_empty_dict_returns_zero(self):
        gen = _make_generator()
        score = gen._fundamental_score({}, [])
        assert score == 0.0

    def test_pe_in_preferred_range_returns_positive(self):
        """P/E in 10-25 range should contribute positively."""
        gen = _make_generator()
        score = gen._fundamental_score({"pe_ratio": 15.0}, [])
        assert score > 0.0

    def test_pe_in_10_to_20_gives_highest_pe_score(self):
        """P/E 10-20 gives score contribution of 0.6 (vs 0.3 for 20-30)."""
        gen = _make_generator()
        score_optimal = gen._fundamental_score({"pe_ratio": 15.0}, [])
        score_moderate = gen._fundamental_score({"pe_ratio": 25.0}, [])
        assert score_optimal > score_moderate

    def test_high_pe_above_50_returns_negative(self):
        gen = _make_generator()
        score = gen._fundamental_score({"pe_ratio": 75.0}, [])
        assert score < 0.0

    def test_pe_between_30_and_50_returns_slightly_negative(self):
        gen = _make_generator()
        score = gen._fundamental_score({"pe_ratio": 45.0}, [])
        assert score < 0.0

    def test_eps_growth_positive_adds_to_score(self):
        gen = _make_generator()
        score_with_growth = gen._fundamental_score({"eps_growth": 0.3}, [])
        score_without = gen._fundamental_score({}, [])
        assert score_with_growth > score_without

    def test_eps_growth_negative_reduces_score(self):
        gen = _make_generator()
        score = gen._fundamental_score({"eps_growth": -0.5}, [])
        assert score < 0.0

    def test_beta_in_moderate_range_adds_small_positive(self):
        gen = _make_generator()
        score_moderate_beta = gen._fundamental_score({"beta": 1.0}, [])
        score_no_beta = gen._fundamental_score({}, [])
        assert score_moderate_beta > score_no_beta

    def test_very_high_beta_penalised(self):
        gen = _make_generator()
        score_high_beta = gen._fundamental_score({"beta": 3.0}, [])
        score_moderate_beta = gen._fundamental_score({"beta": 1.0}, [])
        assert score_high_beta < score_moderate_beta

    def test_reasoning_appended_for_pe(self):
        gen = _make_generator()
        reasoning = []
        gen._fundamental_score({"pe_ratio": 15.0}, reasoning)
        assert any("P/E" in r for r in reasoning)

    def test_score_clipped_to_minus_one_plus_one(self):
        gen = _make_generator()
        # Combine extreme positive contributors
        score = gen._fundamental_score(
            {"pe_ratio": 15.0, "eps_growth": 10.0, "beta": 1.2}, []
        )
        assert -1.0 <= score <= 1.0
