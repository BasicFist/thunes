# Disaster Recovery Drill - Phase 13 Pre-Deployment

**Date**: 2025-10-09
**Purpose**: Validate operational procedures documented in OPERATIONAL-RUNBOOK.md
**Duration**: ~2 hours
**Prerequisites**: System must be running on testnet

---

## Overview

This drill validates that disaster recovery procedures work as documented. Each test should be executed manually and results recorded.

**Tests**:
1. Kill-switch activation (manual trigger)
2. Kill-switch deactivation (runbook procedure)
3. Crash recovery (unclean shutdown)
4. Position reconciliation

---

## Test 1: Kill-Switch Manual Activation (30 minutes)

### Objective
Verify kill-switch can be manually triggered and behaves correctly.

### Prerequisites
- System running on testnet
- At least one open position (create if needed)
- Telegram bot configured

### Procedure

**Step 1: Record pre-test state**
```bash
# Check current system state
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

pt = PositionTracker()
rm = RiskManager(position_tracker=pt)

print('Pre-Test State')
print('=' * 50)
print(f'Kill-switch active: {rm.kill_switch_active}')
print(f'Daily P&L: {rm.get_daily_pnl()}')
print(f'Open positions: {pt.count_open_positions()}')
print(f'Risk status: {rm.get_risk_status()}')
"
```

**Expected output**:
```
Pre-Test State
==================================================
Kill-switch active: False
Daily P&L: -5.23
Open positions: 1
Risk status: {'kill_switch_active': False, ...}
```

**Step 2: Manually activate kill-switch**
```bash
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

pt = PositionTracker()
rm = RiskManager(position_tracker=pt)

print('Activating kill-switch manually...')
rm.activate_kill_switch('DRILL: Manual activation test')
print(f'Kill-switch active: {rm.kill_switch_active}')
"
```

**Expected output**:
```
Activating kill-switch manually...
[CRITICAL LOG] 🚨 KILL SWITCH ACTIVATED: DRILL: Manual activation test
Kill-switch active: True
```

**Step 3: Verify Telegram alert**
- Check Telegram for kill-switch notification
- Alert should arrive within 5 seconds
- Record actual delivery time: _____ seconds

**Step 4: Test trade rejection**
```bash
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

pt = PositionTracker()
rm = RiskManager(position_tracker=pt)

# Try to place BUY order (should be rejected)
is_valid, reason = rm.validate_trade('BTCUSDT', 100, 'BUY', 'test')
print(f'BUY order valid: {is_valid}')
print(f'Reason: {reason}')

# Try to place SELL order (should be allowed)
is_valid, reason = rm.validate_trade('BTCUSDT', 100, 'SELL', 'test')
print(f'SELL order valid: {is_valid}')
print(f'Reason: {reason}')
"
```

**Expected output**:
```
BUY order valid: False
Reason: ❌ Kill-switch is active. No new positions allowed.
SELL order valid: True
Reason: ✅ SELL orders allowed during kill-switch to close positions
```

**Step 5: Verify audit trail**
```bash
tail -5 logs/audit_trail.jsonl | jq '.'
```

**Expected**: Should see kill-switch activation event with:
- `event_type: "KILL_SWITCH_ACTIVATED"`
- `reason: "DRILL: Manual activation test"`
- Timestamp in ISO 8601 format

### Success Criteria
- [ ] Kill-switch activated successfully
- [ ] Telegram alert received within 5 seconds
- [ ] BUY orders rejected
- [ ] SELL orders allowed
- [ ] Audit trail logged correctly

### Results
- **Test Status**: [ ] PASS [ ] FAIL
- **Telegram Alert Delivery**: _____ seconds
- **Issues Encountered**: _____________________________________
- **Deviations from Runbook**: _____________________________________

---

## Test 2: Kill-Switch Deactivation (30 minutes)

### Objective
Verify kill-switch deactivation procedure from OPERATIONAL-RUNBOOK.md works correctly.

### Prerequisites
- Kill-switch currently active (from Test 1)

### Procedure

**Step 1: Review runbook procedure**
Open `docs/OPERATIONAL-RUNBOOK.md` and review kill-switch deactivation steps.

**Step 2: Verify kill-switch is active**
```bash
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

pt = PositionTracker()
rm = RiskManager(position_tracker=pt)
assert rm.kill_switch_active, 'Kill-switch not active!'
print('✅ Kill-switch is active, ready for deactivation test')
"
```

**Step 3: Execute deactivation procedure**
```bash
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

pt = PositionTracker()
rm = RiskManager(position_tracker=pt)

print('Deactivating kill-switch...')
rm.deactivate_kill_switch('DRILL: Manual deactivation test')
print(f'Kill-switch active: {rm.kill_switch_active}')
print(f'Risk status: {rm.get_risk_status()}')
"
```

