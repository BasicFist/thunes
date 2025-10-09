# Configuration Workflow - Phase 13 Pre-Deployment

**Date**: 2025-10-09
**Status**: Step-by-step configuration guide
**Time Required**: 30-40 minutes
**Goal**: Pass pre-flight check → Execute DR drill → Deploy Phase 13

---

## Overview

This workflow guides you through configuring prerequisites for the Disaster Recovery drill. Each step includes validation commands to verify success before proceeding.

**Current Status**: Pre-flight check failed (6/8 passed)

**Blockers**:
1. ❌ Telegram not configured
2. ❌ Binance testnet API keys invalid

**After this workflow**: ✅ Pre-flight check passed → Ready for DR drill

---

## Prerequisites

- [ ] Linux/macOS terminal access
- [ ] Internet connectivity
- [ ] Telegram account
- [ ] Email address (for Binance testnet)
- [ ] Text editor (nano, vim, or VSCode)

---

## Phase 1: Telegram Configuration (10-15 minutes)

### Step 1.1: Create Telegram Bot

**Action**: Open Telegram application

1. Search for **@BotFather** in Telegram
2. Start conversation
3. Send command: `/newbot`
4. Follow prompts:
   - Bot name: `THUNES Phase 13 Alert Bot` (or your choice)
   - Bot username: Must end in `bot` (e.g., `thunes_phase13_bot`)

**Expected Response**:
```
Done! Congratulations on your new bot...
Use this token to access the HTTP API:
123456789:ABCdefGHIjklMNOpqrsTUVwxyz

For a description of the Bot API, see this page: https://core.telegram.org/bots/api
```

**Action**: Copy the token (entire string with colon and everything after)

---

### Step 1.2: Get Chat ID

**Action**: Get your Telegram chat ID

1. Send any message to your bot (e.g., "Hello")
2. Open browser, visit (replace `<BOT_TOKEN>` with your token):
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```

**Expected Response** (JSON):
```json
{
  "ok": true,
  "result": [{
    "message": {
      "chat": {
        "id": 123456789,
        "first_name": "Your Name",
        "type": "private"
      }
    }
  }]
}
```

**Action**: Copy the `"id"` value (numeric only, e.g., `123456789`)

---

### Step 1.3: Configure .env File

**Action**: Add Telegram credentials to .env

```bash
cd ~/LAB/projects/THUNES

# Open .env file
nano .env

# Add these lines (replace with YOUR values):
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Save and exit (Ctrl+O, Enter, Ctrl+X in nano)
```

**Verification**: Check file was saved correctly
```bash
grep "TELEGRAM_" .env
```

**Expected**: Should see your token and chat ID (values will be visible - this is OK for testnet)

---

### Step 1.4: Test Telegram Configuration

**Action**: Run Telegram validation script

```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate
python scripts/validate_telegram.py
```

**Expected Output**:
```
[CHECK 1/5] Environment Variables
✅ PASS: TELEGRAM_BOT_TOKEN configured
✅ PASS: TELEGRAM_CHAT_ID configured

[CHECK 2/5] Module Import
✅ PASS: TelegramBot module imported successfully

[CHECK 3/5] Bot Initialization
✅ PASS: TelegramBot initialized successfully

[CHECK 4/5] Message Delivery Test
✅ PASS: Test message sent successfully
   Delivery time: 1.23 seconds

[CHECK 5/5] Kill-Switch Alert Simulation
✅ PASS: Kill-switch simulation alert sent
   Delivery time: 0.89 seconds
   ✅ Excellent: Alert delivered in <5s

