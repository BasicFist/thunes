"""Tests for Risk Manager module."""

import json
from collections.abc import Generator
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from src.config import settings
from src.models.position import Position, PositionTracker
from src.risk.manager import AUDIT_TRAIL_PATH, RiskManager


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


class TestAuditTrail:
    """Tests for audit trail functionality."""

    @pytest.fixture(autouse=True)
    def cleanup_audit_trail(self) -> Generator[None, None, None]:
        """Remove audit trail file before/after tests."""
        if AUDIT_TRAIL_PATH.exists():
            AUDIT_TRAIL_PATH.unlink()
        yield
        if AUDIT_TRAIL_PATH.exists():
            AUDIT_TRAIL_PATH.unlink()

    def test_audit_trail_created_on_kill_switch(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test audit trail entry created when kill-switch activated."""
        # Mock Telegram to avoid actual network calls
        with patch("src.alerts.telegram.TelegramBot"):
            risk_manager.activate_kill_switch(reason="Test activation")

        # Verify audit trail file created
        assert AUDIT_TRAIL_PATH.exists()

        # Read and verify audit entry
        with open(AUDIT_TRAIL_PATH) as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 1
        entry = entries[0]
        assert entry["event"] == "KILL_SWITCH_ACTIVATED"
        assert entry["reason"] == "Test activation"
        assert "timestamp" in entry
        assert "daily_pnl" in entry
        assert "circuit_breaker_status" in entry

    def test_audit_trail_logs_trade_rejections(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test audit trail logs rejected trades."""
        # Activate kill-switch to trigger rejection
        with patch("src.alerts.telegram.TelegramBot"):
            risk_manager.activate_kill_switch()

        # Clear audit trail from kill-switch activation
        AUDIT_TRAIL_PATH.unlink()

        # Attempt trade (should be rejected)
        is_valid, msg = risk_manager.validate_trade(
            symbol="BTCUSDT", quote_qty=10.0, side="BUY", strategy_id="test_strategy"
        )

        assert is_valid is False

        # Verify rejection logged
        with open(AUDIT_TRAIL_PATH) as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 1
        entry = entries[0]
        assert entry["event"] == "TRADE_REJECTED"
        assert entry["reason"] == "kill_switch_active"
        assert entry["symbol"] == "BTCUSDT"
        assert entry["strategy_id"] == "test_strategy"

    def test_audit_trail_logs_trade_approvals(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test audit trail logs approved trades."""
        is_valid, msg = risk_manager.validate_trade(
            symbol="BTCUSDT", quote_qty=4.0, side="BUY", strategy_id="rsi_strategy"
        )

        assert is_valid is True

        # Verify approval logged
        with open(AUDIT_TRAIL_PATH) as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 1
        entry = entries[0]
        assert entry["event"] == "TRADE_APPROVED"
        assert entry["symbol"] == "BTCUSDT"
        assert entry["side"] == "BUY"
        assert entry["quote_qty"] == 4.0
        assert entry["strategy_id"] == "rsi_strategy"

    def test_audit_trail_logs_kill_switch_deactivation(self, risk_manager: RiskManager) -> None:
        """Test audit trail logs kill-switch deactivation."""
        # Activate then deactivate
        with patch("src.alerts.telegram.TelegramBot"):
            risk_manager.activate_kill_switch()
        risk_manager.deactivate_kill_switch(reason="Manual override")

        # Read all entries
        with open(AUDIT_TRAIL_PATH) as f:
            entries = [json.loads(line) for line in f]

        # Should have 2 entries: activation + deactivation
        assert len(entries) == 2
        assert entries[0]["event"] == "KILL_SWITCH_ACTIVATED"
        assert entries[1]["event"] == "KILL_SWITCH_DEACTIVATED"
        assert entries[1]["reason"] == "Manual override"

    def test_audit_trail_jsonl_format(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test audit trail uses JSONL format (one JSON per line)."""
        # Create multiple events
        risk_manager.validate_trade("BTCUSDT", 4.0, "BUY", "strategy1")
        risk_manager.validate_trade("ETHUSDT", 3.0, "BUY", "strategy2")

        # Verify each line is valid JSON
        with open(AUDIT_TRAIL_PATH) as f:
            lines = f.readlines()

        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line.strip())
            assert "event" in entry
            assert "timestamp" in entry


class TestTelegramIntegration:
    """Tests for Telegram alert integration."""

    @pytest.fixture(autouse=True)
    def cleanup_audit_trail(self) -> Generator[None, None, None]:
        """Remove audit trail file before/after tests."""
        if AUDIT_TRAIL_PATH.exists():
            AUDIT_TRAIL_PATH.unlink()
        yield
        if AUDIT_TRAIL_PATH.exists():
            AUDIT_TRAIL_PATH.unlink()

    @patch("src.alerts.telegram.TelegramBot")
    def test_kill_switch_sends_telegram_alert(
        self, mock_telegram_class: Mock, risk_manager: RiskManager
    ) -> None:
        """Test kill-switch activation sends Telegram alert."""
        mock_telegram_instance = Mock()
        mock_telegram_instance.send_kill_switch_alert = Mock()
        mock_telegram_class.return_value = mock_telegram_instance

        risk_manager.activate_kill_switch(reason="Test alert")

        # Verify Telegram bot was instantiated
        mock_telegram_class.assert_called_once()

    @patch("src.alerts.telegram.TelegramBot")
    def test_kill_switch_handles_telegram_failure_gracefully(
        self, mock_telegram_class: Mock, risk_manager: RiskManager
    ) -> None:
        """Test kill-switch activation continues even if Telegram fails."""
        # Make Telegram raise an exception
        mock_telegram_class.side_effect = Exception("Telegram API error")

        # Should not raise - kill-switch should still activate
        risk_manager.activate_kill_switch()

        assert risk_manager.kill_switch_active is True

        # Audit trail should still be written
        assert AUDIT_TRAIL_PATH.exists()


class TestValidateTradeStrategyId:
    """Tests for strategy_id parameter in validate_trade."""

    @pytest.fixture(autouse=True)
    def cleanup_audit_trail(self) -> Generator[None, None, None]:
        """Remove audit trail file before/after tests."""
        if AUDIT_TRAIL_PATH.exists():
            AUDIT_TRAIL_PATH.unlink()
        yield
        if AUDIT_TRAIL_PATH.exists():
            AUDIT_TRAIL_PATH.unlink()

    def test_strategy_id_included_in_audit_log(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test strategy_id is captured in audit log."""
        risk_manager.validate_trade(
            symbol="BTCUSDT", quote_qty=4.0, side="BUY", strategy_id="rsi_conservative"
        )

        with open(AUDIT_TRAIL_PATH) as f:
            entry = json.loads(f.readline())

        assert entry["strategy_id"] == "rsi_conservative"

    def test_default_strategy_id(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test default strategy_id when not provided."""
        risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")

        with open(AUDIT_TRAIL_PATH) as f:
            entry = json.loads(f.readline())

        assert entry["strategy_id"] == "unknown"
