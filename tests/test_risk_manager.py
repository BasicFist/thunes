"""Tests for Risk Manager module."""

import json
from collections.abc import Generator
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.config import settings
from src.models.position import Position, PositionTracker
from src.risk.manager import AUDIT_TRAIL_PATH, RiskManager


@pytest.fixture
def isolated_audit_trail(tmp_path: Path, monkeypatch):
    """
    Create isolated audit trail for each test.

    Prevents race conditions in parallel test execution by giving each test
    its own temporary audit_trail.jsonl file. Uses pytest's tmp_path fixture
    for automatic cleanup.

    Args:
        tmp_path: Pytest's temporary directory fixture
        monkeypatch: Pytest's monkeypatch fixture for patching

    Yields:
        Path: Isolated audit trail file path
    """
    audit_file = tmp_path / "audit_trail.jsonl"
    # Patch the module-level constant in src.risk.manager
    monkeypatch.setattr("src.risk.manager.AUDIT_TRAIL_PATH", audit_file)
    yield audit_file
    # Cleanup is automatic via tmp_path


@pytest.fixture
def mock_position_tracker() -> Mock:
    """Create a mock PositionTracker."""
    tracker = Mock(spec=PositionTracker)
    tracker.get_all_open_positions.return_value = []
    tracker.has_open_position.return_value = False
    tracker.get_position_history.return_value = []
    tracker.count_open_positions.return_value = 0  # Added in Sprint 1.7 for atomic counting
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
    mock_position_tracker.count_open_positions.return_value = 3  # Atomic count

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
    mock_position_tracker.count_open_positions.return_value = 1  # Atomic count

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
    def use_isolated_audit_trail(self, isolated_audit_trail: Path):
        """Automatically use isolated audit trail for all tests in this class."""
        # The isolated_audit_trail fixture handles patching and cleanup
        return isolated_audit_trail

    def test_audit_trail_created_on_kill_switch(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test audit trail entry created when kill-switch activated."""
        # Mock Telegram to avoid actual network calls
        with patch("src.alerts.telegram.TelegramBot"):
            risk_manager.activate_kill_switch(reason="Test activation")

        # Verify audit trail file created
        assert isolated_audit_trail.exists()

        # Read and verify audit entry
        with open(isolated_audit_trail) as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 1
        entry = entries[0]
        assert entry["event"] == "KILL_SWITCH_ACTIVATED"
        assert entry["reason"] == "Test activation"
        assert "timestamp" in entry
        assert "daily_pnl" in entry
        assert "circuit_breaker_status" in entry

    def test_audit_trail_logs_trade_rejections(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test audit trail logs rejected trades."""
        # Activate kill-switch to trigger rejection
        with patch("src.alerts.telegram.TelegramBot"):
            risk_manager.activate_kill_switch()

        # Clear audit trail from kill-switch activation
        isolated_audit_trail.unlink()

        # Attempt trade (should be rejected)
        is_valid, msg = risk_manager.validate_trade(
            symbol="BTCUSDT", quote_qty=10.0, side="BUY", strategy_id="test_strategy"
        )

        assert is_valid is False

        # Verify rejection logged
        with open(isolated_audit_trail) as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 1
        entry = entries[0]
        assert entry["event"] == "TRADE_REJECTED"
        assert entry["reason"] == "kill_switch_active"
        assert entry["symbol"] == "BTCUSDT"
        assert entry["strategy_id"] == "test_strategy"

    def test_audit_trail_logs_trade_approvals(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test audit trail logs approved trades."""
        is_valid, msg = risk_manager.validate_trade(
            symbol="BTCUSDT", quote_qty=4.0, side="BUY", strategy_id="rsi_strategy"
        )

        assert is_valid is True

        # Verify approval logged
        with open(isolated_audit_trail) as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 1
        entry = entries[0]
        assert entry["event"] == "TRADE_APPROVED"
        assert entry["symbol"] == "BTCUSDT"
        assert entry["side"] == "BUY"
        assert entry["quote_qty"] == 4.0
        assert entry["strategy_id"] == "rsi_strategy"

    def test_audit_trail_logs_kill_switch_deactivation(
        self, risk_manager: RiskManager, isolated_audit_trail: Path
    ) -> None:
        """Test audit trail logs kill-switch deactivation."""
        # Activate then deactivate
        with patch("src.alerts.telegram.TelegramBot"):
            risk_manager.activate_kill_switch()
        risk_manager.deactivate_kill_switch(reason="Manual override")

        # Read all entries
        with open(isolated_audit_trail) as f:
            entries = [json.loads(line) for line in f]

        # Should have 2 entries: activation + deactivation
        assert len(entries) == 2
        assert entries[0]["event"] == "KILL_SWITCH_ACTIVATED"
        assert entries[1]["event"] == "KILL_SWITCH_DEACTIVATED"
        assert entries[1]["reason"] == "Manual override"

    def test_audit_trail_jsonl_format(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test audit trail uses JSONL format (one JSON per line)."""
        # Create multiple events
        risk_manager.validate_trade("BTCUSDT", 4.0, "BUY", "strategy1")
        risk_manager.validate_trade("ETHUSDT", 3.0, "BUY", "strategy2")

        # Verify each line is valid JSON
        with open(isolated_audit_trail) as f:
            lines = f.readlines()

        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line.strip())
            assert "event" in entry
            assert "timestamp" in entry

    def test_kill_switch_allows_sell_orders(
        self, risk_manager: RiskManager, isolated_audit_trail: Path
    ) -> None:
        """Test that kill-switch blocks BUY but allows SELL orders to exit positions."""
        # Activate kill-switch
        with patch("src.alerts.telegram.TelegramBot"):
            risk_manager.activate_kill_switch(reason="Test: Daily loss limit")

        # SELL order should pass validation (exit allowed)
        is_valid, msg = risk_manager.validate_trade(
            symbol="BTCUSDT", quote_qty=10.0, side="SELL", strategy_id="test_exit"
        )
        assert is_valid is True, f"SELL should pass under kill-switch, got: {msg}"

        # BUY order should fail validation (new positions blocked)
        is_valid, msg = risk_manager.validate_trade(
            symbol="BTCUSDT", quote_qty=10.0, side="BUY", strategy_id="test_entry"
        )
        assert is_valid is False, "BUY should fail under kill-switch"
        assert "KILL-SWITCH ACTIVE" in msg
        assert "exits allowed" in msg


class TestTelegramIntegration:
    """Tests for Telegram alert integration."""

    @pytest.fixture(autouse=True)
    def use_isolated_audit_trail(self, isolated_audit_trail: Path):
        """Automatically use isolated audit trail for all tests in this class."""
        return isolated_audit_trail

    @patch("src.alerts.telegram.TelegramBot")
    def test_kill_switch_sends_telegram_alert(
        self,
        mock_telegram_class: Mock,
        risk_manager: RiskManager,
        isolated_audit_trail: Path,
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
        self,
        mock_telegram_class: Mock,
        risk_manager: RiskManager,
        isolated_audit_trail: Path,
    ) -> None:
        """Test kill-switch activation continues even if Telegram fails."""
        # Make Telegram raise an exception
        mock_telegram_class.side_effect = Exception("Telegram API error")

        # Should not raise - kill-switch should still activate
        risk_manager.activate_kill_switch()

        assert risk_manager.kill_switch_active is True

        # Audit trail should still be written
        assert isolated_audit_trail.exists()


class TestValidateTradeStrategyId:
    """Tests for strategy_id parameter in validate_trade."""

    @pytest.fixture(autouse=True)
    def use_isolated_audit_trail(self, isolated_audit_trail: Path):
        """Automatically use isolated audit trail for all tests in this class."""
        return isolated_audit_trail

    def test_strategy_id_included_in_audit_log(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test strategy_id is captured in audit log."""
        risk_manager.validate_trade(
            symbol="BTCUSDT", quote_qty=4.0, side="BUY", strategy_id="rsi_conservative"
        )

        with open(isolated_audit_trail) as f:
            entry = json.loads(f.readline())

        assert entry["strategy_id"] == "rsi_conservative"

    def test_default_strategy_id(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test default strategy_id when not provided."""
        risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")

        with open(isolated_audit_trail) as f:
            entry = json.loads(f.readline())

        assert entry["strategy_id"] == "unknown"


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration with RiskManager."""

    @pytest.fixture(autouse=True)
    def use_isolated_audit_trail(self, isolated_audit_trail: Path):
        """Automatically use isolated audit trail for all tests in this class."""
        return isolated_audit_trail

    @patch("src.risk.manager.circuit_monitor")
    def test_validate_trade_rejects_when_circuit_breaker_open(
        self,
        mock_circuit_monitor: Mock,
        risk_manager: RiskManager,
        isolated_audit_trail: Path,
    ) -> None:
        """Test trade validation fails when circuit breaker is open."""
        # Mock circuit breaker as open
        mock_circuit_monitor.is_any_open.return_value = True
        mock_circuit_monitor.get_status.return_value = {
            "binance_api": {
                "state": "open",
                "fail_counter": 5,
            }
        }

        is_valid, msg = risk_manager.validate_trade(
            symbol="BTCUSDT", quote_qty=4.0, side="BUY", strategy_id="test_strategy"
        )

        assert is_valid is False
        assert "circuit breaker" in msg.lower()

        # Verify audit trail
        with open(isolated_audit_trail) as f:
            entry = json.loads(f.readline())

        assert entry["event"] == "TRADE_REJECTED"
        assert entry["reason"] == "circuit_breaker_open"
        assert "circuit_breaker_status" in entry

    @patch("src.risk.manager.circuit_monitor")
    def test_validate_trade_passes_when_circuit_breaker_closed(
        self,
        mock_circuit_monitor: Mock,
        risk_manager: RiskManager,
        isolated_audit_trail: Path,
    ) -> None:
        """Test trade validation passes when circuit breaker is closed."""
        mock_circuit_monitor.is_any_open.return_value = False

        is_valid, msg = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")

        assert is_valid is True


class TestDailyPnLCaching:
    """Tests for daily PnL caching behavior."""

    def test_get_daily_pnl_caches_result(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test daily PnL is cached to avoid excessive DB queries."""
        today = datetime.utcnow()
        mock_position_tracker.get_position_history.return_value = [
            Position(
                symbol="BTCUSDT",
                quantity=Decimal("0.1"),
                entry_price=Decimal("50000"),
                entry_time=today,
                order_id="1",
                exit_price=Decimal("51000"),
                exit_time=today,
                pnl=Decimal("100.0"),
                status="CLOSED",
            ),
        ]

        # First call - should query DB
        pnl1 = risk_manager.get_daily_pnl()
        assert pnl1 == Decimal("100.0")
        assert mock_position_tracker.get_position_history.call_count == 1

        # Second call within 60 seconds - should use cache
        pnl2 = risk_manager.get_daily_pnl()
        assert pnl2 == Decimal("100.0")
        assert mock_position_tracker.get_position_history.call_count == 1  # Not called again

    def test_get_daily_pnl_cache_expires_after_60_seconds(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test daily PnL cache expires after 60 seconds."""
        today = datetime.utcnow()
        mock_position_tracker.get_position_history.return_value = [
            Position(
                symbol="BTCUSDT",
                quantity=Decimal("0.1"),
                entry_price=Decimal("50000"),
                entry_time=today,
                order_id="1",
                exit_price=Decimal("51000"),
                exit_time=today,
                pnl=Decimal("100.0"),
                status="CLOSED",
            ),
        ]

        # First call
        pnl1 = risk_manager.get_daily_pnl()
        assert pnl1 == Decimal("100.0")

        # Manually expire cache (simulate 61 seconds passing)
        if risk_manager._daily_loss_cache:
            cache_time, cache_value = risk_manager._daily_loss_cache
            risk_manager._daily_loss_cache = (
                cache_time - timedelta(seconds=61),
                cache_value,
            )

        # Second call - cache expired, should query DB again
        pnl2 = risk_manager.get_daily_pnl()
        assert pnl2 == Decimal("100.0")
        assert mock_position_tracker.get_position_history.call_count == 2


class TestAuditLogWriteFailure:
    """Tests for audit log write failure handling."""

    @pytest.fixture(autouse=True)
    def use_isolated_audit_trail(self, isolated_audit_trail: Path):
        """Automatically use isolated audit trail for all tests in this class."""
        return isolated_audit_trail

    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_audit_log_write_failure_logged_but_not_raised(
        self,
        mock_open: Mock,
        risk_manager: RiskManager,
        isolated_audit_trail: Path,
    ) -> None:
        """Test audit log write failures are logged but don't crash."""
        # This should not raise an exception even though open() fails
        risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")

        # Risk manager should still function
        assert risk_manager.kill_switch_active is False


class TestRiskStatusReporting:
    """Tests for get_risk_status and log_risk_status."""

    def test_get_risk_status_with_cool_down_active(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test risk status includes cool-down information."""
        risk_manager.record_loss()

        status = risk_manager.get_risk_status()

        assert status["cool_down_active"] is True
        assert status["cool_down_remaining_minutes"] is not None
        assert status["cool_down_remaining_minutes"] > 0

    def test_get_risk_status_with_cool_down_expired(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test risk status when cool-down has expired."""
        # Set cool-down in the past
        risk_manager.last_loss_time = datetime.utcnow() - timedelta(
            minutes=settings.cool_down_minutes + 10
        )

        status = risk_manager.get_risk_status()

        # Cool-down should be inactive
        assert status["cool_down_active"] is False
        assert status["cool_down_remaining_minutes"] is None

    def test_get_risk_status_daily_loss_utilization(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test daily loss utilization percentage calculation."""
        today = datetime.utcnow()

        # Mock 50% of max daily loss
        mock_position_tracker.get_position_history.return_value = [
            Position(
                symbol="BTCUSDT",
                quantity=Decimal("0.1"),
                entry_price=Decimal("50000"),
                entry_time=today,
                order_id="1",
                exit_price=Decimal("49900"),
                exit_time=today,
                pnl=Decimal("-10.0"),  # 50% of MAX_DAILY_LOSS=20.0
                status="CLOSED",
            ),
        ]

        status = risk_manager.get_risk_status()

        assert status["daily_loss_utilization"] == 50.0

    def test_log_risk_status_executes_without_error(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test log_risk_status method executes successfully."""
        # This should not raise any exceptions
        risk_manager.log_risk_status()


class TestKillSwitchEdgeCases:
    """Tests for kill-switch edge cases."""

    @pytest.fixture(autouse=True)
    def use_isolated_audit_trail(self, isolated_audit_trail: Path):
        """Automatically use isolated audit trail for all tests in this class."""
        return isolated_audit_trail

    @patch("src.alerts.telegram.TelegramBot")
    def test_deactivate_kill_switch_when_already_inactive(
        self,
        mock_telegram_class: Mock,
        risk_manager: RiskManager,
        isolated_audit_trail: Path,
    ) -> None:
        """Test deactivating kill-switch when it's already inactive."""
        # Kill-switch is inactive by default
        assert risk_manager.kill_switch_active is False

        # Should handle gracefully
        risk_manager.deactivate_kill_switch(reason="Test")

        # Should remain inactive
        assert risk_manager.kill_switch_active is False

    @patch("src.alerts.telegram.TelegramBot")
    def test_activate_kill_switch_when_already_active(
        self,
        mock_telegram_class: Mock,
        risk_manager: RiskManager,
        isolated_audit_trail: Path,
    ) -> None:
        """Test activating kill-switch when it's already active."""
        # Activate first time
        risk_manager.activate_kill_switch(reason="First activation")
        assert risk_manager.kill_switch_active is True

        # Clear audit trail
        isolated_audit_trail.unlink()

        # Activate again - should be idempotent
        risk_manager.activate_kill_switch(reason="Second activation")
        assert risk_manager.kill_switch_active is True

        # Should NOT create audit log entry (already active)
        assert not isolated_audit_trail.exists()


class TestSellOrderValidation:
    """Tests for SELL order validation logic."""

    @pytest.fixture(autouse=True)
    def use_isolated_audit_trail(self, isolated_audit_trail: Path):
        """Automatically use isolated audit trail for all tests in this class."""
        return isolated_audit_trail

    def test_sell_order_ignores_per_trade_limit(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test SELL orders are not subject to per-trade loss limit."""
        # SELL with large quote_qty that would exceed limit for BUY
        is_valid, msg = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=100.0, side="SELL")

        # Should pass - SELL doesn't check per-trade limit
        assert is_valid is True

    def test_sell_order_ignores_position_count_limit(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test SELL orders are not subject to position count limit."""
        # Mock max positions reached
        mock_position_tracker.get_all_open_positions.return_value = [
            Mock(),
            Mock(),
            Mock(),
        ]

        is_valid, msg = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=10.0, side="SELL")

        # Should pass - SELL doesn't check position limit
        assert is_valid is True

    def test_sell_order_ignores_duplicate_position_check(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test SELL orders are not subject to duplicate position check."""
        mock_position_tracker.has_open_position.return_value = True

        is_valid, msg = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=10.0, side="SELL")

        # Should pass - SELL doesn't check for duplicate position
        assert is_valid is True


class TestConcurrentValidation:
    """Tests for concurrent trade validation edge cases."""

    @pytest.fixture(autouse=True)
    def use_isolated_audit_trail(self, isolated_audit_trail: Path):
        """Automatically use isolated audit trail for all tests in this class."""
        return isolated_audit_trail

    def test_multiple_trades_same_symbol_rejected(
        self,
        risk_manager: RiskManager,
        mock_position_tracker: Mock,
        isolated_audit_trail: Path,
    ) -> None:
        """Test multiple BUY orders for same symbol are rejected."""
        # First trade should pass
        is_valid1, msg1 = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")
        assert is_valid1 is True

        # Mock position tracker to show position exists
        mock_position_tracker.has_open_position.return_value = True

        # Second trade for same symbol should fail
        is_valid2, msg2 = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")
        assert is_valid2 is False
        assert "already exists" in msg2.lower()

    def test_multiple_trades_different_symbols_allowed(
        self, risk_manager: RiskManager, mock_position_tracker: Mock
    ) -> None:
        """Test multiple BUY orders for different symbols are allowed."""
        # First trade
        is_valid1, msg1 = risk_manager.validate_trade(symbol="BTCUSDT", quote_qty=4.0, side="BUY")
        assert is_valid1 is True

        # Second trade for different symbol
        is_valid2, msg2 = risk_manager.validate_trade(symbol="ETHUSDT", quote_qty=4.0, side="BUY")
        assert is_valid2 is True
