"""Tests for Risk Manager module."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.config import settings
from src.models.position import Position, PositionTracker
from src.risk.manager import RiskManager


@pytest.fixture
def mock_position_tracker() -> Mock:
    """Create a mock PositionTracker."""
    tracker = Mock(spec=PositionTracker)
    tracker.get_all_open_positions.return_value = []
    tracker.has_open_position.return_value = False
    tracker.get_position_history.return_value = []
    return tracker


@pytest.fixture
def risk_manager(mock_position_tracker: Mock) -> RiskManager:
    """Create RiskManager with mock dependencies."""
    return RiskManager(position_tracker=mock_position_tracker)


def test_risk_manager_initialization(risk_manager: RiskManager) -> None:
    """Test Risk Manager initializes with correct settings."""
    assert risk_manager.max_loss_per_trade == Decimal(str(settings.max_loss_per_trade))
    assert risk_manager.max_daily_loss == Decimal(str(settings.max_daily_loss))
    assert risk_manager.max_positions == settings.max_positions
    assert risk_manager.kill_switch_active is False


def test_validate_trade_passes_normally(risk_manager: RiskManager) -> None:
    """Test trade validation passes under normal conditions."""
    is_valid, msg = risk_manager.validate_trade(
        symbol="BTCUSDT", quote_qty=4.0, side="BUY"  # Under MAX_LOSS_PER_TRADE=5.0
    )

    assert is_valid is True
    assert "passed" in msg.lower()


def test_validate_trade_rejects_when_kill_switch_active(risk_manager: RiskManager) -> None:
    """Test trade validation fails when kill-switch is active."""
    risk_manager.activate_kill_switch()

    is_valid, msg = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")

    assert is_valid is False
    assert "kill-switch" in msg.lower()


def test_validate_trade_rejects_excessive_quote_qty(risk_manager: RiskManager) -> None:
    """Test trade validation fails when quote quantity exceeds limit."""
    is_valid, msg = risk_manager.validate_trade(
        symbol="BTCUSDT", quote_qty=100.0, side="BUY"  # Exceeds default MAX_LOSS_PER_TRADE=5.0
    )

    assert is_valid is False
    assert "exceeds max loss per trade" in msg.lower()


def test_validate_trade_rejects_when_max_positions_reached(
    risk_manager: RiskManager, mock_position_tracker: Mock
) -> None:
    """Test trade validation fails when max positions limit reached."""
    # Mock 3 open positions (default MAX_POSITIONS=3)
    mock_position_tracker.get_all_open_positions.return_value = [Mock(), Mock(), Mock()]

    is_valid, msg = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")

    assert is_valid is False
    assert "max position limit" in msg.lower()


def test_validate_trade_rejects_duplicate_position(
    risk_manager: RiskManager, mock_position_tracker: Mock
) -> None:
    """Test trade validation fails when position already exists for symbol."""
    mock_position_tracker.has_open_position.return_value = True

    is_valid, msg = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")

    assert is_valid is False
    assert "already exists" in msg.lower()


def test_validate_trade_respects_cool_down(risk_manager: RiskManager) -> None:
    """Test trade validation fails during cool-down period."""
    # Record a loss to trigger cool-down
    risk_manager.record_loss()

    is_valid, msg = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")

    assert is_valid is False
    assert "cool-down" in msg.lower()


def test_validate_trade_allows_sell_during_cool_down(risk_manager: RiskManager) -> None:
    """Test SELL orders are allowed during cool-down."""
    risk_manager.record_loss()

    is_valid, msg = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="SELL")

    # SELL should be allowed even during cool-down
    assert is_valid is True


def test_get_daily_pnl_calculates_correctly(
    risk_manager: RiskManager, mock_position_tracker: Mock
) -> None:
    """Test daily PnL calculation from closed positions."""
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)

    # Mock positions: 2 today (one win, one loss), 1 yesterday
    mock_position_tracker.get_position_history.return_value = [
        Position(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            entry_time=today,
            order_id="1",
            exit_price=Decimal("51000"),
            exit_time=today,
            pnl=Decimal("100.0"),  # Win
            status="CLOSED",
        ),
        Position(
            symbol="ETHUSDT",
            quantity=Decimal("1.0"),
            entry_price=Decimal("3000"),
            entry_time=today,
            order_id="2",
            exit_price=Decimal("2950"),
            exit_time=today,
            pnl=Decimal("-50.0"),  # Loss
            status="CLOSED",
        ),
        Position(
            symbol="BNBUSDT",
            quantity=Decimal("1.0"),
            entry_price=Decimal("500"),
            entry_time=yesterday,
            order_id="3",
            exit_price=Decimal("550"),
            exit_time=yesterday,
            pnl=Decimal("50.0"),  # Yesterday - shouldn't count
            status="CLOSED",
        ),
    ]

    daily_pnl = risk_manager.get_daily_pnl()

    # Should only count today's trades: 100 - 50 = 50
    assert daily_pnl == Decimal("50.0")


def test_get_daily_pnl_triggers_kill_switch(
    risk_manager: RiskManager, mock_position_tracker: Mock
) -> None:
    """Test kill-switch activates when daily loss exceeds limit."""
    today = datetime.utcnow()

    # Mock large loss today
    mock_position_tracker.get_position_history.return_value = [
        Position(
            symbol="BTCUSDT",
            quantity=Decimal("1.0"),
            entry_price=Decimal("50000"),
            entry_time=today,
            order_id="1",
            exit_price=Decimal("49900"),
            exit_time=today,
            pnl=Decimal("-25.0"),  # Loss exceeds MAX_DAILY_LOSS=20.0
            status="CLOSED",
        ),
    ]

    # validate_trade should trigger kill-switch
    is_valid, msg = risk_manager.validate_trade("BTCUSDT", 10.0, "BUY")

    assert is_valid is False
    assert risk_manager.kill_switch_active is True
    assert "kill-switch" in msg.lower()


def test_activate_kill_switch(risk_manager: RiskManager) -> None:
    """Test kill-switch activation."""
    assert risk_manager.kill_switch_active is False

    risk_manager.activate_kill_switch()

    assert risk_manager.kill_switch_active is True


def test_deactivate_kill_switch(risk_manager: RiskManager) -> None:
    """Test kill-switch deactivation."""
    risk_manager.activate_kill_switch()
    assert risk_manager.kill_switch_active is True

    risk_manager.deactivate_kill_switch(reason="Test reset")

    assert risk_manager.kill_switch_active is False


def test_record_loss_starts_cool_down(risk_manager: RiskManager) -> None:
    """Test recording loss starts cool-down period."""
    assert risk_manager.last_loss_time is None

    risk_manager.record_loss()

    assert risk_manager.last_loss_time is not None
    assert isinstance(risk_manager.last_loss_time, datetime)


def test_record_win_clears_cool_down(risk_manager: RiskManager) -> None:
    """Test recording win clears cool-down."""
    risk_manager.record_loss()
    assert risk_manager.last_loss_time is not None

    risk_manager.record_win()

    assert risk_manager.last_loss_time is None


def test_get_risk_status(risk_manager: RiskManager, mock_position_tracker: Mock) -> None:
    """Test risk status reporting."""
    mock_position_tracker.get_all_open_positions.return_value = [Mock()]

    status = risk_manager.get_risk_status()

    assert "kill_switch_active" in status
    assert "daily_pnl" in status
    assert "open_positions" in status
    assert status["open_positions"] == 1
    assert status["max_positions"] == settings.max_positions


def test_reset_daily_state(risk_manager: RiskManager) -> None:
    """Test daily state reset."""
    risk_manager.record_loss()
    risk_manager._daily_loss_cache = (datetime.utcnow(), Decimal("10.0"))

    risk_manager.reset_daily_state()

    assert risk_manager.last_loss_time is None
    assert risk_manager._daily_loss_cache is None


def test_reset_daily_state_preserves_kill_switch(risk_manager: RiskManager) -> None:
    """Test daily reset does NOT deactivate kill-switch."""
    risk_manager.activate_kill_switch()

    risk_manager.reset_daily_state()

    # Kill-switch should still be active (requires manual deactivation)
    assert risk_manager.kill_switch_active is True
