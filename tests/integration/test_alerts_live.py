"""Alerting integration smoke tests (opt-in)."""

from __future__ import annotations

import os
import time

import pytest

from src.alerts.telegram import TelegramBot
from src.config import settings

pytestmark = [pytest.mark.slow, pytest.mark.integration_creds]

if os.getenv("TELEGRAM_TESTS_ENABLE") != "1":  # pragma: no cover - opt-in
    pytest.skip(
        "Set TELEGRAM_TESTS_ENABLE=1 to run Telegram integration smoke",
        allow_module_level=True,
    )


@pytest.mark.integration_creds
def test_telegram_alert_delivery() -> None:
    """Send a short Telegram message when integration testing is enabled."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        pytest.skip("Telegram credentials not configured")

    bot = TelegramBot()
    if not bot.enabled:
        pytest.skip("TelegramBot disabled despite credentials")

    message = f"THUNES integration ping {int(time.time())}"
    assert bot.send_message_sync(message)
