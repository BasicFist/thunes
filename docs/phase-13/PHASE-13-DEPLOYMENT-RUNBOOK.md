# Phase 13 Deployment Runbook
**Binance Spot Testnet - 7-Day Rodage**

**Version**: 1.0
**Date**: 2025-10-09
**Estimated Duration**: 30 minutes deployment + 7 days monitoring
**Risk Level**: 🟡 MEDIUM (testnet, no financial risk)

---

## Quick Reference

**Emergency Stop**: `pkill -9 -f scheduler && python -c "from src.risk.manager import RiskManager; from src.models.position import PositionTracker; RiskManager(position_tracker=PositionTracker()).activate_kill_switch('EMERGENCY')"`

**Graceful Shutdown**: `kill $(cat /tmp/scheduler.pid)`

**System Status**: `ps aux | grep scheduler && tail -20 logs/paper_trader.log`

---

## Pre-Deployment (T-Minus 30 minutes)

### Step 1: Pre-Flight Validation (5 minutes)

```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate

# Run comprehensive validation
bash scripts/pre_deployment_validation.sh
```

**Expected Output**:
```
✅ READY FOR DEPLOYMENT
```

**If validation fails**:
- Review errors in output
- Fix issues one by one
- Re-run validation
- Do NOT proceed until all checks pass

---

### Step 2: Final Environment Check (5 minutes)

```bash
# 1. Verify working directory
pwd
# Expected: ~/LAB/projects/THUNES

# 2. Check git status
git status
# Expected: "working tree clean" or only untracked files

# 3. Pull latest changes (if needed)
git pull origin main

# 4. Verify Python environment
python --version
# Expected: Python 3.10+ or 3.12

# 5. Activate virtual environment (if not already)
source .venv/bin/activate

# 6. Verify critical packages
pip list | grep -E "binance|apscheduler|pytest"
# Expected: python-binance 1.0.29, APScheduler 3.x, pytest 8.x
```

---

### Step 3: Configuration Review (5 minutes)

```bash
# Review .env configuration (without exposing secrets)
echo "=== Configuration Review ==="
grep "^ENVIRONMENT=" .env | head -c 50
grep "^MAX_DAILY_LOSS=" .env
grep "^MAX_POSITIONS=" .env
grep "^COOL_DOWN_MINUTES=" .env
grep "^DEFAULT_SYMBOL=" .env
grep "^DEFAULT_QUOTE_AMOUNT=" .env

# Expected values for Phase 13:
# ENVIRONMENT=testnet (or paper)
# MAX_DAILY_LOSS=20.0
# MAX_POSITIONS=3
# COOL_DOWN_MINUTES=60
# DEFAULT_SYMBOL=BTCUSDT
# DEFAULT_QUOTE_AMOUNT=10.0
```

**Review checklist**:
- [ ] Environment is testnet or paper (NOT production)
- [ ] MAX_DAILY_LOSS is reasonable ($20 USDT)
- [ ] MAX_POSITIONS is conservative (3 max)
- [ ] COOL_DOWN_MINUTES prevents rapid re-entry (60 min)
- [ ] DEFAULT_QUOTE_AMOUNT is small ($10 USDT)

---

### Step 4: Binance Testnet Connectivity (5 minutes)

```bash
# Test Binance testnet connection
python -c "
from src.data.binance_client import BinanceDataClient

client = BinanceDataClient(testnet=True)
account = client.client.get_account()

print('Binance Testnet Connection Test')
print('=' * 50)
print(f'Account Type: {account.get(\"accountType\")}')
print(f'Can Trade: {account.get(\"canTrade\")}')
print(f'Can Withdraw: {account.get(\"canWithdraw\")}')
print()

# Get balances
balances = [b for b in account['balances'] if float(b['free']) + float(b['locked']) > 0.001]
print(f'Non-zero Balances: {len(balances)}')
for b in balances[:5]:  # Show first 5
    asset = b['asset']
    total = float(b['free']) + float(b['locked'])
    print(f'  {asset}: {total:.4f}')

print()
print('✅ Binance testnet connection successful')
"
```

**Expected Output**:
```
Binance Testnet Connection Test
==================================================
Account Type: SPOT
Can Trade: True
Can Withdraw: False  # ✅ This should be False!
```

**If Can Withdraw is True**: ⚠️ **STOP DEPLOYMENT**
- This is a security issue
- API keys should have withdrawal disabled
- Regenerate keys with correct permissions

---

### Step 5: Telegram Alert Test (5 minutes)

```bash
# Test Telegram bot
python scripts/verify_telegram.py
```

**Expected Output**:
```
✅ Telegram bot configuration valid
📨 Test message sent successfully
⏱️ Delivery time: 1.23 seconds
```

