#!/usr/bin/env python3
"""Verify Telegram bot configuration for THUNES.

This script checks if Telegram credentials are properly configured
and tests the bot connectivity.

Usage:
    python scripts/verify_telegram.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.alerts.telegram import TelegramBot  # noqa: E402
from src.config import settings  # noqa: E402


def main() -> None:
    """Verify Telegram configuration."""
    print("=" * 60)
    print("   THUNES Telegram Bot Verification")
    print("=" * 60)
    print()

    # Check credentials
    print("1. Checking credentials...")
    if not settings.telegram_bot_token:
        print("   ✗ TELEGRAM_BOT_TOKEN not found in .env")
        print()
        print("   Run: ./scripts/setup_telegram.sh")
        sys.exit(1)

    if not settings.telegram_chat_id:
        print("   ✗ TELEGRAM_CHAT_ID not found in .env")
        print()
        print("   Run: ./scripts/setup_telegram.sh")
        sys.exit(1)

    print(f"   ✓ Bot Token: {'*' * 20}{settings.telegram_bot_token[-10:]}")
    print(f"   ✓ Chat ID: {settings.telegram_chat_id}")
    print()

    # Initialize bot
    print("2. Initializing bot...")
    try:
        bot = TelegramBot()
        if not bot.enabled:
            print("   ✗ Bot initialization failed (disabled)")
            sys.exit(1)
        print("   ✓ Bot initialized successfully")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        sys.exit(1)
    print()

    # Test connectivity
    print("3. Testing connectivity...")
    test_message = (
        "🔍 THUNES Telegram Verification\n\n"
        "If you see this message, your Telegram bot is:\n"
        "✓ Properly configured\n"
        "✓ Connected to Telegram API\n"
        "✓ Ready for Phase 13 deployment\n\n"
        "You will receive:\n"
        "• Kill-switch alerts (if triggered)\n"
        "• Daily summaries (23:00 UTC)\n"
        "• Parameter decay warnings\n"
        "• Re-optimization notifications"
    )

    try:
        result = bot.send_message_sync(test_message)
        if result:
            print("   ✓ Test message sent successfully")
            print()
            print("=" * 60)
            print("   Verification Complete! ✓")
            print("=" * 60)
            print()
            print("Check your Telegram app to confirm you received the message.")
            print()
            sys.exit(0)
        else:
            print("   ✗ Failed to send test message")
            sys.exit(1)
    except Exception as e:
        print(f"   ✗ Error sending message: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
