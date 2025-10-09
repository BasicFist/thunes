# Phase 13 Testnet Deployment Checklist

**Version**: 1.0
**Date**: 2025-10-09
**Target Environment**: Binance Spot Testnet
**Deployment Type**: 7-Day Rodage (Continuous Operation)
**Risk Level**: 🟡 MEDIUM (testnet, no financial risk)

---

## Pre-Deployment Checklist

### A. Environment Validation ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

- [ ] **Python Environment**
  ```bash
  python --version  # Should be 3.10+
  source .venv/bin/activate
  pip list | grep -E "binance|vectorbt|pytest"
  ```
  Expected: python-binance 1.0.29, vectorbt 0.28.1, pytest 8.4.2

- [ ] **.env Configuration**
  ```bash
  test -f .env && echo "✅ .env exists" || echo "❌ Missing"
  chmod 600 .env  # Secure permissions
  ```
  Required variables:
  - `BINANCE_TESTNET_API_KEY=________`
  - `BINANCE_TESTNET_API_SECRET=________`
  - `TELEGRAM_BOT_TOKEN=________`
  - `TELEGRAM_CHAT_ID=________`
  - `MAX_DAILY_LOSS=20.0`
  - `MAX_POSITIONS=3`
  - `COOL_DOWN_MINUTES=60`

- [ ] **Git Status Clean**
  ```bash
  git status
  # Should show: "working tree clean" or only untracked files
  ```

- [ ] **Latest Code Pulled**
  ```bash
  git pull origin main
  git log -1 --oneline
  # Should show recent audit commits
  ```

---

### B. Security Validation ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

- [ ] **No Secrets in Git History**
  ```bash
  git log --all --full-history -- .env | wc -l
  # Expected: 0
  ```

- [ ] **API Key Permissions** (Testnet)
  ```bash
  python scripts/validate_api_permissions.py
  # Expected: canTrade=true, canWithdraw=false
  ```

- [ ] **Telegram Alerts Working**
  ```bash
  python scripts/verify_telegram.py
  # Expected: Test message received within 5 seconds
  ```

- [ ] **.env File Permissions**
  ```bash
  ls -la .env
  # Expected: -rw------- (600 permissions)
  ```

---

### C. Code Quality Validation ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

- [ ] **Critical Tests Passing**
  ```bash
  pytest tests/test_risk_manager.py tests/test_filters.py -v
  # Expected: 50/50 tests passing (100%)
  ```

- [ ] **Concurrency Tests Passing**
  ```bash
  pytest tests/test_risk_manager_concurrent.py -v
  # Expected: 12/12 tests passing (100%)
  ```

- [ ] **Circuit Breaker Tests Passing**
  ```bash
  pytest tests/test_circuit_breaker.py -v
  # Expected: 14/14 tests passing (100%)
  ```

- [ ] **Linting Passes**
  ```bash
  ruff check src/ --select=E,F,W
  # Expected: No critical errors
  ```

---

### D. Disaster Recovery Validation ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

**⚠️ DEPLOYMENT BLOCKER**: Must complete before deployment

- [ ] **DR Drill Executed**
  ```bash
  # Follow: scripts/disaster_recovery_drill.md
  # Record results in drill document
  ```
  Tests completed:
  - [ ] Kill-switch activation (30 min)
  - [ ] Kill-switch deactivation (30 min)
  - [ ] Crash recovery (30 min)
  - [ ] Position reconciliation (30 min)

- [ ] **All DR Tests Passed**
  Document any failures: ________________________________

- [ ] **Runbook Updated**
  - [ ] Kill-switch procedures accurate
  - [ ] Crash recovery steps validated
  - [ ] Position reconciliation documented

---

### E. Operational Readiness ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

- [ ] **Monitoring Setup**
  - [ ] Logs directory exists: `mkdir -p logs`
  - [ ] Audit trail initialized: `touch logs/audit_trail.jsonl`
  - [ ] Log rotation configured: `logrotate -d /etc/logrotate.d/thunes` (optional)