**Check your Telegram**:
- [ ] Test message received within 5 seconds
- [ ] Message is readable and formatted correctly
- [ ] Bot name matches your configuration

**If Telegram fails**:
- Verify TELEGRAM_BOT_TOKEN in .env
- Verify TELEGRAM_CHAT_ID in .env
- Check bot permissions in Telegram
- Phase 13 can proceed without Telegram (optional but recommended)

---

### Step 6: Disaster Recovery Drill Confirmation (5 minutes)

**⚠️ DEPLOYMENT BLOCKER**: This must be completed before deployment

```bash
# Check if DR drill was executed
cat scripts/disaster_recovery_drill.md | grep "Test Status"
```

**Required**:
- [ ] Kill-switch activation test: **PASS**
- [ ] Kill-switch deactivation test: **PASS**
- [ ] Crash recovery test: **PASS**
- [ ] Position reconciliation test: **PASS** (or PARTIAL acceptable)

**If DR drill not executed**:
```bash
# Execute now (2 hours)
cat scripts/disaster_recovery_drill.md
# Follow step-by-step guide
# Record results in document
```

**Do NOT proceed to deployment until DR drill is complete**

---

## Deployment Execution (T-0)

### Step 7: Final Pre-Launch Checks (T-Minus 2 minutes)

```bash
# 1. Record deployment start time
date -u +"%Y-%m-%d %H:%M:%S UTC"

# 2. Create deployment log
mkdir -p logs/deployments
echo "Phase 13 Deployment: $(date -u)" > logs/deployments/phase13_$(date +%Y%m%d_%H%M%S).log

# 3. Verify no scheduler already running
ps aux | grep scheduler | grep -v grep
# Expected: No output (scheduler not running)

# 4. Clean any stale PID files
rm -f /tmp/scheduler.pid

# 5. Prepare monitoring terminal (optional but recommended)
# Open a second terminal for log monitoring:
# Terminal 2: tail -f logs/paper_trader.log
```

---

### Step 8: Launch Scheduler (T-0)

```bash
# Launch scheduler in background
nohup python -m src.orchestration.run_scheduler > logs/scheduler_stdout.log 2>&1 &

# Capture process ID
echo $! > /tmp/scheduler.pid

# Verify scheduler started
sleep 5
ps -p $(cat /tmp/scheduler.pid) > /dev/null && echo "✅ Scheduler running (PID: $(cat /tmp/scheduler.pid))" || echo "❌ Scheduler failed to start"
```

**Expected Output**:
```
✅ Scheduler running (PID: 12345)
```

**If scheduler fails to start**:
```bash
# Check error logs
cat logs/scheduler_stdout.log
tail -50 logs/paper_trader.log

# Common issues:
# - Import errors: Missing dependencies
# - Config errors: Invalid .env settings
# - Permission errors: logs/ directory not writable
```

---

### Step 9: Initial Verification (T+5 minutes)

```bash
# 1. Verify scheduler process alive
ps -p $(cat /tmp/scheduler.pid)
# Expected: Process running

# 2. Check logs for startup messages
tail -30 logs/paper_trader.log
# Expected: "Scheduler started", "Trading enabled", no critical errors

# 3. Verify kill-switch inactive
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
print(f'Kill-switch active: {rm.kill_switch_active}')
print(f'Risk status: {rm.get_risk_status()}')
"
# Expected: kill_switch_active = False

# 4. Check for immediate errors
grep -i "critical\|error" logs/paper_trader.log | tail -10
# Expected: No critical errors (warnings OK)

# 5. Verify Telegram startup notification (if configured)
# Check Telegram for deployment start message
```

**Success Criteria (T+5)**:
- [ ] Scheduler process running
- [ ] No critical errors in logs
- [ ] Kill-switch inactive
- [ ] Telegram notification received (if configured)

---

### Step 10: Send Deployment Notification (T+5 minutes)

```bash
# Send manual deployment notification
python -c "
from src.alerts.telegram import TelegramBot
import datetime

bot = TelegramBot()
if bot.enabled:
    message = f'''
🚀 **Phase 13 Deployment Started**

Deployment Time: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}
Environment: Binance Spot Testnet
Duration: 7-day rodage
Risk Limits:
  - Max Daily Loss: \$20 USDT
  - Max Positions: 3
  - Cool-down: 60 minutes

Status: Monitoring active
Next Check: {(datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M UTC')}
'''
    bot.send_message_sync(message)
    print('✅ Deployment notification sent')
else:
    print('⚠️ Telegram not configured - notification skipped')
"
```

---

## Post-Deployment Monitoring

### First Hour Monitoring (T+0 to T+60 minutes)

**Check every 10 minutes**:

