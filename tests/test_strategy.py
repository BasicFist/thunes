"""Tests for trading strategy."""

import pandas as pd
import pytest

from src.backtest.strategy import SMAStrategy


@pytest.fixture
def sample_data() -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
    df = pd.DataFrame(
        {
            "open": [50000 + i * 10 for i in range(100)],
            "high": [50100 + i * 10 for i in range(100)],
            "low": [49900 + i * 10 for i in range(100)],
            "close": [50000 + i * 10 for i in range(100)],
            "volume": [100 for _ in range(100)],
        },
        index=dates,
    )
    return df


def test_strategy_initialization() -> None:
    """Test strategy initialization."""
    strategy = SMAStrategy(fast_window=10, slow_window=30)
    assert strategy.fast_window == 10
    assert strategy.slow_window == 30


def test_generate_signals(sample_data: pd.DataFrame) -> None:
    """Test signal generation."""
    strategy = SMAStrategy(fast_window=10, slow_window=20)
    entries, exits = strategy.generate_signals(sample_data)

    assert len(entries) == len(sample_data)
    assert len(exits) == len(sample_data)
    assert entries.dtype == bool
    assert exits.dtype == bool


def test_backtest_runs(sample_data: pd.DataFrame) -> None:
    """Test that backtest completes without errors."""
    strategy = SMAStrategy(fast_window=10, slow_window=20)
    portfolio = strategy.backtest(sample_data, initial_capital=10000.0)

    assert portfolio is not None
    stats = strategy.get_stats(portfolio)
    assert "Total Return [%]" in stats
