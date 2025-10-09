# Configuration Guide - Phase 13 Pre-Deployment

**Date**: 2025-10-09
**Status**: Pre-flight check failed - Configuration required
**Blockers**: 2 critical issues identified

---

## Pre-Flight Check Results

```
✓ Passed:   6/8
✗ Failed:   2/8
⚠ Warnings: 0

Critical Issues:
1. ❌ Telegram not configured
2. ❌ Exchange connectivity failed (API key format invalid)

Non-Critical:
- ⚠️  No open positions (can skip Test 1 or create position before drill)
```

---

## Required Fixes

### 1. Configure Telegram Bot (Required for Test 1)

**Purpose**: Telegram alerts verify kill-switch notifications in real-time

**Steps**:

1. **Create Telegram Bot** (if not done):
   - Open Telegram, search for `@BotFather`
   - Send `/newbot`
   - Follow prompts to create bot
   - Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Get Chat ID**:
   - Start a conversation with your bot
   - Send any message to the bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find `"chat":{"id":123456789}` in the response
   - Copy the numeric chat ID

3. **Add to .env**:
   ```bash
   # Open .env file
   nano .env

   # Add these lines:
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   ```

4. **Test Telegram**:
   ```bash
   source .venv/bin/activate
   python -c "
   from src.alerts.telegram import TelegramBot
   bot = TelegramBot()
   bot.send_message_sync('✅ Telegram configuration successful!')
   "
   ```

**Expected**: Message appears in your Telegram chat within 5 seconds

---

### 2. Fix Binance Testnet API Keys (Required for Tests 1 & 4)

**Current Error**: `APIError(code=-2014): API-key format invalid`

**Root Cause**: API keys are either:
- Not configured
- Configured for mainnet instead of testnet
- Expired or invalid format

**Steps**:

1. **Get Testnet API Keys**:
   - Visit: https://testnet.binance.vision/
   - Log in or create account (free testnet account)
   - Navigate to API Management
   - Create new API key
   - **IMPORTANT**: These are TESTNET keys (different from mainnet)

2. **Request Testnet Funds** (if needed):
   - After login, find the "Test Funds" section
   - Request USDT test funds (usually 1000 USDT)
   - Wait 1-2 minutes for funds to appear

3. **Configure API Keys**:
   ```bash
   # Open .env file
   nano .env

   # Add/update these lines:
   BINANCE_TESTNET_API_KEY=your_testnet_api_key_here
   BINANCE_TESTNET_API_SECRET=your_testnet_api_secret_here

   # Make sure these are TESTNET keys, not mainnet!
   ```

4. **Test Exchange Connectivity**:
   ```bash
   source .venv/bin/activate
   python -c "
   from src.data.binance_client import BinanceDataClient
   client = BinanceDataClient(testnet=True)
   account = client.client.get_account()
   print(f'✅ Connected to Binance Testnet')
   print(f'Can trade: {account[\"canTrade\"]}')

   # Check USDT balance
   usdt = next((b for b in account['balances'] if b['asset'] == 'USDT'), None)
   if usdt:
       balance = float(usdt['free'])
       print(f'USDT balance: {balance:.2f}')
       if balance < 100:
           print('⚠️  Low balance - request testnet funds at testnet.binance.vision')
   "
   ```

**Expected**:
```
✅ Connected to Binance Testnet
Can trade: True
USDT balance: 1000.00
```

---

### 3. Create Open Position (Optional - for Test 1)

**Current Status**: 0 open positions

**Options**:

**Option A: Skip Test 1** (Kill-switch activation)
- Start drill at Test 2 (Kill-switch deactivation)
- Manually activate kill-switch before starting
- Less comprehensive but still validates core procedures

**Option B: Create Position Before Drill**
```bash
source .venv/bin/activate

# Place small BUY order on testnet
python src/live/paper_trader.py \
    --symbol BTCUSDT \
    --side BUY \
    --amount 10

# Verify position created
python -c "
from src.models.position import PositionTracker
pt = PositionTracker()
count = pt.count_open_positions()
print(f'Open positions: {count}')
if count > 0:
    print('✅ Ready for DR drill Test 1')
"
```

---

## After Fixes: Re-Run Pre-Flight Check

```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate
bash scripts/dr_drill_preflight.sh
```