```bash
# Quick health check script
cat > /tmp/health_check.sh <<'EOF'
#!/bin/bash
echo "=== THUNES Health Check: $(date) ==="
echo ""

# 1. Scheduler running?
if ps -p $(cat /tmp/scheduler.pid 2>/dev/null) > /dev/null 2>&1; then
    echo "✅ Scheduler: Running (PID: $(cat /tmp/scheduler.pid))"
else
    echo "❌ Scheduler: NOT RUNNING"
fi

# 2. Memory usage
MEM=$(ps aux | grep scheduler | grep -v grep | awk '{print $6/1024 " MB"}')
echo "📊 Memory: $MEM"

# 3. Recent errors
ERRORS=$(grep -i "error\|critical" logs/paper_trader.log | tail -1)
if [ -z "$ERRORS" ]; then
    echo "✅ Errors: None"
else
    echo "⚠️ Recent error: $ERRORS"
fi

# 4. Open positions
POSITIONS=$(python -c "from src.models.position import PositionTracker; print(PositionTracker().count_open_positions())" 2>/dev/null)
echo "📈 Open Positions: $POSITIONS/3"

# 5. Kill-switch status
KILLSWITCH=$(python -c "from src.risk.manager import RiskManager; from src.models.position import PositionTracker; print(RiskManager(position_tracker=PositionTracker()).kill_switch_active)" 2>/dev/null)
echo "🚨 Kill-switch: $KILLSWITCH"

echo ""
EOF

chmod +x /tmp/health_check.sh

# Run every 10 minutes
watch -n 600 /tmp/health_check.sh
```

**T+10, T+20, T+30, T+40, T+50, T+60 minute checks**:
- [ ] Scheduler still running
- [ ] Memory usage <500 MB
- [ ] No critical errors
- [ ] Positions within limits (≤3)
- [ ] Kill-switch inactive

---

### First 24 Hours Monitoring

**Twice daily checks** (9 AM, 6 PM local time):

```bash
# Morning check (9 AM)
echo "=== Morning Health Check: $(date) ==="

# 1. Overnight stability
bash /tmp/health_check.sh

# 2. Trading activity
python -c "
from src.models.position import PositionTracker
pt = PositionTracker()
positions = pt.get_all_open_positions()
closed = pt.get_closed_positions_today()

print(f'Overnight Activity:')
print(f'  Open positions: {len(positions)}')
print(f'  Closed today: {len(closed)}')
"

# 3. P&L calculation
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
pnl = rm.get_daily_pnl()
print(f'Daily P&L: \${pnl:.2f} USDT')
"

# 4. Log file sizes
du -h logs/*.log
# Expected: paper_trader.log <50 MB, audit_trail.jsonl <1 MB

# 5. WebSocket stability
grep -i "websocket\|reconnect" logs/paper_trader.log | tail -5
# Expected: <5 reconnections per day
```

**Evening check (6 PM)**:
- Same checks as morning
- Review day's trading summary
- Document any issues in deployment log

---

### 7-Day Rodage Monitoring

**Daily routine** (15 minutes/day):

1. **Morning (9 AM)**:
   ```bash
   bash /tmp/health_check.sh
   python scripts/generate_daily_report.py  # If exists
   ```

2. **Evening (6 PM)**:
   ```bash
   # Calculate day's metrics
   python -c "
   from src.models.position import PositionTracker
   from src.risk.manager import RiskManager

   pt = PositionTracker()
   rm = RiskManager(position_tracker=pt)

   closed_today = pt.get_closed_positions_today()
   winning = [p for p in closed_today if p['pnl'] > 0]

   print(f'Day Summary:')
   print(f'  Trades: {len(closed_today)}')
   print(f'  Wins: {len(winning)}')
   print(f'  Win Rate: {len(winning)/len(closed_today)*100 if closed_today else 0:.1f}%')
   print(f'  Daily P&L: \${rm.get_daily_pnl():.2f}')
   "
   ```

3. **Weekly summary** (Day 7):
   ```bash
   # Generate comprehensive report
   python scripts/generate_rodage_report.py  # Create this if needed
   ```

---

## Troubleshooting

### Common Issues

#### Scheduler Stops Unexpectedly

**Symptoms**: Process not in `ps aux`, logs show unexpected termination

**Diagnosis**:
```bash
# Check exit reason
tail -100 logs/paper_trader.log | grep -i "exit\|stop\|shutdown"

# Check system logs
journalctl -u thunes --since "1 hour ago"  # If systemd
```

**Resolution**:
```bash
# Restart scheduler
nohup python -m src.orchestration.run_scheduler > logs/scheduler_stdout.log 2>&1 &
echo $! > /tmp/scheduler.pid

# Monitor for stability
watch -n 60 "ps -p $(cat /tmp/scheduler.pid)"
```

---

#### Kill-Switch Activates Unexpectedly

**Symptoms**: Trading stops, logs show kill-switch activation

