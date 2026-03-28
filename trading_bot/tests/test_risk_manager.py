"""
tests/test_risk_manager.py
--------------------------
Unit tests for risk/risk_manager.py: RiskManager and SizingResult.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from risk.risk_manager import RiskManager, SizingResult


# ---------------------------------------------------------------------------
# Mock Settings
# ---------------------------------------------------------------------------

class MockSettings:
    MAX_POSITION_SIZE = 0.05    # 5% of portfolio per position
    MAX_PORTFOLIO_HEAT = 0.20   # 20% total heat
    STOP_LOSS_PCT = 0.05        # 5%
    TAKE_PROFIT_PCT = 0.15      # 15%
    MAX_DAILY_DRAWDOWN = 0.03   # 3%
    MAX_SHORT_POSITIONS = 5
    RISK_PER_TRADE = 0.01       # 1%


def _make_manager() -> RiskManager:
    rm = RiskManager.__new__(RiskManager)
    rm.cfg = MockSettings()
    return rm


# ---------------------------------------------------------------------------
# calculate_position_size
# ---------------------------------------------------------------------------

class TestCalculatePositionSize:
    def test_returns_sizing_result(self):
        rm = _make_manager()
        result = rm.calculate_position_size("AAPL", 150.0, 100_000.0, 2.0, "long", 0.5)
        assert isinstance(result, SizingResult)

    def test_shares_positive(self):
        rm = _make_manager()
        result = rm.calculate_position_size("AAPL", 150.0, 100_000.0, 2.0, "long", 0.5)
        assert result.shares > 0

    def test_respects_max_position_size_cap(self):
        """shares * price must not exceed portfolio_value * MAX_POSITION_SIZE."""
        rm = _make_manager()
        price = 150.0
        portfolio = 100_000.0
        result = rm.calculate_position_size("AAPL", price, portfolio, 2.0, "long", 1.0)
        assert result.shares * price <= portfolio * MockSettings.MAX_POSITION_SIZE + 1e-6

    def test_stop_price_below_entry_for_long(self):
        rm = _make_manager()
        price = 100.0
        result = rm.calculate_position_size("AAPL", price, 100_000.0, 2.0, "long", 0.5)
        assert result.stop_price < price

    def test_stop_price_above_entry_for_short(self):
        rm = _make_manager()
        price = 100.0
        result = rm.calculate_position_size("AAPL", price, 100_000.0, 2.0, "short", 0.5)
        assert result.stop_price > price

    def test_take_profit_above_entry_for_long(self):
        rm = _make_manager()
        price = 100.0
        result = rm.calculate_position_size("AAPL", price, 100_000.0, 2.0, "long", 0.5)
        assert result.take_profit_price > price

    def test_take_profit_below_entry_for_short(self):
        rm = _make_manager()
        price = 100.0
        result = rm.calculate_position_size("AAPL", price, 100_000.0, 2.0, "short", 0.5)
        assert result.take_profit_price < price

    def test_higher_confidence_gives_more_shares(self):
        """confidence=1.0 should produce more (or equal) shares than confidence=0.5."""
        rm = _make_manager()
        result_high = rm.calculate_position_size("AAPL", 100.0, 100_000.0, 1.0, "long", 1.0)
        result_low  = rm.calculate_position_size("AAPL", 100.0, 100_000.0, 1.0, "long", 0.5)
        assert result_high.shares >= result_low.shares

    def test_dollar_risk_is_positive(self):
        rm = _make_manager()
        result = rm.calculate_position_size("AAPL", 100.0, 100_000.0, 2.0, "long", 0.5)
        assert result.dollar_risk > 0

    def test_max_loss_equals_dollar_risk(self):
        rm = _make_manager()
        result = rm.calculate_position_size("AAPL", 100.0, 100_000.0, 2.0, "long", 0.5)
        assert result.max_loss == result.dollar_risk

    def test_at_least_one_share_returned(self):
        """Even with tiny portfolio or very expensive stock, min 1 share."""
        rm = _make_manager()
        result = rm.calculate_position_size("BRK-B", 400.0, 500.0, 1.0, "long", 0.1)
        assert result.shares >= 1


# ---------------------------------------------------------------------------
# check_portfolio_heat
# ---------------------------------------------------------------------------

class TestCheckPortfolioHeat:
    def test_returns_true_when_heat_within_limit(self):
        rm = _make_manager()
        positions = [{"unrealized_pl": 100.0}, {"unrealized_pl": -50.0}]
        result = rm.check_portfolio_heat(positions, 100_000.0, 500.0)
        assert result is True

    def test_returns_false_when_heat_would_exceed_limit(self):
        rm = _make_manager()
        # Existing heat: 18 000 / 100 000 = 18%, proposed = 3000 / 100000 = 3%
        # Total 21% > MAX_PORTFOLIO_HEAT (20%)
        positions = [{"unrealized_pl": -18_000.0}]
        result = rm.check_portfolio_heat(positions, 100_000.0, 3_000.0)
        assert result is False

    def test_empty_positions_heat_depends_on_proposed(self):
        rm = _make_manager()
        # Proposed risk = 25 000 on 100 000 portfolio = 25% > 20%
        result = rm.check_portfolio_heat([], 100_000.0, 25_000.0)
        assert result is False

    def test_zero_proposed_always_within_limit(self):
        rm = _make_manager()
        result = rm.check_portfolio_heat([], 100_000.0, 0.0)
        assert result is True


# ---------------------------------------------------------------------------
# check_short_capacity
# ---------------------------------------------------------------------------

class TestCheckShortCapacity:
    def test_returns_true_when_few_shorts(self):
        rm = _make_manager()
        positions = [{"qty": -10}, {"qty": 50}, {"qty": -5}]  # 2 shorts
        assert rm.check_short_capacity(positions) is True

    def test_returns_false_when_at_max_short_positions(self):
        rm = _make_manager()
        # MAX_SHORT_POSITIONS = 5; create exactly 5 short positions
        positions = [{"qty": -1} for _ in range(5)]
        assert rm.check_short_capacity(positions) is False

    def test_returns_false_when_above_max_short_positions(self):
        rm = _make_manager()
        positions = [{"qty": -1} for _ in range(7)]
        assert rm.check_short_capacity(positions) is False

    def test_no_shorts_returns_true(self):
        rm = _make_manager()
        positions = [{"qty": 10}, {"qty": 20}]
        assert rm.check_short_capacity(positions) is True

    def test_empty_positions_returns_true(self):
        rm = _make_manager()
        assert rm.check_short_capacity([]) is True


# ---------------------------------------------------------------------------
# check_daily_drawdown
# ---------------------------------------------------------------------------

class TestCheckDailyDrawdown:
    def test_no_halt_when_drawdown_small(self):
        """Daily loss of 1% should not trigger the circuit breaker (limit is 3%)."""
        rm = _make_manager()
        daily_pnl = -1_000.0  # -1% of 100k
        result = rm.check_daily_drawdown(daily_pnl, 100_000.0)
        assert result is False

    def test_halt_when_drawdown_at_limit(self):
        """Daily loss of exactly 3% should trigger halt."""
        rm = _make_manager()
        daily_pnl = -3_000.0  # exactly 3%
        result = rm.check_daily_drawdown(daily_pnl, 100_000.0)
        assert result is True

    def test_halt_when_drawdown_exceeds_limit(self):
        rm = _make_manager()
        daily_pnl = -5_000.0  # 5% > 3%
        result = rm.check_daily_drawdown(daily_pnl, 100_000.0)
        assert result is True

    def test_positive_pnl_never_halts(self):
        rm = _make_manager()
        result = rm.check_daily_drawdown(5_000.0, 100_000.0)
        assert result is False

    def test_zero_pnl_does_not_halt(self):
        rm = _make_manager()
        result = rm.check_daily_drawdown(0.0, 100_000.0)
        assert result is False


# ---------------------------------------------------------------------------
# get_trailing_stop
# ---------------------------------------------------------------------------

class TestGetTrailingStop:
    def test_long_trailing_stop_increases_as_price_rises(self):
        """For a long position, the trailing stop should move up when price rises."""
        rm = _make_manager()
        entry = 100.0
        atr = 2.0
        stop_when_price_110 = rm.get_trailing_stop("AAPL", "long", entry, 110.0, atr)
        stop_when_price_120 = rm.get_trailing_stop("AAPL", "long", entry, 120.0, atr)
        assert stop_when_price_120 > stop_when_price_110

    def test_long_initial_stop_below_entry(self):
        rm = _make_manager()
        stop = rm.get_trailing_stop("AAPL", "long", 100.0, 100.0, 2.0)
        assert stop < 100.0

    def test_short_trailing_stop_decreases_as_price_falls(self):
        """For a short position, the trailing stop should move down when price falls."""
        rm = _make_manager()
        entry = 100.0
        atr = 2.0
        stop_when_price_90 = rm.get_trailing_stop("AAPL", "short", entry, 90.0, atr)
        stop_when_price_80 = rm.get_trailing_stop("AAPL", "short", entry, 80.0, atr)
        assert stop_when_price_80 < stop_when_price_90

    def test_short_initial_stop_above_entry(self):
        rm = _make_manager()
        stop = rm.get_trailing_stop("AAPL", "short", 100.0, 100.0, 2.0)
        assert stop > 100.0


# ---------------------------------------------------------------------------
# should_force_exit
# ---------------------------------------------------------------------------

class TestShouldForceExit:
    def test_returns_tuple(self):
        rm = _make_manager()
        result = rm.should_force_exit("AAPL", "long", 100.0, 95.0)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_no_exit_when_loss_below_threshold(self):
        """Loss < 1.5 * STOP_LOSS_PCT (< 7.5%) should not force exit."""
        rm = _make_manager()
        # Loss of 2%: entry=100, current=98 → loss_pct=0.02 < 0.075
        should_exit, reason = rm.should_force_exit("AAPL", "long", 100.0, 98.0)
        assert should_exit is False
        assert reason == ""

    def test_force_exit_when_loss_exceeds_threshold(self):
        """Loss >= 1.5 * STOP_LOSS_PCT (>= 7.5%) should force exit."""
        rm = _make_manager()
        # STOP_LOSS_PCT=0.05, so threshold = 0.075 = 7.5%
        # Entry=100, current=92 → loss_pct=0.08 > 0.075
        should_exit, reason = rm.should_force_exit("AAPL", "long", 100.0, 92.0)
        assert should_exit is True
        assert len(reason) > 0

    def test_force_exit_reason_contains_symbol(self):
        rm = _make_manager()
        should_exit, reason = rm.should_force_exit("TSLA", "long", 100.0, 90.0)
        assert should_exit is True
        assert "TSLA" in reason

    def test_force_exit_short_when_loss_exceeds_threshold(self):
        """Short position: if price rises > 7.5% above entry, force exit."""
        rm = _make_manager()
        # Entry=100, current=110 → loss_pct=0.10 > 0.075
        should_exit, reason = rm.should_force_exit("AAPL", "short", 100.0, 110.0)
        assert should_exit is True
        assert len(reason) > 0

    def test_no_force_exit_short_small_loss(self):
        rm = _make_manager()
        # Entry=100, current=103 → loss_pct=0.03 < 0.075
        should_exit, reason = rm.should_force_exit("AAPL", "short", 100.0, 103.0)
        assert should_exit is False
