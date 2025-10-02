"""Telegram notifications for critical trading events.

Implements async notifications for:
- Kill-switch triggers (daily loss limit)
- Parameter decay warnings (Sharpe < 1.0 or < 0.5)
- Re-optimization completion
- Daily performance summaries
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any

from telegram import Bot
from telegram.error import TelegramError

from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TelegramBot:
    """Async Telegram bot for trading alerts.

    Attributes:
        bot: Telegram Bot instance
        chat_id: Target chat ID for notifications
        enabled: Whether notifications are enabled
    """

    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        """Initialize Telegram bot.

        Args:
            token: Telegram bot token (defaults to settings)
            chat_id: Target chat ID (defaults to settings)
        """
        self.token = token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id

        # Check if Telegram is properly configured
        self.enabled = bool(self.token and self.chat_id)

        if self.enabled:
            self.bot = Bot(token=self.token)
            logger.info(f"TelegramBot initialized (chat_id={self.chat_id})")
        else:
            logger.warning("TelegramBot disabled: Missing token or chat_id")

    async def send_message(
        self, message: str, parse_mode: str = "Markdown", disable_notification: bool = False
    ) -> bool:
        """Send message to configured chat.

        Args:
            message: Message text (supports Markdown)
            parse_mode: Telegram parse mode (Markdown or HTML)
            disable_notification: Whether to send silently

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled, would send: {message}")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )
            logger.info("Telegram message sent successfully")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_kill_switch_alert(self, daily_loss: Decimal, limit: Decimal) -> bool:
        """Send kill-switch trigger notification.

        Args:
            daily_loss: Current daily loss amount
            limit: Daily loss limit that was exceeded

        Returns:
            True if sent successfully
        """
        message = (
            "🚨 *KILL-SWITCH TRIGGERED* 🚨\n\n"
            f"*Daily Loss Limit Exceeded*\n"
            f"Current Loss: `{daily_loss:.2f} USDT`\n"
            f"Limit: `{limit:.2f} USDT`\n\n"
            f"⛔ *TRADING HALTED* ⛔\n"
            f"Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
            f"Action Required: Review logs and adjust strategy parameters"
        )
        return await self.send_message(message, disable_notification=False)

    async def send_parameter_decay_warning(
        self,
        current_sharpe: Decimal,
        threshold: Decimal,
        severity: str = "WARNING",
    ) -> bool:
        """Send parameter decay warning.

        Args:
            current_sharpe: Current rolling Sharpe ratio
            threshold: Sharpe threshold that was crossed
            severity: Alert severity (WARNING or CRITICAL)

        Returns:
            True if sent successfully
        """
        emoji = "⚠️" if severity == "WARNING" else "🚨"
        message = (
            f"{emoji} *PARAMETER DECAY: {severity}* {emoji}\n\n"
            f"*Strategy Performance Degrading*\n"
            f"Current Sharpe: `{current_sharpe:.4f}`\n"
            f"Threshold: `{threshold:.4f}`\n\n"
            f"{'⏳ Re-optimization recommended' if severity == 'WARNING' else '🔴 Re-optimization REQUIRED'}\n"
            f"Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        return await self.send_message(message, disable_notification=(severity == "WARNING"))

    async def send_reoptimization_complete(
        self,
        old_params: dict[str, Any],
        new_params: dict[str, Any],
        improvement: float,
    ) -> bool:
        """Send re-optimization completion notification.

        Args:
            old_params: Previous strategy parameters
            new_params: New optimized parameters
            improvement: Performance improvement percentage

        Returns:
            True if sent successfully
        """
        message = (
            "✅ *RE-OPTIMIZATION COMPLETE*\n\n"
            f"*New Parameters Loaded*\n"
            f"Strategy: `{new_params.get('strategy', 'Unknown')}`\n"
            f"Improvement: `{improvement:+.2f}%`\n\n"
            f"*Parameter Changes:*\n"
        )

        # Compare old vs new parameters
        old_p = old_params.get("parameters", {})
        new_p = new_params.get("parameters", {})

        for key in sorted(new_p.keys()):
            old_val = old_p.get(key, "N/A")
            new_val = new_p[key]
            message += f"• {key}: `{old_val}` → `{new_val}`\n"

        message += f"\nTime: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"

        return await self.send_message(message, disable_notification=True)

    async def send_daily_summary(
        self,
        total_pnl: Decimal,
        win_rate: float,
        sharpe: Decimal,
        total_trades: int,
        profitable_trades: int,
    ) -> bool:
        """Send daily performance summary.

        Args:
            total_pnl: Total realized PnL for the day
            win_rate: Win rate percentage
            sharpe: Sharpe ratio
            total_trades: Total number of trades
            profitable_trades: Number of profitable trades

        Returns:
            True if sent successfully
        """
        emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➖"
        message = (
            f"{emoji} *DAILY SUMMARY*\n\n"
            f"*Performance (24h)*\n"
            f"Total PnL: `{total_pnl:+.2f} USDT`\n"
            f"Win Rate: `{win_rate:.1f}%`\n"
            f"Sharpe Ratio: `{sharpe:.4f}`\n\n"
            f"*Trade Statistics*\n"
            f"Total Trades: `{total_trades}`\n"
            f"Profitable: `{profitable_trades}` ({win_rate:.1f}%)\n"
            f"Losing: `{total_trades - profitable_trades}`\n\n"
            f"Date: `{datetime.now().strftime('%Y-%m-%d')}`"
        )
        return await self.send_message(message, disable_notification=True)

    async def send_custom_alert(self, title: str, details: dict[str, Any]) -> bool:
        """Send custom alert with arbitrary details.

        Args:
            title: Alert title
            details: Key-value pairs to include in message

        Returns:
            True if sent successfully
        """
        message = f"*{title}*\n\n"
        for key, value in details.items():
            message += f"• {key}: `{value}`\n"
        message += f"\nTime: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"

        return await self.send_message(message, disable_notification=True)

    def send_message_sync(self, message: str) -> bool:
        """Synchronous wrapper for send_message (for non-async contexts).

        Args:
            message: Message text

        Returns:
            True if sent successfully
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.send_message(message))


# Convenience function for quick alerts
def send_alert(message: str, bot_instance: TelegramBot | None = None) -> bool:
    """Send quick alert using default or provided bot instance.

    Args:
        message: Message to send
        bot_instance: Optional bot instance (creates new one if None)

    Returns:
        True if sent successfully
    """
    bot = bot_instance or TelegramBot()
    return bot.send_message_sync(message)
