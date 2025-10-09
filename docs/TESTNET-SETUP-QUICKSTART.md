# Binance Testnet Quick Setup Guide

## 🚨 IMMEDIATE ACTION REQUIRED

Your system is configured but needs valid Binance Testnet API credentials to begin Phase 13 rodage.

## Step 1: Get Testnet API Keys (2 minutes)

1. **Open Browser**: https://testnet.binance.vision/
2. **Click**: "Generate HMAC_SHA256 Key" button
3. **Save Both**:
   - API Key (64 characters)
   - Secret Key (64 characters)
4. **Optional**: Click "Get Faucet" for test BTC/USDT

## Step 2: Update Credentials (1 minute)

### Option A: Use Setup Script (Recommended)
```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate
python scripts/setup_testnet_credentials.py
```

### Option B: Manual Update
```bash
# Edit .env file
nano .env

# Update these lines (replace with your actual keys):
BINANCE_TESTNET_API_KEY="your_64_character_api_key_here"
BINANCE_TESTNET_API_SECRET="your_64_character_secret_here"

# Optional Telegram alerts:
TELEGRAM_BOT_TOKEN="your_bot_token"  # From @BotFather
TELEGRAM_CHAT_ID="your_chat_id"      # From @userinfobot
```

## Step 3: Verify Connection (30 seconds)

```bash
# Test API connection
source .venv/bin/activate
python -c "
from src.data.binance_client import BinanceDataClient
client = BinanceDataClient()
account = client.client.get_account()
print('✅ Connected! Can trade:', account.get('canTrade'))
"

# Check balance
make balance
```

## Step 4: Get Test Funds (1 minute)

If no balance:
1. Go to: https://testnet.binance.vision/
2. Click "Get Faucet" button
3. Select BTC and USDT
4. Submit request
5. Wait ~30 seconds
6. Run `make balance` to verify

## Step 5: Launch Rodage (Ready in 5 minutes!)

Once credentials are configured:

```bash
# Final pre-launch check
make test  # Verify 203+ tests pass

# Launch 24/7 scheduler
screen -S thunes-rodage
source .venv/bin/activate
python src/orchestration/run_scheduler.py

# Detach screen (keeps running)
# Press: Ctrl+A, then D

# Monitor logs
tail -f logs/paper_trader.log
```

## ⚠️ CRITICAL REMINDERS

1. **USE TESTNET ONLY**: Never use production API keys during rodage
2. **NO REAL MONEY**: Testnet uses fake funds only
3. **MONITOR DAILY**: Check twice per day per rodage checklist
4. **7-DAY MINIMUM**: Full week required before Phase 14

## Troubleshooting

**"API-key format invalid" Error**:
- Ensure keys are from testnet.binance.vision (NOT binance.com)
- Check for extra spaces or quotes in .env file
- Keys should be exactly 64 alphanumeric characters

**"No balance" After Faucet**:
- Wait 1-2 minutes for faucet to process
- Try different assets (ETH, BNB if BTC/USDT fail)
- Check testnet status: https://testnet.binance.vision/

**Connection Timeouts**:
- Verify internet connectivity
- Check if testnet is under maintenance
- Try again in 5 minutes

## Current System Status

✅ **Phase 13 Ready** (203/225 tests passing - 90.2%)
✅ **Risk Management**: Kill-switch, position limits, audit trail
✅ **CI/CD**: Enforced quality gates
✅ **Documentation**: Rodage checklist prepared

⏳ **Waiting For**: Valid API credentials to begin

---
Generated: 2025-10-07
Next: Configure credentials and launch scheduler