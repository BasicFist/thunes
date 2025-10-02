"""Tests for exchange filters module."""

from decimal import Decimal
from unittest.mock import Mock, MagicMock

import pytest

from src.filters.exchange_filters import ExchangeFilters


@pytest.fixture
def mock_client() -> Mock:
    """Create a mock Binance client."""
    client = Mock()
    client.get_exchange_info.return_value = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {
                        "filterType": "PRICE_FILTER",
                        "tickSize": "0.01",
                    },
                    {
                        "filterType": "LOT_SIZE",
                        "stepSize": "0.00001",
                    },
                    {
                        "filterType": "NOTIONAL",
                        "minNotional": "10.0",
                    },
                ],
            }
        ]
    }
    return client


@pytest.fixture
def filters(mock_client: Mock) -> ExchangeFilters:
    """Create ExchangeFilters instance with mock client."""
    return ExchangeFilters(mock_client)


def test_get_tick_size(filters: ExchangeFilters) -> None:
    """Test tick size retrieval."""
    tick = filters.get_tick_size("BTCUSDT")
    assert tick == Decimal("0.01")


def test_get_step_size(filters: ExchangeFilters) -> None:
    """Test step size retrieval."""
    step = filters.get_step_size("BTCUSDT")
    assert step == Decimal("0.00001")


def test_get_min_notional(filters: ExchangeFilters) -> None:
    """Test minimum notional retrieval."""
    min_not = filters.get_min_notional("BTCUSDT")
    assert min_not == Decimal("10.0")


def test_round_price(filters: ExchangeFilters) -> None:
    """Test price rounding."""
    # Price 50000.567 should round to 50000.56 (tick=0.01)
    rounded = filters.round_price("BTCUSDT", 50000.567)
    assert rounded == Decimal("50000.56")


def test_round_quantity(filters: ExchangeFilters) -> None:
    """Test quantity rounding."""
    # Qty 0.123456 should round to 0.12345 (step=0.00001)
    rounded = filters.round_quantity("BTCUSDT", 0.123456)
    assert rounded == Decimal("0.12345")


def test_validate_order_success(filters: ExchangeFilters) -> None:
    """Test successful order validation."""
    is_valid, msg = filters.validate_order("BTCUSDT", quote_qty=15.0)
    assert is_valid is True
    assert "valid" in msg.lower()


def test_validate_order_below_min_notional(filters: ExchangeFilters) -> None:
    """Test order validation failure due to min notional."""
    is_valid, msg = filters.validate_order("BTCUSDT", quote_qty=5.0)
    assert is_valid is False
    assert "min notional" in msg.lower()
