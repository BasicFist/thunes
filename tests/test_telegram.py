"""Tests for Telegram notification system."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.alerts.telegram import TelegramBot, send_alert


@pytest.fixture
def telegram_bot() -> TelegramBot:
    """Create TelegramBot instance with mocked Bot."""
    with patch("src.alerts.telegram.Bot") as MockBot:
        mock_bot_instance = MagicMock()
        # Mock async send_message method
        mock_bot_instance.send_message = AsyncMock()
        MockBot.return_value = mock_bot_instance

        bot = TelegramBot(
            token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789",
        )
        # Store mock for verification in tests
        bot._mock_bot = mock_bot_instance  # type: ignore[attr-defined]
        return bot


@pytest.fixture
def disabled_telegram_bot() -> TelegramBot:
    """Create TelegramBot with disabled configuration."""
    return TelegramBot(token="", chat_id="")


def test_telegram_bot_initialization(telegram_bot: TelegramBot) -> None:
    """Test TelegramBot initialization with valid credentials."""
    assert telegram_bot.enabled is True
    assert telegram_bot.token is not None
    assert telegram_bot.chat_id is not None
    assert telegram_bot.bot is not None


def test_telegram_bot_disabled(disabled_telegram_bot: TelegramBot) -> None:
    """Test TelegramBot initialization when disabled."""
    assert disabled_telegram_bot.enabled is False


@pytest.mark.asyncio
async def test_send_message(telegram_bot: TelegramBot) -> None:
    """Test sending a basic message."""
    result = await telegram_bot.send_message("Test message")

    assert result is True
    telegram_bot._mock_bot.send_message.assert_called_once()
    call_kwargs = telegram_bot._mock_bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == telegram_bot.chat_id
    assert call_kwargs["text"] == "Test message"
    assert call_kwargs["parse_mode"] == "Markdown"
    assert call_kwargs["disable_notification"] is False


@pytest.mark.asyncio
async def test_send_message_disabled(disabled_telegram_bot: TelegramBot) -> None:
    """Test sending message when Telegram is disabled."""
    result = await disabled_telegram_bot.send_message("Test message")
    assert result is False


@pytest.mark.asyncio
async def test_send_kill_switch_alert(telegram_bot: TelegramBot) -> None:
    """Test kill-switch alert formatting and sending."""
    daily_loss = Decimal("25.50")
    limit = Decimal("20.00")

    result = await telegram_bot.send_kill_switch_alert(daily_loss, limit)

    assert result is True
    telegram_bot._mock_bot.send_message.assert_called_once()
    call_kwargs = telegram_bot._mock_bot.send_message.call_args.kwargs
    message = call_kwargs["text"]

    # Verify message contains key information
    assert "KILL-SWITCH TRIGGERED" in message
    assert "25.50 USDT" in message
    assert "20.00 USDT" in message
    assert "TRADING HALTED" in message
    assert call_kwargs["disable_notification"] is False  # Critical alert


@pytest.mark.asyncio
async def test_send_parameter_decay_warning(telegram_bot: TelegramBot) -> None:
    """Test parameter decay warning alert."""
    current_sharpe = Decimal("0.75")
    threshold = Decimal("1.00")

    result = await telegram_bot.send_parameter_decay_warning(
        current_sharpe, threshold, severity="WARNING"
    )

    assert result is True
    telegram_bot._mock_bot.send_message.assert_called_once()
    call_kwargs = telegram_bot._mock_bot.send_message.call_args.kwargs
    message = call_kwargs["text"]

    # Verify message formatting
    assert "PARAMETER DECAY: WARNING" in message
    assert "0.7500" in message or "0.75" in message
    assert "1.00" in message or "1.0000" in message
    assert "Re-optimization recommended" in message
    assert call_kwargs["disable_notification"] is True  # Non-critical


@pytest.mark.asyncio
async def test_send_parameter_decay_critical(telegram_bot: TelegramBot) -> None:
    """Test parameter decay critical alert."""
    current_sharpe = Decimal("0.40")
    threshold = Decimal("0.50")

    result = await telegram_bot.send_parameter_decay_warning(
        current_sharpe, threshold, severity="CRITICAL"
    )

    assert result is True
    call_kwargs = telegram_bot._mock_bot.send_message.call_args.kwargs
    message = call_kwargs["text"]

    # Verify critical severity formatting
    assert "PARAMETER DECAY: CRITICAL" in message
    assert "REQUIRED" in message
    assert call_kwargs["disable_notification"] is False  # Critical = notify


@pytest.mark.asyncio
async def test_send_reoptimization_complete(telegram_bot: TelegramBot) -> None:
    """Test re-optimization completion notification."""
    old_params = {
        "strategy": "RSI",
        "parameters": {"rsi_period": 14, "oversold": 30.0, "overbought": 70.0},
    }
    new_params = {
        "strategy": "RSI",
        "parameters": {"rsi_period": 18, "oversold": 25.0, "overbought": 75.0},
    }
    improvement = 15.5

    result = await telegram_bot.send_reoptimization_complete(old_params, new_params, improvement)

    assert result is True
    call_kwargs = telegram_bot._mock_bot.send_message.call_args.kwargs
    message = call_kwargs["text"]

    # Verify message contains parameter changes
    assert "RE-OPTIMIZATION COMPLETE" in message
    assert "RSI" in message
    assert "+15.50%" in message
    assert "rsi_period" in message
    assert "14" in message and "18" in message  # Old and new values
    assert call_kwargs["disable_notification"] is True  # Informational


@pytest.mark.asyncio
async def test_send_daily_summary(telegram_bot: TelegramBot) -> None:
    """Test daily performance summary."""
    total_pnl = Decimal("12.50")
    win_rate = 65.0
    sharpe = Decimal("1.25")
    total_trades = 20
    profitable_trades = 13

    result = await telegram_bot.send_daily_summary(
        total_pnl, win_rate, sharpe, total_trades, profitable_trades
    )

    assert result is True
    call_kwargs = telegram_bot._mock_bot.send_message.call_args.kwargs
    message = call_kwargs["text"]

    # Verify summary statistics
    assert "DAILY SUMMARY" in message
    assert "+12.50 USDT" in message
    assert "65.0%" in message
    assert "1.25" in message
    assert "20" in message  # Total trades
    assert "13" in message  # Profitable trades
    assert call_kwargs["disable_notification"] is True  # Regular update


@pytest.mark.asyncio
async def test_send_custom_alert(telegram_bot: TelegramBot) -> None:
    """Test custom alert with arbitrary details."""
    result = await telegram_bot.send_custom_alert(
        title="Test Alert", details={"Status": "OK", "Value": 123}
    )

    assert result is True
    call_kwargs = telegram_bot._mock_bot.send_message.call_args.kwargs
    message = call_kwargs["text"]

    assert "Test Alert" in message
    assert "Status" in message
    assert "OK" in message
    assert "Value" in message
    assert "123" in message


def test_send_message_sync(telegram_bot: TelegramBot) -> None:
    """Test synchronous message wrapper."""
    result = telegram_bot.send_message_sync("Sync test")

    assert result is True
    telegram_bot._mock_bot.send_message.assert_called_once()


def test_send_alert_convenience_function() -> None:
    """Test the send_alert convenience function."""
    with patch("src.alerts.telegram.TelegramBot") as MockBot:
        mock_instance = MagicMock()
        mock_instance.send_message_sync.return_value = True
        MockBot.return_value = mock_instance

        result = send_alert("Test convenience")

        assert result is True
        mock_instance.send_message_sync.assert_called_once_with("Test convenience")


@pytest.mark.asyncio
async def test_telegram_error_handling(telegram_bot: TelegramBot) -> None:
    """Test error handling when Telegram API fails."""
    from telegram.error import TelegramError

    # Make send_message raise an error
    telegram_bot._mock_bot.send_message.side_effect = TelegramError("Network error")

    result = await telegram_bot.send_message("Test error handling")

    assert result is False  # Should return False on error


def test_emoji_usage_in_critical_alerts(telegram_bot: TelegramBot) -> None:
    """Test that critical alerts include appropriate emojis."""
    import asyncio

    # Run async methods synchronously for simplicity
    asyncio.run(telegram_bot.send_kill_switch_alert(Decimal("25"), Decimal("20")))

    # Verify emoji in kill-switch message
    call_kwargs = telegram_bot._mock_bot.send_message.call_args.kwargs
    message = call_kwargs["text"]
    assert "🚨" in message  # Critical alert emoji
    assert "⛔" in message  # Stop sign emoji