✅ TELEGRAM VALIDATION COMPLETE
```

**Verification**: Check your Telegram app
- You should have received **2 messages**:
  1. Test message with timestamp
  2. Kill-switch simulation alert

**If Failed**: See troubleshooting section at end of document

**Checkpoint**: ✅ Telegram configured and validated

---

## Phase 2: Binance Testnet Configuration (15-20 minutes)

### Step 2.1: Create Testnet Account

**Action**: Visit Binance testnet

1. Open browser: https://testnet.binance.vision/
2. Click **"Register"** (top right)
3. Fill form:
   - Email: Your email address
   - Password: Strong password (save in password manager)
4. Verify email (check inbox/spam)
5. Complete login

**Verification**: You should see Binance testnet dashboard

---

### Step 2.2: Request Testnet Funds

**Action**: Get free USDT for testing

1. In testnet dashboard, find **"Test Funds"** or **"Faucet"**
   - Usually in top menu or right sidebar
2. Select **USDT**
3. Click **"Request"** or **"Get Testnet USDT"**
4. Wait 30-60 seconds

**Expected**: 1000 USDT credited to your testnet account

**Verification**: Check balances in dashboard
```
USDT: 1000.00000000
```

**If not found**: Look for "Assets" → "Spot" → "USDT"

---

### Step 2.3: Create API Keys

**Action**: Generate testnet API keys

1. In testnet dashboard, navigate to **"API Management"**
   - Usually under account icon or settings
2. Click **"Create API"** or **"Create New Key"**
3. Fill form:
   - Label: `THUNES Phase 13 Testing`
   - Permissions:
     - ✅ **Enable Reading** (required)
     - ✅ **Enable Spot & Margin Trading** (required)
     - ❌ **Enable Withdrawals** (NOT recommended)
4. Complete verification (email code, 2FA if enabled)
5. **CRITICAL**: Copy API Key and Secret Key immediately
   - API Key: Long alphanumeric string
   - Secret Key: Even longer alphanumeric string
   - **Save both** - Secret cannot be viewed again!

**Verification**: You should have:
- API Key (starts with letters, ~64 chars)
- Secret Key (very long, ~64+ chars)

---

### Step 2.4: Configure .env File

**Action**: Add Binance credentials to .env

```bash
cd ~/LAB/projects/THUNES

# Open .env file
nano .env

# Add these lines (replace with YOUR values):
BINANCE_TESTNET_API_KEY=your_api_key_here
BINANCE_TESTNET_API_SECRET=your_secret_key_here

# Save and exit (Ctrl+O, Enter, Ctrl+X in nano)
```

**CRITICAL VERIFICATION**: Ensure you're using TESTNET keys
```bash
# Check environment variable is set
grep "BINANCE_TESTNET_" .env

# Should see:
# BINANCE_TESTNET_API_KEY=...
# BINANCE_TESTNET_API_SECRET=...

# NOT mainnet keys (these should NOT exist for testnet):
# BINANCE_API_KEY=...     ← WRONG (mainnet)
# BINANCE_API_SECRET=...  ← WRONG (mainnet)
```

---

### Step 2.5: Test Binance Configuration

**Action**: Run Binance validation script

```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate
python scripts/validate_binance.py
```

**Expected Output**:
```
[CHECK 1/7] Environment Variables
✅ PASS: BINANCE_TESTNET_API_KEY configured
✅ PASS: BINANCE_TESTNET_API_SECRET configured

[CHECK 2/7] Module Import
✅ PASS: BinanceDataClient module imported successfully

[CHECK 3/7] Client Initialization
✅ PASS: BinanceDataClient initialized for TESTNET

[CHECK 4/7] Exchange Connectivity
✅ PASS: Successfully connected to Binance testnet
   Account type: SPOT
   Can trade: True
   Can withdraw: False

[CHECK 5/7] Account Permissions
✅ PASS: Trading enabled
✅ EXCELLENT: Withdrawal disabled

[CHECK 6/7] Account Balances
Non-zero balances:
  USDT: 1000.00000000 (free: 1000.00000000, locked: 0.00000000)
✅ EXCELLENT: USDT balance (1000.00) sufficient for testing

[CHECK 7/7] Order Validation (Dry-Run)
✅ PASS: Order validation working

✅ BINANCE TESTNET VALIDATION COMPLETE
```

**If Failed**: See troubleshooting section at end of document

**Checkpoint**: ✅ Binance testnet configured and validated

---

## Phase 3: Final Pre-Flight Check (5 minutes)

### Step 3.1: Run Complete Pre-Flight Check

**Action**: Verify all prerequisites are met

```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate
bash scripts/dr_drill_preflight.sh
```

**Expected Output**:
```
═══════════════════════════════════════════════════════════
   Disaster Recovery Drill - Pre-Flight Checklist
═══════════════════════════════════════════════════════════

[CHECK] Virtual environment activated... ✓ PASS
[CHECK] .env file exists... ✓ PASS
[CHECK] Required environment variables set... ✓ PASS

2. Telegram Bot Configuration
✅ Telegram bot operational
✅ Test message sent successfully

3. Exchange Connectivity
✅ Binance testnet connection active
   Can trade: True
   USDT balance: 1000.00

4. Position Tracker Operational
✅ Position tracker initialized
   Current open positions: 0
⚠️  No open positions - DR drill Test 1 requires at least one position

5. Risk Manager Operational
✅ Risk manager initialized

6. Audit Trail Setup
✓ PASS: Audit trail file exists and valid

7. Required Files Present
✓ PASS: All documentation files present

8. System Resources
✓ PASS: Disk space sufficient
✓ PASS: Memory available