**Expected output**:
```
Deactivating kill-switch...
[INFO LOG] 🔓 Kill-switch deactivated: DRILL: Manual deactivation test
Kill-switch active: False
Risk status: {'kill_switch_active': False, ...}
```

**Step 4: Verify trading enabled**
```bash
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

pt = PositionTracker()
rm = RiskManager(position_tracker=pt)

# BUY orders should now be allowed (subject to other limits)
is_valid, reason = rm.validate_trade('BTCUSDT', 100, 'BUY', 'test')
print(f'BUY order valid: {is_valid}')
print(f'Reason: {reason}')
"
```

**Expected output**:
```
BUY order valid: True
Reason: ✅ Trade validation passed
```

**Step 5: Verify audit trail**
```bash
tail -2 logs/audit_trail.jsonl | jq '.'
```

**Expected**: Should see deactivation event with:
- `event_type: "KILL_SWITCH_DEACTIVATED"`
- `reason: "DRILL: Manual deactivation test"`

### Success Criteria
- [ ] Kill-switch deactivated successfully
- [ ] Runbook procedure followed without errors
- [ ] Trading re-enabled (BUY orders allowed)
- [ ] Audit trail logged correctly
- [ ] No deviations from documented procedure

### Results
- **Test Status**: [ ] PASS [ ] FAIL
- **Time to Complete**: _____ minutes (expected: <5 minutes)
- **Issues Encountered**: _____________________________________
- **Runbook Accuracy**: [ ] Accurate [ ] Needs updates

---

## Test 3: Crash Recovery (30 minutes)

### Objective
Verify system recovers correctly from unclean shutdown (simulated with kill -9).

### Prerequisites
- System running on testnet
- At least one open position

### Procedure

**Step 1: Record pre-crash state**
```bash
python -c "
from src.models.position import PositionTracker
import json

pt = PositionTracker()
positions = pt.get_all_open_positions()

print('Pre-Crash State')
print('=' * 50)
print(f'Open positions: {len(positions)}')
for pos in positions:
    print(f'  Symbol: {pos[\"symbol\"]}, Side: {pos[\"side\"]}, Qty: {pos[\"quantity\"]}')

# Save state to file for comparison
with open('/tmp/pre_crash_state.json', 'w') as f:
    json.dump([dict(pos) for pos in positions], f, indent=2, default=str)

print('State saved to /tmp/pre_crash_state.json')
"
```

**Step 2: Check audit trail integrity**
```bash
# Count audit trail lines before crash
wc -l logs/audit_trail.jsonl
# Verify all lines are valid JSON
python -c "
import json
with open('logs/audit_trail.jsonl') as f:
    lines = f.readlines()
    for i, line in enumerate(lines, 1):
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            print(f'Line {i} is invalid JSON: {e}')
            exit(1)
print(f'✅ All {len(lines)} audit trail lines are valid JSON')
"
```

**Step 3: Simulate unclean shutdown**
```bash
# Find paper_trader process and kill it
pkill -9 -f paper_trader
# Or if running in foreground: Ctrl+Z, then kill -9 %1

echo "Simulated crash (kill -9) executed"
sleep 5
```

**Step 4: Restart system**
```bash
# Restart paper trader
cd ~/LAB/projects/THUNES
source .venv/bin/activate
python src/live/paper_trader.py --symbol BTCUSDT --side BUY --amount 100 &

echo "System restarted"
sleep 10
```

**Step 5: Verify state recovery**
```bash
python -c "
from src.models.position import PositionTracker
import json

pt = PositionTracker()
positions = pt.get_all_open_positions()

print('Post-Crash State')
print('=' * 50)
print(f'Open positions: {len(positions)}')
for pos in positions:
    print(f'  Symbol: {pos[\"symbol\"]}, Side: {pos[\"side\"]}, Qty: {pos[\"quantity\"]}')

# Compare with pre-crash state
with open('/tmp/pre_crash_state.json') as f:
    pre_crash = json.load(f)

if len(pre_crash) == len(positions):
    print('✅ Position count matches pre-crash state')
else:
    print(f'❌ Position count mismatch: {len(pre_crash)} → {len(positions)}')
"
```

**Step 6: Verify audit trail integrity**
```bash
# Count audit trail lines after crash
wc -l logs/audit_trail.jsonl
# Verify no corruption
python -c "
import json
with open('logs/audit_trail.jsonl') as f:
    lines = f.readlines()
    for i, line in enumerate(lines, 1):
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            print(f'Line {i} is CORRUPT: {e}')
            exit(1)
print(f'✅ All {len(lines)} audit trail lines are valid JSON (no corruption)')
"
```

### Success Criteria
- [ ] System restarts without errors
- [ ] Position state recovered correctly
- [ ] Audit trail integrity maintained (no corruption)
- [ ] No data loss in SQLite database
- [ ] Logs indicate clean recovery

