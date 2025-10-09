#!/usr/bin/env python3
"""
Telegram Configuration Validator
Tests Telegram bot connectivity and alert delivery
"""

import sys
import os
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def validate_telegram():
    """Validate Telegram bot configuration and connectivity"""

    print("=" * 70)
    print("   Telegram Configuration Validator")
    print("=" * 70)
    print()

    # Check environment variables
    print("[CHECK 1/5] Environment Variables")
    print("-" * 70)

    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not bot_token:
        print("❌ FAIL: TELEGRAM_BOT_TOKEN not set")
        print("   Add to .env: TELEGRAM_BOT_TOKEN=your_token_here")
        return False
    else:
        print(f"✅ PASS: TELEGRAM_BOT_TOKEN configured ({bot_token[:10]}...)")

    if not chat_id:
        print("❌ FAIL: TELEGRAM_CHAT_ID not set")
        print("   Add to .env: TELEGRAM_CHAT_ID=your_chat_id_here")
        return False
    else:
        print(f"✅ PASS: TELEGRAM_CHAT_ID configured ({chat_id})")

    print()

    # Import TelegramBot
    print("[CHECK 2/5] Module Import")
    print("-" * 70)

    try:
        from src.alerts.telegram import TelegramBot
        print("✅ PASS: TelegramBot module imported successfully")
    except ImportError as e:
        print(f"❌ FAIL: Cannot import TelegramBot: {e}")
        return False

    print()

    # Initialize bot
    print("[CHECK 3/5] Bot Initialization")
    print("-" * 70)

    try:
        bot = TelegramBot()
        if not bot.enabled:
            print("❌ FAIL: Telegram bot is disabled")
            print("   Check .env configuration")
            return False
        print("✅ PASS: TelegramBot initialized successfully")
        print(f"   Bot enabled: {bot.enabled}")
    except Exception as e:
        print(f"❌ FAIL: Bot initialization failed: {e}")
        return False

    print()

    # Send test message
    print("[CHECK 4/5] Message Delivery Test")
    print("-" * 70)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_message = f"""🧪 Telegram Validation Test

Timestamp: {timestamp}
Status: Testing message delivery
Component: Phase 13 Pre-Deployment Validation

If you receive this message, Telegram is configured correctly! ✅"""

    try:
        start_time = time.time()
        success = bot.send_message_sync(test_message)
        delivery_time = time.time() - start_time

        if success:
            print(f"✅ PASS: Test message sent successfully")
            print(f"   Delivery time: {delivery_time:.2f} seconds")
            if delivery_time > 5:
                print(f"   ⚠️  Warning: Delivery took >{delivery_time:.1f}s (target: <5s)")
        else:
            print("❌ FAIL: Message delivery failed (returned False)")
            return False
    except Exception as e:
        print(f"❌ FAIL: Message delivery exception: {e}")
        return False

    print()

    # Send kill-switch simulation
    print("[CHECK 5/5] Kill-Switch Alert Simulation")
    print("-" * 70)

    kill_switch_message = """🚨 KILL SWITCH ACTIVATED 🚨

Reason: VALIDATION TEST
Timestamp: {timestamp}
Component: Risk Manager

This is a TEST alert simulating kill-switch activation.
In production, this alert indicates trading has been halted.

✅ If you receive this, kill-switch alerts will work correctly!"""

    try:
        start_time = time.time()
        success = bot.send_message_sync(kill_switch_message.format(timestamp=timestamp))
        delivery_time = time.time() - start_time

        if success:
            print(f"✅ PASS: Kill-switch simulation alert sent")
            print(f"   Delivery time: {delivery_time:.2f} seconds")
            if delivery_time < 5:
                print(f"   ✅ Excellent: Alert delivered in <5s")
            else:
                print(f"   ⚠️  Warning: Slow delivery (target: <5s)")
        else:
            print("❌ FAIL: Kill-switch alert failed")
            return False
    except Exception as e:
        print(f"❌ FAIL: Kill-switch alert exception: {e}")
        return False

    print()

    # Summary
    print("=" * 70)
    print("   ✅ TELEGRAM VALIDATION COMPLETE")
    print("=" * 70)
    print()
    print("All checks passed! Telegram is ready for DR drill.")
    print()
    print("Expected in your Telegram:")
    print("  1. Test message with timestamp")
    print("  2. Kill-switch simulation alert")
    print()
    print("Next steps:")
    print("  1. Confirm you received both messages in Telegram")
    print("  2. Continue with Binance testnet validation: python scripts/validate_binance.py")
    print("  3. Re-run pre-flight check: bash scripts/dr_drill_preflight.sh")
    print()

    return True


if __name__ == "__main__":
    try:
        success = validate_telegram()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