═══════════════════════════════════════════════════════════
Pre-Flight Check Results:
  ✓ Passed:   8
  ✗ Failed:   0
  ⚠ Warnings: 1

✅ PRE-FLIGHT CHECK PASSED
═══════════════════════════════════════════════════════════

All prerequisites met for DR drill execution

Next steps:
1. Review the DR drill guide:
   cat scripts/disaster_recovery_drill.md
2. Execute the drill (2 hours)
3. After drill completion:
   - Update deployment readiness (51% → 72%)
   - Proceed with Phase 13 deployment
```

**Warning**: "No open positions" is non-critical. Options:
- **Option A**: Create position before drill (enables Test 1)
- **Option B**: Skip Test 1, proceed with Tests 2-4

**Checkpoint**: ✅ All systems ready for DR drill

---

## Phase 4: Create Test Position (Optional, 5 minutes)

**Required For**: Kill-switch activation test (Test 1)
**Skip If**: You want to test kill-switch deactivation only

### Step 4.1: Place Test Order

**Action**: Create small BUY position on testnet

```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate

# Place 10 USDT BUY order for BTCUSDT
python src/live/paper_trader.py --symbol BTCUSDT --side BUY --amount 10
```

**Expected Output**:
```
[INFO] Placing BUY order: BTCUSDT, 10.0 USDT
[INFO] Order filled: ...
[INFO] Position opened: BTCUSDT (BUY)
```

---

### Step 4.2: Verify Position Created

**Action**: Check position tracker

```bash
source .venv/bin/activate
python -c "
from src.models.position import PositionTracker
pt = PositionTracker()
count = pt.count_open_positions()
print(f'Open positions: {count}')

