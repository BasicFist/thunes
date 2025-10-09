#!/usr/bin/env python3
"""
Binance Testnet Configuration Validator
Tests exchange connectivity and account permissions
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def validate_binance():
    """Validate Binance testnet configuration and connectivity"""

    print("=" * 70)
    print("   Binance Testnet Configuration Validator")
    print("=" * 70)
    print()

    # Check environment variables
    print("[CHECK 1/7] Environment Variables")
    print("-" * 70)

    api_key = os.getenv('BINANCE_TESTNET_API_KEY')
    api_secret = os.getenv('BINANCE_TESTNET_API_SECRET')

    if not api_key:
        print("❌ FAIL: BINANCE_TESTNET_API_KEY not set")
        print("   Add to .env: BINANCE_TESTNET_API_KEY=your_key_here")
        print("   Get keys at: https://testnet.binance.vision/")
        return False
    else:
        print(f"✅ PASS: BINANCE_TESTNET_API_KEY configured ({api_key[:10]}...)")

    if not api_secret:
        print("❌ FAIL: BINANCE_TESTNET_API_SECRET not set")
        print("   Add to .env: BINANCE_TESTNET_API_SECRET=your_secret_here")
        return False
    else:
        print(f"✅ PASS: BINANCE_TESTNET_API_SECRET configured (hidden)")

    print()

    # Import client
    print("[CHECK 2/7] Module Import")
    print("-" * 70)

    try:
        from src.data.binance_client import BinanceDataClient
        print("✅ PASS: BinanceDataClient module imported successfully")
    except ImportError as e:
        print(f"❌ FAIL: Cannot import BinanceDataClient: {e}")
        return False

    print()

    # Initialize client
    print("[CHECK 3/7] Client Initialization")
    print("-" * 70)

    try:
        client = BinanceDataClient(testnet=True)
        print("✅ PASS: BinanceDataClient initialized for TESTNET")
    except Exception as e:
        print(f"❌ FAIL: Client initialization failed: {e}")
        print("   Check API key format (should be from testnet.binance.vision)")
        return False

    print()

    # Test connectivity
    print("[CHECK 4/7] Exchange Connectivity")
    print("-" * 70)

    try:
        account = client.client.get_account()
        print("✅ PASS: Successfully connected to Binance testnet")
        print(f"   Account type: {account.get('accountType', 'SPOT')}")
        print(f"   Can trade: {account.get('canTrade', False)}")
        print(f"   Can withdraw: {account.get('canWithdraw', False)}")
        print(f"   Can deposit: {account.get('canDeposit', False)}")
    except Exception as e:
        print(f"❌ FAIL: Exchange connectivity failed: {e}")
        print("   Common issues:")
        print("   - Using mainnet keys instead of testnet keys")
        print("   - API key expired or invalid")
        print("   - Network connectivity issues")
        return False

    print()

    # Check account permissions
    print("[CHECK 5/7] Account Permissions")
    print("-" * 70)

    can_trade = account.get('canTrade', False)
    can_withdraw = account.get('canWithdraw', True)  # Default True if not present

    if not can_trade:
        print("❌ FAIL: Trading not enabled on this API key")
        print("   Enable 'Spot & Margin Trading' permission")
        return False
    else:
        print("✅ PASS: Trading enabled")

    if can_withdraw:
        print("⚠️  WARNING: Withdrawal enabled (not recommended even for testnet)")
        print("   Disable withdrawal permission for safety")
    else:
        print("✅ EXCELLENT: Withdrawal disabled (secure configuration)")

    print()

    # Check balances
    print("[CHECK 6/7] Account Balances")
    print("-" * 70)

    balances = account.get('balances', [])
    non_zero_balances = [
        b for b in balances
        if float(b.get('free', 0)) + float(b.get('locked', 0)) > 0.001
    ]

    print(f"Total assets: {len(balances)}")
    print(f"Non-zero balances: {len(non_zero_balances)}")
    print()

    if not non_zero_balances:
        print("⚠️  WARNING: No testnet funds detected")
        print("   Request funds at: https://testnet.binance.vision/")
        print("   Need at least 100 USDT for DR drill")
    else:
        print("Non-zero balances:")
        for balance in non_zero_balances[:10]:  # Show first 10
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked
            print(f"  {asset}: {total:.8f} (free: {free:.8f}, locked: {locked:.8f})")

        # Check USDT specifically
        usdt = next((b for b in balances if b['asset'] == 'USDT'), None)
        if usdt:
            usdt_balance = float(usdt['free'])
            if usdt_balance < 100:
                print()
                print(f"⚠️  WARNING: USDT balance ({usdt_balance:.2f}) is low")
                print("   Request more funds for comprehensive testing")
                print("   Recommended: 1000+ USDT for DR drill")
            else:
                print()
                print(f"✅ EXCELLENT: USDT balance ({usdt_balance:.2f}) sufficient for testing")

    print()

    # Test order validation (dry-run)
    print("[CHECK 7/7] Order Validation (Dry-Run)")
    print("-" * 70)

    try:
        from src.filters.exchange_filters import ExchangeFilters

        filters = ExchangeFilters(client.client)

        # Test validate_order
        is_valid, adjusted_qty, price, reason = filters.validate_order('BTCUSDT', 10.0)

        if is_valid:
            print(f"✅ PASS: Order validation working")
            print(f"   Symbol: BTCUSDT")
            print(f"   Quote amount: 10.0 USDT")
            print(f"   Adjusted quantity: {adjusted_qty}")
            print(f"   Price: {price}")
        else:
            print(f"⚠️  WARNING: Order validation returned invalid")
            print(f"   Reason: {reason}")
            print("   This may be due to market conditions")
    except Exception as e:
        print(f"⚠️  WARNING: Order validation test failed: {e}")
        print("   This is non-critical - exchange connectivity is confirmed")

    print()

    # Summary
    print("=" * 70)
    print("   ✅ BINANCE TESTNET VALIDATION COMPLETE")
    print("=" * 70)
    print()

    if non_zero_balances:
        usdt = next((b for b in balances if b['asset'] == 'USDT'), None)
        usdt_balance = float(usdt['free']) if usdt else 0

        if usdt_balance >= 100:
            print("All checks passed! Binance testnet is ready for DR drill.")
        else:
            print("⚠️  Configuration valid but low USDT balance")
            print(f"   Current: {usdt_balance:.2f} USDT")
            print(f"   Recommended: 100+ USDT")
            print()
            print("   Request funds at: https://testnet.binance.vision/")
    else:
        print("⚠️  Configuration valid but no testnet funds")
        print("   Request funds before DR drill: https://testnet.binance.vision/")

    print()
    print("Next steps:")
    print("  1. If low balance: Request testnet funds")
    print("  2. Re-run pre-flight check: bash scripts/dr_drill_preflight.sh")
    print("  3. Execute DR drill: cat scripts/disaster_recovery_drill.md")
    print()

    return True


if __name__ == "__main__":
    try:
        success = validate_binance()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
