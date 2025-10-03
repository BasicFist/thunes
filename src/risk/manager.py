"""Risk management module with kill-switch functionality.

This module implements critical safety features:
- Daily loss tracking and limits (kill-switch)
- Per-trade loss limits
- Position count limits
- Cool-down periods after losses
- Circuit breaker integration
- Immutable audit trail for regulatory compliance
- Telegram alerts for critical events
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.config import settings
from src.models.position import PositionTracker
from src.utils.circuit_breaker import circuit_monitor
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Audit trail file path
AUDIT_TRAIL_PATH = Path("logs/audit_trail.jsonl")


class RiskManager:
    """Enforces trading risk limits with kill-switch protection."""

    def __init__(
        self,
        position_tracker: PositionTracker | None = None,
        enable_telegram: bool = True,
        telegram_bot: Any | None = None,
    ) -> None:
        """
        Initialize risk manager.

        Args:
            position_tracker: PositionTracker instance (creates new if None)
            enable_telegram: Enable Telegram kill-switch alerts
            telegram_bot: Pre-initialized TelegramBot instance (creates new if None and enabled)
        """
        self.position_tracker = position_tracker or PositionTracker()
        self.enable_telegram = enable_telegram
        self.telegram_bot = telegram_bot

        # Risk limits from config
        self.max_loss_per_trade = Decimal(str(settings.max_loss_per_trade))
        self.max_daily_loss = Decimal(str(settings.max_daily_loss))
        self.max_positions = settings.max_positions
        self.cool_down_minutes = settings.cool_down_minutes

        # State tracking
        self.kill_switch_active = False
        self.last_loss_time: datetime | None = None
        self._daily_loss_cache: tuple[datetime, Decimal] | None = None

        logger.info(
            f"RiskManager initialized: max_loss_per_trade={self.max_loss_per_trade}, "
            f"max_daily_loss={self.max_daily_loss}, max_positions={self.max_positions}, "
            f"telegram_enabled={self.enable_telegram}"
        )

    def validate_trade(
        self,
        symbol: str,
        quote_qty: float,
        side: str = "BUY",
        strategy_id: str = "unknown",
    ) -> tuple[bool, str]:
        """
        Validate if trade is allowed under risk management rules.

        Args:
            symbol: Trading pair symbol
            quote_qty: Amount in quote currency (e.g., USDT)
            side: Trade side ("BUY" or "SELL")
            strategy_id: Strategy identifier for audit trail

        Returns:
            Tuple of (is_valid, reason_message)
        """
        # 1. Check kill-switch
        if self.kill_switch_active:
            self._write_audit_log(
                event="TRADE_REJECTED",
                details={
                    "reason": "kill_switch_active",
                    "symbol": symbol,
                    "side": side,
                    "quote_qty": quote_qty,
                    "strategy_id": strategy_id,
                },
            )
            return False, "🛑 KILL-SWITCH ACTIVE: Trading halted due to max daily loss"

        # 2. Check daily loss limit
        daily_loss = self.get_daily_pnl()
        if daily_loss <= -self.max_daily_loss:
            self.activate_kill_switch(reason=f"Daily loss {daily_loss:.2f} exceeds limit")
            self._write_audit_log(
                event="TRADE_REJECTED",
                details={
                    "reason": "daily_loss_limit_exceeded",
                    "symbol": symbol,
                    "side": side,
                    "quote_qty": quote_qty,
                    "strategy_id": strategy_id,
                    "daily_pnl": float(daily_loss),
                    "daily_loss_limit": float(self.max_daily_loss),
                },
            )
            return (
                False,
                f"🛑 KILL-SWITCH: Daily loss {daily_loss:.2f} exceeds limit {-self.max_daily_loss:.2f}",
            )

        # 3. Check per-trade loss limit (for BUY orders)
        if side == "BUY":
            quote_decimal = Decimal(str(quote_qty))
            if quote_decimal > self.max_loss_per_trade:
                self._write_audit_log(
                    event="TRADE_REJECTED",
                    details={
                        "reason": "per_trade_loss_limit_exceeded",
                        "symbol": symbol,
                        "side": side,
                        "quote_qty": quote_qty,
                        "strategy_id": strategy_id,
                        "max_loss_per_trade": float(self.max_loss_per_trade),
                    },
                )
                return (
                    False,
                    f"❌ Trade size {quote_qty:.2f} exceeds max loss per trade {self.max_loss_per_trade}",
                )

        # 4. Check position count limit (for BUY orders)
        if side == "BUY":
            open_positions = self.position_tracker.get_all_open_positions()
            if len(open_positions) >= self.max_positions:
                self._write_audit_log(
                    event="TRADE_REJECTED",
                    details={
                        "reason": "max_position_limit_reached",
                        "symbol": symbol,
                        "side": side,
                        "quote_qty": quote_qty,
                        "strategy_id": strategy_id,
                        "open_positions": len(open_positions),
                        "max_positions": self.max_positions,
                    },
                )
                return (
                    False,
                    f"❌ Max position limit reached ({len(open_positions)}/{self.max_positions})",
                )

        # 5. Check if position already exists for symbol (for BUY orders)
        if side == "BUY":
            if self.position_tracker.has_open_position(symbol):
                self._write_audit_log(
                    event="TRADE_REJECTED",
                    details={
                        "reason": "duplicate_position",
                        "symbol": symbol,
                        "side": side,
                        "quote_qty": quote_qty,
                        "strategy_id": strategy_id,
                    },
                )
                return False, f"❌ Position already exists for {symbol}"

        # 6. Check cool-down period after loss
        if self.last_loss_time and side == "BUY":
            cool_down_end = self.last_loss_time + timedelta(minutes=self.cool_down_minutes)
            if datetime.utcnow() < cool_down_end:
                remaining = (cool_down_end - datetime.utcnow()).total_seconds() / 60
                self._write_audit_log(
                    event="TRADE_REJECTED",
                    details={
                        "reason": "cool_down_active",
                        "symbol": symbol,
                        "side": side,
                        "quote_qty": quote_qty,
                        "strategy_id": strategy_id,
                        "cool_down_remaining_minutes": round(remaining, 1),
                    },
                )
                return False, f"⏳ Cool-down active: {remaining:.1f} min remaining after loss"

        # 7. Check circuit breaker status
        if circuit_monitor.is_any_open():
            status = circuit_monitor.get_status()
            self._write_audit_log(
                event="TRADE_REJECTED",
                details={
                    "reason": "circuit_breaker_open",
                    "symbol": symbol,
                    "side": side,
                    "quote_qty": quote_qty,
                    "strategy_id": strategy_id,
                    "circuit_breaker_status": status,
                },
            )
            return False, f"⚡ Circuit breaker open: {status}"

        # All checks passed - log approval
        self._write_audit_log(
            event="TRADE_APPROVED",
            details={
                "symbol": symbol,
                "side": side,
                "quote_qty": quote_qty,
                "strategy_id": strategy_id,
                "daily_pnl": float(daily_loss),
                "open_positions": len(self.position_tracker.get_all_open_positions()),
            },
        )

        return True, "✅ Trade validation passed"

    def get_daily_pnl(self) -> Decimal:
        """
        Calculate total PnL for the current day.

        Returns:
            Total PnL in quote currency (negative for losses)
        """
        # Check cache (valid for 1 minute to avoid excessive DB queries)
        now = datetime.utcnow()
        if self._daily_loss_cache:
            cache_time, cache_value = self._daily_loss_cache
            if (now - cache_time).total_seconds() < 60:
                return cache_value

        # Calculate PnL from positions closed today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        all_positions = self.position_tracker.get_position_history(limit=1000)

        daily_pnl = Decimal("0.0")
        for position in all_positions:
            if position.exit_time and position.exit_time >= today_start:
                if position.pnl:
                    daily_pnl += position.pnl

        # Cache the result
        self._daily_loss_cache = (now, daily_pnl)

        logger.debug(f"Daily PnL: {daily_pnl:.2f} (from {len(all_positions)} positions)")
        return daily_pnl

    def _write_audit_log(self, event: str, details: dict) -> None:
        """
        Write event to immutable audit trail for regulatory compliance.

        Args:
            event: Event type (e.g., "KILL_SWITCH_ACTIVATED", "TRADE_REJECTED")
            details: Event-specific details dictionary
        """
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            **details,
        }

        # Ensure logs directory exists
        AUDIT_TRAIL_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Append to audit trail (JSONL format - one JSON object per line)
        try:
            with open(AUDIT_TRAIL_PATH, "a") as f:
                f.write(json.dumps(audit_entry) + "\n")
            logger.debug(f"Audit log written: {event}")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def activate_kill_switch(self, reason: str = "Daily loss limit exceeded") -> None:
        """
        Activate kill-switch to halt all trading.

        Triggers:
        - Critical logging
        - Telegram alert
        - Immutable audit trail entry

        Args:
            reason: Reason for activation (for audit trail)
        """
        if not self.kill_switch_active:
            self.kill_switch_active = True
            daily_loss = self.get_daily_pnl()
            logger.critical(
                f"🛑🛑🛑 KILL-SWITCH ACTIVATED 🛑🛑🛑\n"
                f"Daily loss: {daily_loss:.2f} / Limit: {-self.max_daily_loss:.2f}\n"
                f"All trading halted. Manual intervention required."
            )

            # Telegram alert (only if enabled)
            if self.enable_telegram:
                try:
                    # Use existing bot instance or create new one
                    if self.telegram_bot is None:
                        from src.alerts.telegram import TelegramBot

                        self.telegram_bot = TelegramBot()

                    # Only send if bot is properly configured
                    if self.telegram_bot and self.telegram_bot.enabled:
                        # Format kill-switch message manually
                        message = (
                            f"🛑 *KILL-SWITCH ACTIVATED* 🛑\n\n"
                            f"Daily Loss: `{daily_loss:.2f}` USDT\n"
                            f"Limit: `{-self.max_daily_loss:.2f}` USDT\n"
                            f"Utilization: `{abs(daily_loss / self.max_daily_loss * 100):.1f}%`\n\n"
                            f"⚠️ *All trading halted. Manual intervention required.*\n"
                            f"Reason: {reason}"
                        )
                        self.telegram_bot.send_message_sync(message)
                    else:
                        logger.info("Telegram bot not configured - skipping kill-switch alert")
                except Exception as e:
                    logger.error(f"Failed to send Telegram kill-switch alert: {e}")

            # Immutable audit trail
            self._write_audit_log(
                event="KILL_SWITCH_ACTIVATED",
                details={
                    "reason": reason,
                    "daily_pnl": float(daily_loss),
                    "daily_loss_limit": float(self.max_daily_loss),
                    "open_positions": len(self.position_tracker.get_all_open_positions()),
                    "circuit_breaker_status": circuit_monitor.get_status(),
                },
            )

    def deactivate_kill_switch(self, reason: str = "Manual reset") -> None:
        """
        Deactivate kill-switch (requires manual action).

        Args:
            reason: Reason for deactivation (for audit trail)
        """
        if self.kill_switch_active:
            self.kill_switch_active = False
            logger.warning(f"Kill-switch deactivated: {reason}")

            # Audit trail entry
            self._write_audit_log(
                event="KILL_SWITCH_DEACTIVATED",
                details={
                    "reason": reason,
                    "daily_pnl": float(self.get_daily_pnl()),
                },
            )
        else:
            logger.info("Kill-switch was not active")

    def record_loss(self) -> None:
        """
        Record a losing trade to trigger cool-down period.

        Should be called after closing a position with negative PnL.
        """
        self.last_loss_time = datetime.utcnow()
        logger.info(f"Loss recorded. Cool-down period active for {self.cool_down_minutes} minutes.")

    def record_win(self) -> None:
        """
        Record a winning trade (clears cool-down).

        Should be called after closing a position with positive PnL.
        """
        self.last_loss_time = None
        logger.info("Win recorded. Cool-down period cleared.")

    def get_risk_status(self) -> dict:
        """
        Get current risk management status.

        Returns:
            Dictionary with risk metrics and limits
        """
        daily_pnl = self.get_daily_pnl()
        open_positions = self.position_tracker.get_all_open_positions()

        cool_down_remaining = None
        if self.last_loss_time:
            cool_down_end = self.last_loss_time + timedelta(minutes=self.cool_down_minutes)
            if datetime.utcnow() < cool_down_end:
                cool_down_remaining = (cool_down_end - datetime.utcnow()).total_seconds() / 60

        return {
            "kill_switch_active": self.kill_switch_active,
            "daily_pnl": float(daily_pnl),
            "daily_loss_limit": float(-self.max_daily_loss),
            "daily_loss_utilization": (
                float(abs(daily_pnl) / self.max_daily_loss * 100) if daily_pnl < 0 else 0.0
            ),
            "open_positions": len(open_positions),
            "max_positions": self.max_positions,
            "position_slots_available": self.max_positions - len(open_positions),
            "cool_down_active": cool_down_remaining is not None,
            "cool_down_remaining_minutes": cool_down_remaining,
            "circuit_breaker_status": circuit_monitor.get_status(),
        }

    def log_risk_status(self) -> None:
        """Log current risk management status."""
        status = self.get_risk_status()

        logger.info(
            f"Risk Status:\n"
            f"  Kill-Switch: {'🛑 ACTIVE' if status['kill_switch_active'] else '✅ Inactive'}\n"
            f"  Daily PnL: {status['daily_pnl']:.2f} / Limit: {status['daily_loss_limit']:.2f} "
            f"({status['daily_loss_utilization']:.1f}%)\n"
            f"  Positions: {status['open_positions']}/{status['max_positions']}\n"
            f"  Cool-down: {'⏳ Active' if status['cool_down_active'] else '✅ None'}"
        )

    def reset_daily_state(self) -> None:
        """
        Reset daily state (should be called at start of new trading day).

        This does NOT deactivate kill-switch - that requires manual action.
        """
        self._daily_loss_cache = None
        if not self.kill_switch_active:
            self.last_loss_time = None
            logger.info("Daily state reset (cool-down cleared)")
        else:
            logger.warning(
                "Daily state reset (kill-switch still active - requires manual deactivation)"
            )