- [ ] **Binance Testnet Account**
  - [ ] Account created: testnet.binance.vision
  - [ ] Test funds available: `make balance`
  - [ ] 2FA enabled: Manual verification
  - [ ] API keys created with correct permissions

- [ ] **Emergency Contacts Updated**
  Edit `scripts/disaster_recovery_drill.md` Appendix:
  - [ ] Primary on-call: Name: ________ Contact: ________
  - [ ] Secondary on-call: Name: ________ Contact: ________
  - [ ] Binance support: testnet@binance.com

- [ ] **Deployment Window Scheduled**
  - Deployment date: ________
  - Deployment time: ________ (prefer business hours)
  - On-call assigned: ________

---

### F. Documentation Review ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

- [ ] **Audit Report Reviewed**
  ```bash
  cat docs/PHASE-13-PRE-DEPLOYMENT-AUDIT-2025-10-09.md
  ```
  Key findings understood:
  - [ ] Deployment readiness: 72% after DR drill
  - [ ] Critical blind spots identified
  - [ ] Success metrics defined

- [ ] **Security Report Reviewed**
  ```bash
  cat docs/SECURITY-VALIDATION-2025-10-09.md
  ```
  - [ ] No critical vulnerabilities
  - [ ] Phase 14 recommendations noted

- [ ] **OPERATIONAL-RUNBOOK.md Current**
  - [ ] Kill-switch procedures accurate
  - [ ] Disaster recovery steps validated
  - [ ] Emergency procedures documented

---

## Deployment Execution Checklist

### G. Pre-Deployment Smoke Test ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

**Run automated validation script**:
```bash
bash scripts/pre_deployment_validation.sh
```

Expected output:
```
✅ Environment validation passed
✅ Security checks passed
✅ Critical tests passed
✅ Disaster recovery validated
✅ Documentation current

🚀 READY FOR DEPLOYMENT
```

If any checks fail:
- [ ] Review failure details
- [ ] Fix issues
- [ ] Re-run validation
- [ ] Do NOT proceed until all checks pass

---

### H. Deployment Execution (T-Minus Countdown) 🚀

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

**T-10 minutes: Final Checks**
- [ ] Working tree clean: `git status`
- [ ] Latest code: `git pull origin main`
- [ ] Virtual environment active: `source .venv/bin/activate`
- [ ] Telegram alerts tested: Message received
- [ ] On-call personnel notified: Deployment starting

**T-5 minutes: System Initialization**
- [ ] Start scheduler in background:
  ```bash
  nohup python src/orchestration/scheduler.py > logs/scheduler.out 2>&1 &
  echo $! > /tmp/scheduler.pid
  ```
- [ ] Verify scheduler running: `ps aux | grep scheduler`
- [ ] Check initial logs: `tail -f logs/paper_trader.log`

**T-0: Deployment Start**
- [ ] Record deployment start time: ________ UTC
- [ ] Send Telegram notification: "Phase 13 deployment started"
- [ ] Begin continuous monitoring

---

## Post-Deployment Verification Checklist

### I. Immediate Verification (First 10 Minutes) ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

**Run automated verification script**:
```bash
bash scripts/post_deployment_verification.sh
```

Manual checks:
- [ ] **Scheduler Running**
  ```bash
  ps aux | grep scheduler
  # Should show active process
  ```

- [ ] **No Critical Errors**
  ```bash
  grep -i "critical\|error" logs/paper_trader.log | tail -20
  # Should show no unhandled errors
  ```

- [ ] **Telegram Alerts Flowing**
  - [ ] Startup notification received
  - [ ] Test manual alert: `python scripts/test_telegram_alert.py`

- [ ] **Kill-Switch Inactive**
  ```bash
  python -c "
  from src.risk.manager import RiskManager
  from src.models.position import PositionTracker
  rm = RiskManager(position_tracker=PositionTracker())
  assert not rm.kill_switch_active, 'Kill-switch active!'
  print('✅ Kill-switch inactive')
  "
  ```

