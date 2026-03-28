"""
tests/test_portfolio_manager.py
--------------------------------
Unit tests for portfolio/portfolio_manager.py: PortfolioManager.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
import pandas as pd

from portfolio.portfolio_manager import PortfolioManager


# ---------------------------------------------------------------------------
# Mock broker
# ---------------------------------------------------------------------------

class MockBroker:
    """Simple broker stub that returns fixed account and position data."""

    def __init__(self, portfolio_value=100_000.0, cash=50_000.0, positions=None):
        self._account = {
            "equity":          portfolio_value,
            "portfolio_value": portfolio_value,
            "cash":            cash,
            "buying_power":    cash * 2,
        }
        self._positions = positions if positions is not None else []

    def get_account(self) -> dict:
        return dict(self._account)

    def get_positions(self) -> list:
        return list(self._positions)


# ---------------------------------------------------------------------------
# Sample positions
# ---------------------------------------------------------------------------

SAMPLE_POSITIONS = [
    {
        "symbol": "AAPL",
        "side": "long",
        "qty": 10,
        "avg_entry_price": 150.0,
        "current_price": 155.0,
        "market_value": 1_550.0,
        "unrealized_pl": 50.0,
        "unrealized_plpc": 0.033,
    },
    {
        "symbol": "MSFT",
        "side": "long",
        "qty": 5,
        "avg_entry_price": 300.0,
        "current_price": 310.0,
        "market_value": 1_550.0,
        "unrealized_pl": 50.0,
        "unrealized_plpc": 0.033,
    },
    {
        "symbol": "TSLA",
        "side": "short",
        "qty": -8,
        "avg_entry_price": 200.0,
        "current_price": 190.0,
        "market_value": -1_520.0,
        "unrealized_pl": 80.0,
        "unrealized_plpc": 0.05,
    },
]


def _make_pm_with_positions(positions=None) -> PortfolioManager:
    """Create a PortfolioManager and refresh it with the given positions."""
    if positions is None:
        positions = SAMPLE_POSITIONS
    pm = PortfolioManager()
    broker = MockBroker(portfolio_value=100_000.0, cash=50_000.0, positions=positions)
    pm.refresh(broker)
    return pm


# ---------------------------------------------------------------------------
# refresh / get_portfolio_value
# ---------------------------------------------------------------------------

class TestRefreshAndPortfolioValue:
    def test_portfolio_value_after_refresh(self):
        pm = PortfolioManager()
        broker = MockBroker(portfolio_value=123_456.0)
        pm.refresh(broker)
        assert pm.get_portfolio_value() == 123_456.0

    def test_cash_after_refresh(self):
        pm = PortfolioManager()
        broker = MockBroker(portfolio_value=100_000.0, cash=40_000.0)
        pm.refresh(broker)
        assert pm.get_cash() == 40_000.0

    def test_buying_power_after_refresh(self):
        pm = PortfolioManager()
        broker = MockBroker(portfolio_value=100_000.0, cash=40_000.0)
        pm.refresh(broker)
        assert pm.get_buying_power() == 80_000.0

    def test_equity_after_refresh(self):
        pm = PortfolioManager()
        broker = MockBroker(portfolio_value=75_000.0)
        pm.refresh(broker)
        assert pm.get_equity() == 75_000.0

    def test_last_refresh_is_set(self):
        pm = PortfolioManager()
        broker = MockBroker()
        pm.refresh(broker)
        assert pm._last_refresh is not None


# ---------------------------------------------------------------------------
# Position queries
# ---------------------------------------------------------------------------

class TestIsLong:
    def test_is_long_true_for_positive_qty(self):
        pm = _make_pm_with_positions()
        assert pm.is_long("AAPL") is True

    def test_is_long_false_for_short_position(self):
        pm = _make_pm_with_positions()
        assert pm.is_long("TSLA") is False

    def test_is_long_false_for_unknown_symbol(self):
        pm = _make_pm_with_positions()
        assert pm.is_long("GOOG") is False


class TestIsShort:
    def test_is_short_true_for_negative_qty(self):
        pm = _make_pm_with_positions()
        assert pm.is_short("TSLA") is True

    def test_is_short_false_for_long_position(self):
        pm = _make_pm_with_positions()
        assert pm.is_short("AAPL") is False

    def test_is_short_false_for_unknown_symbol(self):
        pm = _make_pm_with_positions()
        assert pm.is_short("GOOG") is False


class TestHasPosition:
    def test_has_position_true_for_known_symbol(self):
        pm = _make_pm_with_positions()
        assert pm.has_position("AAPL") is True

    def test_has_position_false_for_unknown_symbol(self):
        pm = _make_pm_with_positions()
        assert pm.has_position("UNKNOWN") is False

    def test_has_position_false_for_empty_portfolio(self):
        pm = _make_pm_with_positions(positions=[])
        assert pm.has_position("AAPL") is False


# ---------------------------------------------------------------------------
# count_long_positions / count_short_positions
# ---------------------------------------------------------------------------

class TestCountPositions:
    def test_count_long_positions(self):
        pm = _make_pm_with_positions()
        # AAPL (long qty=10) and MSFT (long qty=5)
        assert pm.count_long_positions() == 2

    def test_count_short_positions(self):
        pm = _make_pm_with_positions()
        # TSLA (short qty=-8)
        assert pm.count_short_positions() == 1

    def test_count_long_no_positions(self):
        pm = _make_pm_with_positions(positions=[])
        assert pm.count_long_positions() == 0

    def test_count_short_no_positions(self):
        pm = _make_pm_with_positions(positions=[])
        assert pm.count_short_positions() == 0

    def test_count_with_only_longs(self):
        positions = [
            {**SAMPLE_POSITIONS[0]},
            {**SAMPLE_POSITIONS[1]},
        ]
        pm = _make_pm_with_positions(positions=positions)
        assert pm.count_long_positions() == 2
        assert pm.count_short_positions() == 0


# ---------------------------------------------------------------------------
# get_daily_pnl
# ---------------------------------------------------------------------------

class TestGetDailyPnl:
    def test_daily_pnl_equals_portfolio_value_minus_day_start(self):
        pm = PortfolioManager()
        broker = MockBroker(portfolio_value=100_000.0)
        pm.refresh(broker)
        # Simulate a day's gain by changing portfolio value
        broker._account["portfolio_value"] = 102_000.0
        broker._account["equity"] = 102_000.0
        pm._portfolio_value = 102_000.0
        assert pm.get_daily_pnl() == pytest.approx(2_000.0, abs=1e-6)

    def test_daily_pnl_zero_on_first_refresh(self):
        """On the first refresh, day_start_value == portfolio_value → pnl == 0."""
        pm = PortfolioManager()
        broker = MockBroker(portfolio_value=100_000.0)
        pm.refresh(broker)
        assert pm.get_daily_pnl() == pytest.approx(0.0, abs=1e-6)

    def test_negative_daily_pnl_on_loss(self):
        pm = PortfolioManager()
        broker = MockBroker(portfolio_value=100_000.0)
        pm.refresh(broker)
        pm._portfolio_value = 97_000.0
        assert pm.get_daily_pnl() == pytest.approx(-3_000.0, abs=1e-6)


# ---------------------------------------------------------------------------
# get_exposure
# ---------------------------------------------------------------------------

class TestGetExposure:
    def test_exposure_keys_present(self):
        pm = _make_pm_with_positions()
        exp = pm.get_exposure()
        for key in ("long_exposure", "short_exposure", "net_exposure", "gross_exposure"):
            assert key in exp

    def test_net_exposure_formula(self):
        """net_exposure = (long_mv - short_mv) / portfolio_value."""
        pm = _make_pm_with_positions()
        exp = pm.get_exposure()
        # AAPL + MSFT long: 1550 + 1550 = 3100
        # TSLA short: abs(-1520) = 1520
        # net = (3100 - 1520) / 100000 = 0.0158
        expected_net = (3100.0 - 1520.0) / 100_000.0
        assert exp["net_exposure"] == pytest.approx(expected_net, abs=1e-6)

    def test_long_exposure_non_negative(self):
        pm = _make_pm_with_positions()
        exp = pm.get_exposure()
        assert exp["long_exposure"] >= 0.0

    def test_short_exposure_non_negative(self):
        pm = _make_pm_with_positions()
        exp = pm.get_exposure()
        assert exp["short_exposure"] >= 0.0

    def test_gross_exposure_is_long_plus_short(self):
        pm = _make_pm_with_positions()
        exp = pm.get_exposure()
        assert exp["gross_exposure"] == pytest.approx(
            exp["long_exposure"] + exp["short_exposure"], abs=1e-6
        )

    def test_exposure_all_long_portfolio(self):
        positions = [SAMPLE_POSITIONS[0], SAMPLE_POSITIONS[1]]
        pm = _make_pm_with_positions(positions=positions)
        exp = pm.get_exposure()
        assert exp["short_exposure"] == 0.0
        assert exp["net_exposure"] == exp["long_exposure"]


# ---------------------------------------------------------------------------
# positions_to_dataframe
# ---------------------------------------------------------------------------

class TestPositionsToDataframe:
    def test_returns_dataframe(self):
        pm = _make_pm_with_positions()
        df = pm.positions_to_dataframe()
        assert isinstance(df, pd.DataFrame)

    def test_expected_columns_present(self):
        pm = _make_pm_with_positions()
        df = pm.positions_to_dataframe()
        expected_cols = [
            "symbol", "side", "qty", "avg_entry_price",
            "current_price", "market_value", "unrealized_pl", "pnl_pct"
        ]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_row_count_matches_positions(self):
        pm = _make_pm_with_positions()
        df = pm.positions_to_dataframe()
        assert len(df) == len(SAMPLE_POSITIONS)

    def test_empty_positions_returns_empty_dataframe(self):
        pm = _make_pm_with_positions(positions=[])
        df = pm.positions_to_dataframe()
        assert df.empty

    def test_symbols_in_dataframe(self):
        pm = _make_pm_with_positions()
        df = pm.positions_to_dataframe()
        assert set(df["symbol"].tolist()) == {"AAPL", "MSFT", "TSLA"}


# ---------------------------------------------------------------------------
# get_performance_summary
# ---------------------------------------------------------------------------

class TestGetPerformanceSummary:
    def test_returns_dict(self):
        pm = _make_pm_with_positions()
        summary = pm.get_performance_summary()
        assert isinstance(summary, dict)

    def test_portfolio_value_in_summary(self):
        pm = _make_pm_with_positions()
        summary = pm.get_performance_summary()
        assert "portfolio_value" in summary
        assert summary["portfolio_value"] == 100_000.0

    def test_daily_pnl_in_summary(self):
        pm = _make_pm_with_positions()
        summary = pm.get_performance_summary()
        assert "daily_pnl" in summary

    def test_all_required_keys_present(self):
        pm = _make_pm_with_positions()
        summary = pm.get_performance_summary()
        required_keys = [
            "portfolio_value", "equity", "cash", "buying_power",
            "daily_pnl", "daily_pnl_pct", "total_unrealized_pnl",
            "long_positions", "short_positions",
            "net_exposure_pct", "gross_exposure_pct", "last_refresh",
        ]
        for key in required_keys:
            assert key in summary, f"Missing key: {key}"

    def test_long_positions_count_in_summary(self):
        pm = _make_pm_with_positions()
        summary = pm.get_performance_summary()
        assert summary["long_positions"] == 2

    def test_short_positions_count_in_summary(self):
        pm = _make_pm_with_positions()
        summary = pm.get_performance_summary()
        assert summary["short_positions"] == 1

    def test_total_unrealized_pnl(self):
        pm = _make_pm_with_positions()
        summary = pm.get_performance_summary()
        # AAPL: 50, MSFT: 50, TSLA: 80 → total = 180
        assert summary["total_unrealized_pnl"] == pytest.approx(180.0, abs=1e-6)
