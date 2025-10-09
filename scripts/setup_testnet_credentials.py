#!/usr/bin/env python3
"""Interactive setup for Binance Testnet API credentials."""

import os
import sys
from pathlib import Path
from getpass import getpass
import re

def validate_api_key(key: str) -> bool:
    """Validate API key format (64 character alphanumeric)."""
    return bool(re.match(r'^[A-Za-z0-9]{64}$', key))

def validate_api_secret(secret: str) -> bool:
    """Validate API secret format (64 character alphanumeric)."""
    return bool(re.match(r'^[A-Za-z0-9]{64}$', secret))

def main():
    print("\n" + "="*60)
    print("BINANCE TESTNET API CREDENTIALS SETUP")
    print("="*60)

    print("\n📌 To get testnet API keys:")
    print("1. Go to: https://testnet.binance.vision/")
    print("2. Click 'Generate HMAC_SHA256 Key'")
    print("3. Save both the API Key and Secret Key")
    print("4. Optional: Get test funds using 'Get Faucet' button\n")

    # Check if .env exists
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found. Creating from template...")
        template = Path(".env.template")
        if template.exists():
            import shutil
            shutil.copy(template, env_file)
            print("✅ Created .env from template")
        else:
            print("❌ No .env.template found. Please create .env manually.")
            sys.exit(1)

    # Get current values
    current_env = {}
    with open(env_file, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                current_env[key] = value.strip('"').strip("'")

    print("\n" + "-"*60)
    print("CURRENT CONFIGURATION:")
    print("-"*60)

    current_key = current_env.get('BINANCE_TESTNET_API_KEY', '')
    current_secret = current_env.get('BINANCE_TESTNET_API_SECRET', '')

    if current_key and current_key != 'placeholder_testnet_key':
        print(f"✅ API Key configured: {current_key[:8]}...{current_key[-4:]}")
    else:
        print("⚠️  API Key not configured (using placeholder)")

    if current_secret and current_secret != 'placeholder_testnet_secret':
        print(f"✅ Secret configured: {'*' * 60}")
    else:
        print("⚠️  Secret not configured (using placeholder)")

    # Get Telegram settings
    telegram_token = current_env.get('TELEGRAM_BOT_TOKEN', '')
    telegram_chat = current_env.get('TELEGRAM_CHAT_ID', '')

    if telegram_token:
        print(f"✅ Telegram Bot Token: {telegram_token[:8]}...{telegram_token[-4:]}")
    else:
        print("ℹ️  Telegram Bot Token: Not configured (optional)")

    if telegram_chat:
        print(f"✅ Telegram Chat ID: {telegram_chat}")
    else:
        print("ℹ️  Telegram Chat ID: Not configured (optional)")

    # Ask if they want to update
    print("\n" + "-"*60)
    response = input("\nDo you want to update the API credentials? (yes/no): ").strip().lower()

    if response not in ['yes', 'y']:
        print("✅ Configuration unchanged.")
        return

    # Get new credentials
    print("\n" + "-"*60)
    print("ENTER NEW CREDENTIALS:")
    print("-"*60)

    while True:
        api_key = input("\n📝 Enter Binance Testnet API Key (64 chars): ").strip()
        if validate_api_key(api_key):
            break
        print("❌ Invalid format. API key should be 64 alphanumeric characters.")

    while True:
        api_secret = getpass("🔒 Enter Binance Testnet API Secret (64 chars): ").strip()
        if validate_api_secret(api_secret):
            break
        print("❌ Invalid format. Secret should be 64 alphanumeric characters.")

    # Optional: Telegram setup
    print("\n" + "-"*60)
    print("TELEGRAM ALERTS (Optional):")
    print("-"*60)
    setup_telegram = input("\nSetup Telegram alerts? (yes/no): ").strip().lower()

    if setup_telegram in ['yes', 'y']:
        print("\n📌 To get Telegram credentials:")
        print("1. Create bot with @BotFather on Telegram")
        print("2. Get your chat ID with @userinfobot")

        telegram_token = input("\n📝 Enter Telegram Bot Token (or press Enter to skip): ").strip()
        telegram_chat = input("📝 Enter Telegram Chat ID (or press Enter to skip): ").strip()

    # Update .env file
    print("\n" + "-"*60)
    print("UPDATING CONFIGURATION...")
    print("-"*60)

    # Read all lines
    with open(env_file, 'r') as f:
        lines = f.readlines()

    # Update values
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('BINANCE_TESTNET_API_KEY='):
            lines[i] = f'BINANCE_TESTNET_API_KEY="{api_key}"\n'
            updated = True
        elif line.startswith('BINANCE_TESTNET_API_SECRET='):
            lines[i] = f'BINANCE_TESTNET_API_SECRET="{api_secret}"\n'
            updated = True
        elif setup_telegram in ['yes', 'y']:
            if telegram_token and line.startswith('TELEGRAM_BOT_TOKEN='):
                lines[i] = f'TELEGRAM_BOT_TOKEN="{telegram_token}"\n'
            elif telegram_chat and line.startswith('TELEGRAM_CHAT_ID='):
                lines[i] = f'TELEGRAM_CHAT_ID="{telegram_chat}"\n'

    # Write back
    with open(env_file, 'w') as f:
        f.writelines(lines)

    if updated:
        print("✅ Configuration updated successfully!")
    else:
        print("⚠️  Could not find keys to update. Please check .env manually.")

    # Test connection
    print("\n" + "-"*60)
    print("TESTING CONNECTION...")
    print("-"*60)

    try:
        # Force reload of settings
        import importlib
        import src.config
        importlib.reload(src.config)

        from src.data.binance_client import BinanceDataClient
        client = BinanceDataClient()

        # Test account access
        account = client.client.get_account()
        print("✅ Successfully connected to Binance Testnet!")
        print(f"   Can Trade: {account.get('canTrade', False)}")

        # Check balances
        balances = [b for b in account.get('balances', [])
                   if float(b.get('free', 0)) > 0 or float(b.get('locked', 0)) > 0]

        if balances:
            print("\n💰 Testnet Balances:")
            for bal in balances[:5]:
                total = float(bal['free']) + float(bal['locked'])
                if total > 0:
                    print(f"   {bal['asset']}: {bal['free']} free, {bal['locked']} locked")
        else:
            print("\n⚠️  No testnet balance found.")
            print("   Get test funds at: https://testnet.binance.vision/")
            print("   Click 'Get Faucet' to receive test BTC and USDT")

        # Test Telegram if configured
        if telegram_token:
            print("\n" + "-"*60)
            print("TESTING TELEGRAM...")
            print("-"*60)
            from src.alerts.telegram import TelegramBot
            bot = TelegramBot()
            success = bot.send_message_sync("🚀 THUNES Testnet Setup Complete! Ready for Phase 13 rodage.")
            if success:
                print("✅ Telegram alert sent successfully!")
            else:
                print("⚠️  Could not send Telegram message. Check credentials.")

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        print("\nPlease verify:")
        print("1. API keys are from testnet.binance.vision (not production)")
        print("2. Keys are correctly copied (no extra spaces)")
        print("3. Internet connection is working")

    print("\n" + "="*60)
    print("SETUP COMPLETE")
    print("="*60)
    print("\nNext step: Run 'make paper' to test a single paper trade")
    print("Then: Launch scheduler for 24/7 rodage")
    print("")

if __name__ == "__main__":
    main()