- [ ] **Risk Limits Configured**
  ```bash
  python -c "
  from src.risk.manager import RiskManager
  from src.models.position import PositionTracker
  rm = RiskManager(position_tracker=PositionTracker())
  print(f'Max daily loss: {rm.max_daily_loss}')
  print(f'Max loss per trade: {rm.max_loss_per_trade}')
  print(f'Max positions: {rm.max_positions}')
  print(f'Cool-down: {rm.cool_down_minutes} min')
  "
  # Expected: 20.0, 5.0, 3, 60
  ```

---

### J. First Hour Monitoring ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

**Check every 10 minutes for the first hour**:

- [ ] **T+10 min**: System health
  ```bash
  tail -50 logs/paper_trader.log | grep -E "ERROR|CRITICAL"
  # Expected: No critical errors
  ```

- [ ] **T+20 min**: First trade (if strategy triggers)
  ```bash
  python -c "
  from src.models.position import PositionTracker
  pt = PositionTracker()
  print(f'Open positions: {pt.count_open_positions()}')
  "
  ```

- [ ] **T+30 min**: Memory usage
  ```bash
  ps aux | grep scheduler | awk '{print $6/1024 " MB"}'
  # Expected: <500 MB
  ```

- [ ] **T+40 min**: Audit trail integrity
  ```bash
  tail -10 logs/audit_trail.jsonl | python -m json.tool
  # Expected: Valid JSON, no errors
  ```

- [ ] **T+50 min**: WebSocket stability
  ```bash
  grep -i "websocket\|reconnect" logs/paper_trader.log | tail -5
  # Expected: No frequent reconnections
  ```

- [ ] **T+60 min**: First hour summary
  - Total trades: ________
  - P&L: ________
  - Errors: ________
  - Kill-switch activations: ________ (expected: 0)
  - Memory usage: ________ MB

---

### K. First 24 Hours Monitoring ✅

**Status**: [ ] Complete [ ] In Progress [ ] Not Started

**Check twice daily (9 AM, 6 PM local time)**:

**Morning Check (9 AM)**:
- [ ] Scheduler still running: `ps aux | grep scheduler`
- [ ] No overnight errors: `grep -i "critical\|error" logs/paper_trader.log | tail -20`
- [ ] Memory usage stable: `ps aux | grep scheduler | awk '{print $6/1024 " MB"}'`
- [ ] Open positions: `python -c "from src.models.position import PositionTracker; print(PositionTracker().count_open_positions())"`
- [ ] Daily P&L: `python -c "from src.risk.manager import RiskManager; from src.models.position import PositionTracker; rm = RiskManager(position_tracker=PositionTracker()); print(f'P&L: {rm.get_daily_pnl()}')"`

**Evening Check (6 PM)**:
- [ ] Scheduler still running
- [ ] Day's trading activity reviewed
- [ ] Telegram alerts functioning
- [ ] Log file size manageable: `du -h logs/paper_trader.log` (<50 MB)
- [ ] Audit trail size: `du -h logs/audit_trail.jsonl` (<1 MB/day)

**24-Hour Summary** (Day 1 Complete):
- Uptime: ________ hours (expected: 24)
- Total trades: ________
- Win rate: ________%
- Cumulative P&L: ________
- Kill-switch activations: ________
- Critical errors: ________
- WebSocket reconnects: ________
- Memory usage: ________ MB (expected: <1 GB)

**Status**: [ ] All metrics within acceptable ranges [ ] Issues detected (document below)

Issues found: _______________________________________________

---

## 7-Day Rodage Monitoring

### L. Daily Monitoring Checklist (Days 2-7) ✅

**Repeat daily for 7 days**:

**Morning Routine** (15 minutes):
- [ ] Verify system running: `ps aux | grep scheduler`
- [ ] Review overnight logs: `tail -100 logs/paper_trader.log`
- [ ] Check daily P&L: `python scripts/get_daily_pnl.py`
- [ ] Verify position limits: Max 3 concurrent
- [ ] Check kill-switch status: Should be inactive