if count > 0:
    positions = pt.get_all_open_positions()
    for pos in positions:
        print(f\"  {pos['symbol']}: {pos['side']} {pos['quantity']} @ {pos['entry_price']}\")
    print('✅ Ready for DR drill Test 1 (kill-switch activation)')
else:
    print('No positions - will skip Test 1')
"
```

**Expected Output**:
```
Open positions: 1
  BTCUSDT: BUY 0.00015 @ 63254.50
✅ Ready for DR drill Test 1 (kill-switch activation)
```

**Checkpoint**: ✅ Test position created

---

## Phase 5: Execute DR Drill (2 hours)

**Prerequisites Complete**:
- ✅ Telegram configured and validated
- ✅ Binance testnet configured and validated
- ✅ Pre-flight check passed
- ✅ (Optional) Test position created

### Step 5.1: Review Drill Procedures

**Action**: Read quick-start guide

```bash
cat DR_DRILL_QUICKSTART.md
```

**Action**: Review comprehensive guide

```bash
cat docs/DR-DRILL-EXECUTION-GUIDE.md | less
```

---

### Step 5.2: Execute Drill

**Action**: Follow step-by-step procedures

```bash
cat scripts/disaster_recovery_drill.md | less
```

**Tests**:
1. **Kill-Switch Activation** (30 min) - Verify Telegram alerts, trade rejection
2. **Kill-Switch Deactivation** (30 min) - Runbook procedure validation
3. **Crash Recovery** (30 min) - Simulated kill -9, state recovery
4. **Position Reconciliation** (30 min) - Local vs Binance comparison

**Documentation**: Record results in drill document as you execute each test

---

### Step 5.3: Document Results

**Action**: Fill in drill summary

```bash
vi scripts/disaster_recovery_drill.md
# Navigate to "Post-Drill Summary" section
# Fill in all results tables
```

**Required Information**:
- Test results (PASS/FAIL for each of 4 tests)
- Duration for each test
- Issues encountered
- Key learnings
- Runbook updates required
- Action items

---

### Step 5.4: Update Progress Report

**Action**: Update deployment readiness

```bash
vi docs/PHASE-13-PREDEPLOYMENT-PROGRESS-2025-10-09.md
# Update "Disaster Recovery Dry-Run" section
# Change status from ⏳ PENDING to ✅ COMPLETE
# Add test results
```

---

### Step 5.5: Commit Results

**Action**: Save drill results to git

```bash
git add scripts/disaster_recovery_drill.md
git add docs/PHASE-13-PREDEPLOYMENT-PROGRESS-2025-10-09.md
git commit -m "docs: DR drill execution complete

Results:
- Test 1 (Kill-switch activation): [PASS/FAIL]
- Test 2 (Kill-switch deactivation): [PASS/FAIL]
- Test 3 (Crash recovery): [PASS/FAIL]
- Test 4 (Position reconciliation): [PASS/FAIL]

Overall: [X/4 tests passed]
Deployment readiness: 51% → 72%
Authorized for Phase 13 deployment: [YES/NO]"
```

---

## Success Criteria

**Pre-Flight Check**: ✅ 8/8 checks passed (0 warnings acceptable)

**DR Drill**:
- ✅ **PASS**: 4/4 or 3/4 tests passed → Deploy authorized (72% readiness)
- ⚠️ **REVIEW**: 2/4 tests passed → Review failures, decide deployment path
- ❌ **NO-GO**: ≤1/4 tests passed → Fix issues, re-run drill

---

## Troubleshooting

### Telegram Issues

**Problem**: Bot not receiving messages

**Solutions**:
1. Verify bot token has no typos:
   ```bash
   grep TELEGRAM_BOT_TOKEN .env
   # Should be: 123456789:ABCdef... (colon is critical)
   ```

2. Ensure you started conversation with bot:
   - Open bot in Telegram
   - Send `/start`
   - Send any message

3. Verify chat ID is numeric only:
   ```bash
   grep TELEGRAM_CHAT_ID .env
   # Should be: 123456789 (NO quotes, NO letters)
   ```

4. Test with curl:
   ```bash
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \
        -d "chat_id=<CHAT_ID>&text=Test"
   ```

---

### Binance Testnet Issues

**Problem**: API key format invalid

**Solutions**:
1. Verify using TESTNET keys (not mainnet):
   ```bash
   # Keys from testnet.binance.vision ✅
   # Keys from binance.com ❌
   ```

2. Check for whitespace in .env:
   ```bash
   cat -A .env | grep BINANCE
   # Should NOT see $, spaces, or newlines in keys
   ```

3. Regenerate API keys if needed:
   - Visit testnet.binance.vision
   - API Management → Delete old key → Create new key

4. Ensure correct environment variable names:
   ```bash
   # Correct for testnet:
   BINANCE_TESTNET_API_KEY=...
   BINANCE_TESTNET_API_SECRET=...

   # WRONG (mainnet variables):
   BINANCE_API_KEY=...
   BINANCE_API_SECRET=...
   ```

**Problem**: No testnet funds

**Solutions**:
1. Visit https://testnet.binance.vision/ while logged in
2. Find "Test Funds" or "Faucet" section
3. Request 1000 USDT
4. Wait 1-2 minutes, refresh balance

---

### Pre-Flight Check Still Failing

**Problem**: Configuration complete but check fails

**Solutions**:
1. Restart virtual environment:
   ```bash
   deactivate
   source .venv/bin/activate
   ```

2. Check .env file permissions:
   ```bash
   chmod 600 .env
   ls -la .env
   # Should show: -rw-------
   ```

3. Verify environment loaded:
   ```bash
   source .venv/bin/activate
   set | grep TELEGRAM
   set | grep BINANCE_TESTNET
   # Should see your configured values
   ```

4. Run individual validators:
   ```bash
   python scripts/validate_telegram.py
   python scripts/validate_binance.py
   ```

---

## Quick Reference

| Step | Component | Script | Expected Duration |
|------|-----------|--------|-------------------|
| 1 | Telegram setup | Manual | 10-15 min |
| 2 | Telegram validation | `python scripts/validate_telegram.py` | 1 min |
| 3 | Binance setup | Manual | 15-20 min |
| 4 | Binance validation | `python scripts/validate_binance.py` | 1 min |
| 5 | Pre-flight check | `bash scripts/dr_drill_preflight.sh` | 5 min |
| 6 | Create position (opt) | `python src/live/paper_trader.py` | 5 min |
| 7 | DR drill execution | Follow drill guide | 2 hours |
| 8 | Document results | Update markdown files | 30 min |

**Total**: 3-3.5 hours (configuration + drill + documentation)

---

## Next Steps After Completion

1. ✅ Configuration validated
2. ✅ Pre-flight check passed
3. ✅ DR drill executed (4/4 or 3/4 tests passed)
4. ✅ Results documented and committed

**You are now ready for Phase 13 deployment!**

**Deploy Tomorrow**:
1. Pre-deployment validation: `bash scripts/pre_deployment_validation.sh`
2. Follow deployment runbook: `docs/PHASE-13-DEPLOYMENT-RUNBOOK.md`
3. Post-deployment verification: `bash scripts/post_deployment_verification.sh`
4. Begin 7-day rodage monitoring

**Deployment Readiness**: 51% → 72% ✅

---

**Document Created**: 2025-10-09
**Last Updated**: 2025-10-09
**Status**: Complete step-by-step workflow
**Owner**: Deployment Team