**Expected**: `✅ PRE-FLIGHT CHECK PASSED`

---

## Alternative: Dry-Run Mode (Not Recommended)

If you cannot configure Telegram or testnet keys immediately, you can execute a **partial dry-run**:

**What Works**:
- Test 2: Kill-switch deactivation (manual trigger)
- Test 3: Crash recovery (simulated kill -9)
- Partial Test 4: Position reconciliation (local state only)

**What Doesn't Work**:
- Test 1: Kill-switch activation (cannot verify Telegram alerts)
- Partial Test 4: Binance reconciliation (cannot compare with exchange)

**Command**:
```bash
# Activate kill-switch manually for Test 2
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
rm.activate_kill_switch('DRILL: Manual activation')
print('Kill-switch activated - ready for Test 2')
"

# Then follow Test 2-3 procedures in scripts/disaster_recovery_drill.md
```

**Limitations**:
- Cannot validate Telegram alerting (critical for production)
- Cannot validate exchange reconciliation (important for Phase 14)
- Deployment readiness only reaches ~65% (marginal)

**Recommendation**: Fix configuration issues for full validation (72% readiness)

---

## Troubleshooting

### Telegram Bot Not Responding

**Issue**: Bot created but no messages received

**Solutions**:
1. Verify bot token is correct (check for typos)
2. Ensure you started a conversation with the bot (send /start)
3. Check chat ID matches the one from getUpdates
4. Test with curl:
   ```bash
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \
        -d "chat_id=<CHAT_ID>&text=Test"
   ```

### Binance Testnet Connection Failed

**Issue**: API key format invalid

**Solutions**:
1. Verify using TESTNET keys (testnet.binance.vision), not mainnet
2. Check for whitespace or newlines in .env file
3. Regenerate API keys if expired
4. Ensure .env file has correct format (no quotes around values)

### No Testnet Funds

**Issue**: USDT balance is 0

**Solutions**:
1. Visit testnet.binance.vision while logged in
2. Find "Test Funds" or "Faucet" section
3. Request 1000 USDT (usually instant)
4. Wait 1-2 minutes and check balance again

---

## Security Reminders

**DO**:
- ✅ Use TESTNET API keys only
- ✅ Store keys in .env file (gitignored)
- ✅ Verify .env permissions: `chmod 600 .env`
- ✅ Keep Telegram bot token secure

**DON'T**:
- ❌ Use mainnet API keys for testing
- ❌ Commit .env file to git
- ❌ Share API keys or bot tokens publicly
- ❌ Enable withdrawal permissions (even on testnet)

---

## Quick Status Check

After configuration, verify all systems:

```bash
# Complete pre-flight check
bash scripts/dr_drill_preflight.sh

# Expected output:
# ✅ PRE-FLIGHT CHECK PASSED
# All prerequisites met for DR drill execution
```

---

## Next Steps After Configuration

Once pre-flight check passes:

1. **Review drill procedures** (5 min):
   ```bash
   cat DR_DRILL_QUICKSTART.md
   ```

2. **Execute drill** (2 hours):
   ```bash
   cat scripts/disaster_recovery_drill.md | less
   ```

3. **Document results** (30 min):
   - Fill in results in drill document
   - Update progress report
   - Commit results

4. **Deploy** (next day):
   - Follow deployment runbook
   - Execute post-deployment verification
   - Begin 7-day rodage

---

## Contact & Resources

**Setup Guides**:
- Binance Testnet: https://testnet.binance.vision/
- Telegram BotFather: Search @BotFather in Telegram
- getUpdates API: https://api.telegram.org/bot<TOKEN>/getUpdates

**Documentation**:
- DR Drill Guide: `docs/DR-DRILL-EXECUTION-GUIDE.md`
- Operational Runbook: `docs/OPERATIONAL-RUNBOOK.md`
- Deployment Checklist: `docs/PHASE-13-DEPLOYMENT-CHECKLIST.md`

**Support**:
- Pre-flight check: `bash scripts/dr_drill_preflight.sh`
- Logs: `tail -f logs/paper_trader.log`
- Audit trail: `tail -f logs/audit_trail.jsonl | jq '.'`

---

**Document Created**: 2025-10-09
**Status**: Configuration required before DR drill
**Priority**: P0 (Deployment blocker)
**Estimated Fix Time**: 15-30 minutes