**Evening Routine** (15 minutes):
- [ ] Calculate day's metrics:
  - Trades executed: ________
  - Win rate: ________%
  - Daily P&L: ________
  - Max drawdown: ________%
- [ ] Review audit trail: `tail -20 logs/audit_trail.jsonl | jq '.'`
- [ ] Check resource usage:
  - Memory: ________ MB
  - Log file size: ________ MB
  - Database size: ________ MB

**End-of-Day Assessment**:
- [ ] Day __ of 7 complete
- [ ] All Tier 1 metrics passed (zero tolerance)
- [ ] All Tier 2 metrics passed (monitor closely)
- [ ] Any issues escalated: Yes [ ] No [ ]

---

### M. 7-Day Rodage Success Metrics ✅

**Tier 1 - Zero Tolerance (Must Pass)**:

| Metric | Target | Day 1 | Day 2 | Day 3 | Day 4 | Day 5 | Day 6 | Day 7 | Status |
|--------|--------|-------|-------|-------|-------|-------|-------|-------|--------|
| Audit trail integrity | 100% | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Kill-switch activates | On demand | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Position limits enforced | Max 3 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| No unclean shutdowns | 0 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| Telegram alerts working | <5s | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

**Tier 2 - Monitor Closely (Should Pass)**:

| Metric | Target | Day 1 | Day 2 | Day 3 | Day 4 | Day 5 | Day 6 | Day 7 | Status |
|--------|--------|-------|-------|-------|-------|-------|-------|-------|--------|
| WebSocket reconnects | <5/day | ___ | ___ | ___ | ___ | ___ | ___ | ___ | [ ] |
| Circuit breaker trips | <3/week | ___ | ___ | ___ | ___ | ___ | ___ | ___ | [ ] |
| Response time P95 | <500ms | ___ | ___ | ___ | ___ | ___ | ___ | ___ | [ ] |
| Error rate | <10/day | ___ | ___ | ___ | ___ | ___ | ___ | ___ | [ ] |
| Database growth | <10MB | ___ | ___ | ___ | ___ | ___ | ___ | ___ | [ ] |

**Tier 3 - Informational (Nice to Have)**:

| Metric | Target | Week Result | Status |
|--------|--------|-------------|--------|
| Cumulative P&L | Break-even | ________ | [ ] |
| Win rate | >45% | ________% | [ ] |
| Sharpe ratio | >1.0 | ________ | [ ] |
| Max drawdown | <10% | ________% | [ ] |

---

## Phase 13 Completion Checklist

### N. End-of-Rodage Assessment ✅

**After 7 days of continuous operation**:

- [ ] **All Tier 1 Metrics Passed**
  - No audit trail corruption
  - Kill-switch worked on demand
  - Position limits never exceeded
  - No unclean shutdowns
  - Telegram alerts <5s consistently

- [ ] **Tier 2 Metrics Acceptable**
  - WebSocket reconnects: _____ total (target: <35 for 7 days)
  - Circuit breaker trips: _____ total (target: <3)
  - Average P95 latency: _____ ms (target: <500ms)
  - Total errors: _____ (target: <70 for 7 days)
  - Database size: _____ MB (target: <10MB)

- [ ] **Incident Log**
  - Critical incidents: _____ (expected: 0)
  - Manual interventions: _____ (expected: <3)
  - Kill-switch activations: _____ (test + accidental)
  - Unplanned restarts: _____ (expected: 0)

- [ ] **Post-Rodage Report Created**
  ```bash
  cat docs/PHASE-13-RODAGE-REPORT-$(date +%Y-%m-%d).md
  ```

---

### O. Phase 14 Readiness Assessment ✅

**Decision: Proceed to Phase 14 (Live Trading)?**

- [ ] **All Phase 13 Success Criteria Met**
  - 7-day rodage completed without critical incidents
  - All Tier 1 metrics passed
  - All Tier 2 metrics acceptable
  - No unresolved bugs or issues

