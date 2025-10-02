"""Tests for Pydantic validation models."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models.schemas import (
    BalanceModel,
    MarketDataSnapshot,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionModel,
    TradeModel,
)


class TestOrderRequest:
    """Tests for OrderRequest model."""

    def test_valid_market_buy_with_quote_qty(self) -> None:
        """Test valid MARKET BUY order with quote quantity."""
        order = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_quantity=Decimal("100.00"),
        )

        assert order.symbol == "BTCUSDT"
        assert order.side == OrderSide.BUY
        assert order.quote_quantity == Decimal("100.00")

    def test_valid_limit_buy(self) -> None:
        """Test valid LIMIT order."""
        order = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.5"),
            price=Decimal("3000.00"),
        )

        assert order.quantity == Decimal("1.5")
        assert order.price == Decimal("3000.00")

    def test_symbol_must_be_uppercase(self) -> None:
        """Test that symbol must be uppercase."""
        with pytest.raises(ValidationError, match="Symbol must be uppercase"):
            OrderRequest(
                symbol="btcusdt",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quote_quantity=Decimal("100"),
            )

    def test_symbol_minimum_length(self) -> None:
        """Test symbol minimum length validation."""
        with pytest.raises(ValidationError, match="Symbol too short"):
            OrderRequest(
                symbol="BTC",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quote_quantity=Decimal("100"),
            )

    def test_quantity_must_be_positive(self) -> None:
        """Test that quantity must be positive."""
        with pytest.raises(ValidationError):
            OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("-1.0"),
            )

    def test_market_order_requires_quantity_or_quote_quantity(self) -> None:
        """Test MARKET order validation."""
        with pytest.raises(ValidationError, match="MARKET order requires"):
            OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
            )

    def test_limit_order_requires_price(self) -> None:
        """Test LIMIT order requires price."""
        with pytest.raises(ValidationError, match="LIMIT order requires price"):
            OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1.0"),
            )


class TestOrderResponse:
    """Tests for OrderResponse model."""

    def test_valid_order_response(self) -> None:
        """Test valid order response."""
        response = OrderResponse(
            order_id=123456,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            quantity=Decimal("0.1"),
            executed_qty=Decimal("0.1"),
            cumulative_quote_qty=Decimal("5000.00"),
            transact_time=datetime.utcnow(),
        )

        assert response.order_id == 123456
        assert response.is_filled is True
        assert response.fill_ratio == Decimal("1.0")

    def test_average_fill_price(self) -> None:
        """Test average fill price calculation."""
        response = OrderResponse(
            order_id=123456,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            quantity=Decimal("0.1"),
            executed_qty=Decimal("0.1"),
            cumulative_quote_qty=Decimal("5000.00"),
            transact_time=datetime.utcnow(),
        )

        assert response.average_fill_price == Decimal("50000.00")

    def test_partial_fill(self) -> None:
        """Test partially filled order."""
        response = OrderResponse(
            order_id=123456,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            status=OrderStatus.PARTIALLY_FILLED,
            quantity=Decimal("1.0"),
            executed_qty=Decimal("0.5"),
            cumulative_quote_qty=Decimal("25000.00"),
            transact_time=datetime.utcnow(),
        )

        assert response.is_filled is False
        assert response.fill_ratio == Decimal("0.5")


class TestPositionModel:
    """Tests for PositionModel."""

    def test_valid_open_position(self) -> None:
        """Test valid open position."""
        position = PositionModel(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            entry_time=datetime.utcnow(),
            status="OPEN",
        )

        assert position.is_open is True
        assert position.is_closed is False

    def test_valid_closed_position(self) -> None:
        """Test valid closed position."""
        position = PositionModel(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            entry_time=datetime.utcnow(),
            exit_price=Decimal("52000.00"),
            exit_time=datetime.utcnow(),
            pnl=Decimal("200.00"),
            status="CLOSED",
        )

        assert position.is_open is False
        assert position.is_closed is True

    def test_invalid_status(self) -> None:
        """Test invalid status value."""
        with pytest.raises(ValidationError, match="Status must be OPEN or CLOSED"):
            PositionModel(
                symbol="BTCUSDT",
                quantity=Decimal("0.1"),
                entry_price=Decimal("50000.00"),
                entry_time=datetime.utcnow(),
                status="PENDING",
            )

    def test_calculate_unrealized_pnl(self) -> None:
        """Test unrealized PnL calculation."""
        position = PositionModel(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            entry_time=datetime.utcnow(),
            status="OPEN",
        )

        pnl = position.calculate_unrealized_pnl(Decimal("55000.00"))
        assert pnl == Decimal("500.00")


class TestTradeModel:
    """Tests for TradeModel."""

    def test_valid_trade(self) -> None:
        """Test valid trade model."""
        entry_time = datetime(2024, 1, 1, 10, 0, 0)
        exit_time = datetime(2024, 1, 1, 12, 0, 0)

        trade = TradeModel(
            symbol="BTCUSDT",
            entry_order_id=123,
            exit_order_id=456,
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            exit_price=Decimal("52000.00"),
            entry_time=entry_time,
            exit_time=exit_time,
            pnl=Decimal("200.00"),
            pnl_percent=Decimal("4.00"),
            fees=Decimal("10.00"),
        )

        assert trade.is_profitable is True
        assert trade.net_pnl == Decimal("190.00")  # 200 - 10 fees
        assert trade.duration_hours == 2.0

    def test_roi_calculation(self) -> None:
        """Test ROI calculation."""
        trade = TradeModel(
            symbol="BTCUSDT",
            entry_order_id=123,
            exit_order_id=456,
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            exit_price=Decimal("52000.00"),
            entry_time=datetime.utcnow(),
            exit_time=datetime.utcnow(),
            pnl=Decimal("200.00"),
            pnl_percent=Decimal("4.00"),
            fees=Decimal("10.00"),
        )

        # Cost basis = 50000 * 0.1 = 5000
        # Net PnL = 200 - 10 = 190
        # ROI = (190 / 5000) * 100 = 3.8%
        assert trade.return_on_investment == Decimal("3.8")


class TestBalanceModel:
    """Tests for BalanceModel."""

    def test_valid_balance(self) -> None:
        """Test valid balance model."""
        balance = BalanceModel(
            asset="USDT",
            free=Decimal("1000.00"),
            locked=Decimal("250.00"),
        )

        assert balance.total == Decimal("1250.00")

    def test_zero_balance(self) -> None:
        """Test zero balance."""
        balance = BalanceModel(
            asset="BTC",
            free=Decimal("0.0"),
            locked=Decimal("0.0"),
        )

        assert balance.total == Decimal("0.0")


class TestMarketDataSnapshot:
    """Tests for MarketDataSnapshot."""

    def test_valid_snapshot(self) -> None:
        """Test valid market data snapshot."""
        snapshot = MarketDataSnapshot(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            bid_price=Decimal("50000.00"),
            ask_price=Decimal("50010.00"),
            last_price=Decimal("50005.00"),
            volume_24h=Decimal("1000.50"),
        )

        assert snapshot.spread == Decimal("10.00")
        assert snapshot.mid_price == Decimal("50005.00")

    def test_spread_bps_calculation(self) -> None:
        """Test spread in basis points."""
        snapshot = MarketDataSnapshot(
            symbol="BTCUSDT",
            timestamp=datetime.utcnow(),
            bid_price=Decimal("50000.00"),
            ask_price=Decimal("50010.00"),
            last_price=Decimal("50005.00"),
            volume_24h=Decimal("1000.00"),
        )

        # Spread = 10
        # Spread BPS = (10 / 50000) * 10000 = 2 bps
        assert snapshot.spread_bps == Decimal("2.00")