**Diagnosis**:
```bash
# Check audit trail for trigger
grep "KILL_SWITCH_ACTIVATED" logs/audit_trail.jsonl | tail -5 | jq '.'

# Check daily P&L
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
print(f'Daily P&L: {rm.get_daily_pnl()}')
print(f'Max daily loss: {rm.max_daily_loss}')
"
```

**Resolution**:
```bash
# If legitimate (daily loss exceeded), deactivate manually after review:
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
rm.deactivate_kill_switch('Manual reset after review')
"

# If false positive, investigate and fix trigger condition
```

---

#### High Memory Usage

**Symptoms**: Memory >1 GB, system sluggish

**Diagnosis**:
```bash
# Check memory usage over time
ps aux | grep scheduler | awk '{print $6/1024 " MB"}'

# Check for memory leaks
watch -n 60 "ps aux | grep scheduler | awk '{print \$6/1024 \" MB\"}'"
```

**Resolution**:
```bash
# Graceful restart
kill $(cat /tmp/scheduler.pid)
sleep 10
nohup python -m src.orchestration.run_scheduler > logs/scheduler_stdout.log 2>&1 &
echo $! > /tmp/scheduler.pid
```

---

#### WebSocket Frequent Reconnections

**Symptoms**: >10 reconnections/day in logs

**Diagnosis**:
```bash
# Count reconnections
grep -i "reconnect" logs/paper_trader.log | wc -l

# Check network stability
ping -c 10 testnet.binance.vision
```

**Resolution**:
- If network issue: Check firewall, VPN, ISP
- If code issue: Review WebSocket implementation
- If Binance issue: Wait for service stabilization

---

## Emergency Procedures

### Emergency Stop (Immediate)

**When to use**: Critical bug, rapid loss, system instability

```bash
# 1. Kill all processes immediately
pkill -9 -f scheduler
pkill -9 -f paper_trader

# 2. Activate kill-switch
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
rm.activate_kill_switch('EMERGENCY STOP: Critical issue detected')
print('✅ Kill-switch activated')
"

# 3. Close all open positions
python scripts/close_all_positions.py  # If exists

# 4. Send alert
python -c "
from src.alerts.telegram import TelegramBot
bot = TelegramBot()
if bot.enabled:
    bot.send_message_sync('🚨 EMERGENCY STOP EXECUTED 🚨\n\nAll trading halted. Manual review required.')
"

# 5. Document incident
echo "$(date -u): EMERGENCY STOP - Reason: [DOCUMENT REASON]" >> logs/incidents.log
```

---

### Graceful Shutdown (Planned)

**When to use**: Maintenance, updates, planned downtime

```bash
# 1. Activate kill-switch to stop new trades
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
rm.activate_kill_switch('PLANNED MAINTENANCE')
"

# 2. Wait for positions to close (or close manually)
python -c "
from src.models.position import PositionTracker
pt = PositionTracker()
open_count = pt.count_open_positions()
print(f'Waiting for {open_count} positions to close...')
"

# 3. Stop scheduler gracefully
kill $(cat /tmp/scheduler.pid)  # SIGTERM, not SIGKILL

# 4. Verify clean shutdown
sleep 10
ps -p $(cat /tmp/scheduler.pid) || echo "✅ Scheduler stopped cleanly"

# 5. Document shutdown
echo "$(date -u): Graceful shutdown for maintenance" >> logs/maintenance.log
```

---

## Success Criteria

### Deployment Success (Day 1)

- [ ] Scheduler running continuously for 24 hours
- [ ] No critical errors in logs
- [ ] Kill-switch only activated on demand (test)
- [ ] Memory usage <1 GB
- [ ] Telegram alerts functioning

### Rodage Success (Day 7)

- [ ] All Tier 1 metrics passed (100%)
- [ ] All Tier 2 metrics acceptable (>80%)
- [ ] Zero unplanned restarts
- [ ] <3 manual interventions required
- [ ] Position reconciliation accurate daily

### Phase 14 Readiness

- [ ] 7-day rodage completed successfully
- [ ] Technical debt addressed (mypy, datetime)
- [ ] Operational confidence high
- [ ] Team comfortable with procedures
- [ ] Ready for live trading with $10-50

---

## Post-Deployment Checklist

After 7 days, complete this checklist:

- [ ] Generate final rodage report
- [ ] Document all incidents and resolutions
- [ ] Update OPERATIONAL-RUNBOOK.md with lessons learned
- [ ] Review and update risk parameters if needed
- [ ] Phase 14 GO/NO-GO decision documented
- [ ] Deployment artifacts archived

---

**Runbook Version**: 1.0
**Last Updated**: 2025-10-09
**Next Review**: After Phase 13 completion
**Owner**: Deployment Team