- [ ] **Technical Debt Addressed**
  - [ ] MyPy errors reduced to <20
  - [ ] datetime.utcnow() replaced with datetime.now(UTC)
  - [ ] Test pass rate >95%
  - [ ] Prometheus metrics implemented (Phase 11)
  - [ ] Log rotation configured

- [ ] **Operational Maturity Achieved**
  - [ ] Disaster recovery practiced 3× during rodage
  - [ ] Kill-switch tested manually at least once
  - [ ] Position reconciliation validated daily
  - [ ] Team confident in operational procedures

- [ ] **Phase 14 Prerequisites Complete**
  - [ ] Separate API keys created for live trading
  - [ ] API key rotation: 30-day policy (vs 90-day testnet)
  - [ ] 2FA enabled on live Binance account
  - [ ] Withdrawal-disabled keys confirmed
  - [ ] Start capital: $10-50 allocated

- [ ] **Compliance Requirements**
  - [ ] Audit trail proven immutable (7-day validation)
  - [ ] Tax export script tested
  - [ ] Regulatory checklist reviewed
  - [ ] Legal review completed (if required)

**Final Decision**:
- [ ] **GO**: Proceed to Phase 14 (live trading with $10-50)
- [ ] **CONDITIONAL GO**: Address issues, then proceed
- [ ] **NO-GO**: Additional testing required

**Approval**:
- Approved by: _______________
- Date: _______________
- Next phase start date: _______________

---

## Emergency Procedures

### P. Emergency Stop (Kill Everything) 🚨

**Use if**: System behaving erratically, losing money rapidly, audit trail corrupted

```bash
# 1. Stop all processes immediately
pkill -9 -f scheduler
pkill -9 -f paper_trader

# 2. Activate kill-switch
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
rm.activate_kill_switch('EMERGENCY STOP: $(date)')
"

# 3. Close all positions manually
python scripts/close_all_positions.py

# 4. Notify team
python scripts/send_emergency_alert.py "EMERGENCY STOP EXECUTED"

# 5. Document incident
echo "$(date): Emergency stop executed. Reason: ________" >> logs/incidents.log
```

---

### Q. Graceful Shutdown (Planned Maintenance) 🛠️

**Use if**: Need to restart, apply updates, or take system offline

```bash
# 1. Stop accepting new trades (activate kill-switch)
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
rm.activate_kill_switch('PLANNED MAINTENANCE: $(date)')
"

# 2. Wait for open positions to close (or close manually)
python scripts/close_all_positions.py --graceful

# 3. Stop scheduler gracefully (SIGTERM, not SIGKILL)
kill $(cat /tmp/scheduler.pid)

# 4. Verify clean shutdown
tail -50 logs/paper_trader.log

# 5. Document in audit trail
echo "$(date): Graceful shutdown for maintenance" >> logs/maintenance.log
```

---

## Appendix: Quick Reference Commands

### System Status
```bash
# Is scheduler running?
ps aux | grep scheduler

# Current positions
python -c "from src.models.position import PositionTracker; print(PositionTracker().count_open_positions())"

# Daily P&L
python -c "from src.risk.manager import RiskManager; from src.models.position import PositionTracker; rm = RiskManager(position_tracker=PositionTracker()); print(rm.get_daily_pnl())"

# Kill-switch status
python -c "from src.risk.manager import RiskManager; from src.models.position import PositionTracker; print(RiskManager(position_tracker=PositionTracker()).kill_switch_active)"
```

### Log Monitoring
```bash
# Tail all logs
tail -f logs/paper_trader.log

# Search for errors
grep -i "error\|critical" logs/paper_trader.log | tail -20

# Audit trail integrity
tail -20 logs/audit_trail.jsonl | python -m json.tool
```

### Resource Usage
```bash
# Memory usage
ps aux | grep scheduler | awk '{print $6/1024 " MB"}'

# Disk usage
du -h logs/

# Database size
du -h src/models/positions.db
```

---

**Document Version**: 1.0
**Created**: 2025-10-09
**Last Updated**: 2025-10-09
**Owner**: Deployment Team
**Approved By**: [Pending]
