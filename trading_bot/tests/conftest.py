"""Shared pytest fixtures."""
import pytest
import pandas as pd
import numpy as np
import sys, os

# Put the trading_bot package on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def sample_ohlcv():
    """60-day OHLCV DataFrame."""
    np.random.seed(0)
    dates = pd.date_range('2024-01-01', periods=60, freq='D')
    close = 150.0 + np.cumsum(np.random.randn(60) * 0.5)
    df = pd.DataFrame({
        'open':   close * 0.999,
        'high':   close * 1.005,
        'low':    close * 0.995,
        'close':  close,
        'volume': np.random.randint(500_000, 5_000_000, 60).astype(float),
    }, index=dates)
    return df


@pytest.fixture
def mock_positions():
    """A realistic set of open positions."""
    return {
        'AAPL': {
            'symbol': 'AAPL', 'qty': 10.0, 'side': 'long',
            'avg_entry_price': 180.0, 'current_price': 185.0,
            'market_value': 1850.0, 'unrealized_pl': 50.0, 'unrealized_plpc': 0.0278,
            'cost_basis': 1800.0,
        },
        'MSFT': {
            'symbol': 'MSFT', 'qty': -5.0, 'side': 'short',
            'avg_entry_price': 420.0, 'current_price': 415.0,
            'market_value': -2075.0, 'unrealized_pl': 25.0, 'unrealized_plpc': 0.0119,
            'cost_basis': 2100.0,
        },
    }


@pytest.fixture
def mock_account():
    return {
        'id': 'test-account-id',
        'equity': 105_000.0,
        'portfolio_value': 105_000.0,
        'cash': 50_000.0,
        'buying_power': 100_000.0,
        'daytrade_count': 0,
        'pattern_day_trader': False,
        'shorting_enabled': True,
        'status': 'ACTIVE',
    }