### Results
- **Test Status**: [ ] PASS [ ] FAIL
- **Recovery Time**: _____ seconds
- **Data Loss**: [ ] None [ ] Minor [ ] Significant
- **Audit Trail Corruption**: [ ] None [ ] Detected
- **Issues Encountered**: _____________________________________

---

## Test 4: Position Reconciliation (30 minutes)

### Objective
Verify local position tracker matches actual Binance positions.

### Prerequisites
- System running on testnet
- Active positions on Binance testnet

### Procedure

**Step 1: Get local position state**
```bash
python -c "
from src.models.position import PositionTracker

pt = PositionTracker()
local_positions = pt.get_all_open_positions()

print('Local Position Tracker State')
print('=' * 50)
print(f'Total open positions: {len(local_positions)}')
for pos in local_positions:
    print(f'  {pos[\"symbol\"]}: {pos[\"side\"]} {pos[\"quantity\"]} @ {pos[\"entry_price\"]}')
" > /tmp/local_positions.txt
cat /tmp/local_positions.txt
```

**Step 2: Get Binance testnet positions**
```bash
python -c "
from src.data.binance_client import BinanceDataClient

client = BinanceDataClient()
account = client.client.get_account()

print('Binance Testnet Account State')
print('=' * 50)
balances = [b for b in account['balances'] if float(b['free']) + float(b['locked']) > 0]
print(f'Non-zero balances: {len(balances)}')
for balance in balances:
    asset = balance['asset']
    free = float(balance['free'])
    locked = float(balance['locked'])
    if free + locked > 0.001:  # Filter dust
        print(f'  {asset}: {free + locked:.8f} (free: {free:.8f}, locked: {locked:.8f})')
" > /tmp/binance_positions.txt
cat /tmp/binance_positions.txt
```

**Step 3: Manual reconciliation**
Compare the two outputs:
- Do local positions match Binance balances?
- Are there discrepancies?
- Document any differences

**Step 4: Run reconciliation script (if exists)**
```bash
if [ -f scripts/reconcile_positions.py ]; then
    python scripts/reconcile_positions.py
else
    echo "⚠️ Position reconciliation script not found"
    echo "Create scripts/reconcile_positions.py for automated reconciliation"
fi
```

### Success Criteria
- [ ] Local positions match Binance testnet
- [ ] No unexplained discrepancies
- [ ] Reconciliation process documented
- [ ] Automated reconciliation script exists (or created during drill)

### Results
- **Test Status**: [ ] PASS [ ] FAIL [ ] PARTIAL (script missing)
- **Discrepancies Found**: _____________________________________
- **Root Cause**: _____________________________________
- **Action Required**: _____________________________________

---

## Post-Drill Summary

### Overall Results
| Test | Status | Duration | Issues |
|------|--------|----------|--------|
| Kill-switch activation | [ ] PASS [ ] FAIL | _____ min | _____ |
| Kill-switch deactivation | [ ] PASS [ ] FAIL | _____ min | _____ |
| Crash recovery | [ ] PASS [ ] FAIL | _____ min | _____ |
| Position reconciliation | [ ] PASS [ ] FAIL | _____ min | _____ |

### Key Learnings
1. _____________________________________________________
2. _____________________________________________________
3. _____________________________________________________

### Runbook Updates Required
- [ ] Kill-switch procedures accurate
- [ ] Crash recovery procedures accurate
- [ ] Position reconciliation procedures need documentation
- [ ] Emergency contact information needs update

### Action Items
1. **Priority**: [ ] P0 [ ] P1 [ ] P2
   **Action**: _____________________________________________________
   **Owner**: _____________________________________________________
   **Due**: _____________________________________________________

2. **Priority**: [ ] P0 [ ] P1 [ ] P2
   **Action**: _____________________________________________________
   **Owner**: _____________________________________________________
   **Due**: _____________________________________________________

### Drill Completion
- **Start Time**: _____________________________________________________
- **End Time**: _____________________________________________________
- **Total Duration**: _____ hours
- **Participants**: _____________________________________________________
- **Approved By**: _____________________________________________________
- **Next Drill Date**: _____________________________________________________

---

## Appendix: Emergency Contacts

| Role | Name | Contact | Notes |
|------|------|---------|-------|
| Primary On-Call | __________ | __________ | Available 24/7 |
| Secondary On-Call | __________ | __________ | Backup |
| Binance Support | __________ | support@binance.com | Testnet: testnet@binance.com |
| Infrastructure | __________ | __________ | Server access |

---

**Document Created**: 2025-10-09
**Last Drill**: [Not yet executed]
**Next Drill**: [Schedule after Phase 13 deployment]
**Drill Frequency**: Monthly (Phase 13), Weekly (Phase 14)
