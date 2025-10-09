# Disaster Recovery Drill - Execution Guide

**Date**: 2025-10-09
**Purpose**: Complete guide for executing Phase 13 pre-deployment DR drill
**Expected Duration**: 2.5 hours (30min prep + 2h drill)
**Deployment Impact**: 51% → 72% readiness (makes deployment viable)

---

## Executive Summary

The Disaster Recovery (DR) drill is the **single remaining deployment blocker** for Phase 13. This guide provides a complete execution workflow from pre-flight checks through post-drill documentation.

**Why This Matters**:
- Current operational maturity: 60% (inadequate)
- Post-drill operational maturity: 85% (acceptable)
- Overall deployment readiness: 51% → 72%
- **Without DR drill**: Cannot deploy safely (untested procedures)
- **With DR drill**: Ready for Phase 13 testnet deployment

---

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] **2.5 hours** of uninterrupted time
- [ ] **Binance testnet** account with API keys configured
- [ ] **Telegram bot** configured and accessible
- [ ] **Virtual environment** activated
- [ ] **At least one open position** (or ability to create one)
- [ ] **Backup communication channel** (in case Telegram fails)
- [ ] **Notebook/spreadsheet** for recording results

---

## Execution Workflow

### Phase 1: Pre-Flight Check (5 minutes)

**Objective**: Verify all prerequisites are met before starting drill

**Command**:
```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate
bash scripts/dr_drill_preflight.sh
```

**Expected Output**: `✅ PRE-FLIGHT CHECK PASSED`

**If Failed**:
1. Review failure messages
2. Fix configuration issues
3. Re-run pre-flight check
4. **DO NOT proceed** until all checks pass

**Common Issues**:
- Virtual environment not activated → `source .venv/bin/activate`
- Telegram not configured → Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to `.env`
- Exchange connectivity failed → Verify API keys are valid for testnet
- No open positions → Create one or plan to skip Test 1

---

### Phase 2: Drill Preparation (25 minutes)

**Step 1: Review Drill Document** (10 min)
```bash
cat scripts/disaster_recovery_drill.md | less
```

**Read carefully**:
- Test objectives and success criteria
- Expected outputs for each step
- Results recording templates

**Step 2: Prepare Recording Sheet** (10 min)

Create a spreadsheet or notebook with the following structure:

```
Test 1: Kill-Switch Activation
- Start time: _____
- Kill-switch activated: [ ] YES [ ] NO
- Telegram alert delivery: _____ seconds
- BUY orders rejected: [ ] YES [ ] NO
- SELL orders allowed: [ ] YES [ ] NO
- Audit trail logged: [ ] YES [ ] NO
- Issues encountered: _____
- End time: _____

Test 2: Kill-Switch Deactivation
- Start time: _____
- Kill-switch deactivated: [ ] YES [ ] NO
- Trading re-enabled: [ ] YES [ ] NO
- Runbook followed: [ ] YES [ ] NO
- Deviations from runbook: _____
- End time: _____

Test 3: Crash Recovery
- Start time: _____
- System restarted: [ ] YES [ ] NO
- Position state recovered: [ ] YES [ ] NO
- Audit trail integrity: [ ] YES [ ] NO
- Data loss: [ ] NONE [ ] MINOR [ ] SIGNIFICANT
- Recovery time: _____ seconds
- End time: _____

Test 4: Position Reconciliation
- Start time: _____
- Local positions: _____
- Binance positions: _____
- Discrepancies: _____
- Reconciliation script exists: [ ] YES [ ] NO
- End time: _____
```

**Step 3: Setup Monitoring** (5 min)

Open multiple terminal windows:

**Terminal 1**: Main execution terminal
```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate
```

**Terminal 2**: Log monitoring
```bash
cd ~/LAB/projects/THUNES
tail -f logs/paper_trader.log
```

**Terminal 3**: Audit trail monitoring
```bash
cd ~/LAB/projects/THUNES
tail -f logs/audit_trail.jsonl | jq '.'
```

**Terminal 4**: System resource monitoring
```bash
watch -n 5 'ps aux | grep python | head -10'
```

---

### Phase 3: Execute Drill (2 hours)

**Important**: Follow `scripts/disaster_recovery_drill.md` step-by-step. Do not deviate from documented procedures.

#### Test 1: Kill-Switch Activation (30 min)

**Start**: Record start time in your recording sheet

**Execute**: Follow steps 1-5 in `scripts/disaster_recovery_drill.md` section "Test 1"

**Key Validation Points**:
1. Pre-test state captured correctly
2. Kill-switch activation logs to console and file
3. Telegram alert arrives within 5 seconds
4. BUY orders rejected with correct error message
5. SELL orders allowed
6. Audit trail shows `KILL_SWITCH_ACTIVATED` event

**Record**: All results in your recording sheet

---

#### Test 2: Kill-Switch Deactivation (30 min)

**Start**: Record start time

**Execute**: Follow steps 1-5 in `scripts/disaster_recovery_drill.md` section "Test 2"

**Key Validation Points**:
1. Runbook deactivation procedure followed exactly
2. Kill-switch deactivates without errors
3. BUY orders allowed after deactivation
4. Audit trail shows `KILL_SWITCH_DEACTIVATED` event
5. No deviations from documented procedure

**Critical**: If you deviate from runbook procedure, document exactly what you did differently and why.

**Record**: All results, including any runbook deviations

---

#### Test 3: Crash Recovery (30 min)

**Start**: Record start time

**Execute**: Follow steps 1-6 in `scripts/disaster_recovery_drill.md` section "Test 3"

**Key Validation Points**:
1. Pre-crash state saved to `/tmp/pre_crash_state.json`
2. Audit trail integrity validated before crash
3. Process killed with `kill -9` (not graceful shutdown)
4. System restarts without errors
5. Position state matches pre-crash
6. Audit trail has no corruption
7. Database accessible and consistent

**Record**: Recovery time, data loss assessment, any unexpected behavior

---

#### Test 4: Position Reconciliation (30 min)

**Start**: Record start time

**Execute**: Follow steps 1-4 in `scripts/disaster_recovery_drill.md` section "Test 4"

**Key Validation Points**:
1. Local positions retrieved successfully
2. Binance positions retrieved successfully
3. Manual comparison documented
4. Discrepancies identified and explained
5. Reconciliation script evaluated (create if missing)

**Note**: This test may reveal missing reconciliation tooling. Document as action item for Phase 14.

**Record**: All discrepancies and root causes

---

### Phase 4: Post-Drill Documentation (30 minutes)

#### Step 1: Complete Drill Summary

Fill in the "Post-Drill Summary" section of `scripts/disaster_recovery_drill.md`:

```bash
vi scripts/disaster_recovery_drill.md
# Navigate to "Post-Drill Summary" section
# Fill in all results tables
```

**Required Information**:
- Overall test results (PASS/FAIL for each test)
- Duration for each test
- Issues encountered
- Key learnings (at least 3)
- Runbook updates required
- Action items with priorities

#### Step 2: Update Progress Report

Update `docs/PHASE-13-PREDEPLOYMENT-PROGRESS-2025-10-09.md`:

```markdown
### 3. Disaster Recovery Dry-Run ✅ (2 hours - Complete)

**Status**: Executed on [DATE]

**Results**:
- Test 1 (Kill-switch activation): [PASS/FAIL]
- Test 2 (Kill-switch deactivation): [PASS/FAIL]
- Test 3 (Crash recovery): [PASS/FAIL]
- Test 4 (Position reconciliation): [PASS/FAIL]

**Overall**: [X/4 tests passed]

**Key Findings**:
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

**Deployment Readiness**: Updated from 51% → 72%
```

#### Step 3: Update Deployment Checklist

Mark Section B (Pre-Deployment Validation) item 3 as complete in `docs/PHASE-13-DEPLOYMENT-CHECKLIST.md`:

```markdown
- [x] **B.3 Disaster Recovery Validation** (30 min)
  - [x] Kill-switch activation tested
  - [x] Kill-switch deactivation tested
  - [x] Crash recovery validated
  - [x] Position reconciliation verified
  - [x] Results documented in drill guide
```

#### Step 4: Commit Results

```bash
git add scripts/disaster_recovery_drill.md
git add docs/PHASE-13-PREDEPLOYMENT-PROGRESS-2025-10-09.md
git add docs/PHASE-13-DEPLOYMENT-CHECKLIST.md
git commit -m "docs: complete disaster recovery drill execution

Results:
- Test 1 (Kill-switch): [PASS/FAIL]
- Test 2 (Deactivation): [PASS/FAIL]
- Test 3 (Crash recovery): [PASS/FAIL]
- Test 4 (Reconciliation): [PASS/FAIL]

Deployment readiness: 51% → 72%
Ready for Phase 13 deployment: [YES/NO]

See scripts/disaster_recovery_drill.md for complete results."
```

---

## Decision Matrix After Drill

### If All Tests Pass (4/4)

**Status**: ✅ Ready for Phase 13 Deployment

**Deployment Readiness**: 72% (acceptable for testnet)

**Next Steps**:
1. Review pre-deployment checklist: `docs/PHASE-13-DEPLOYMENT-CHECKLIST.md`
2. Execute pre-deployment validation: `bash scripts/pre_deployment_validation.sh`
3. Follow deployment runbook: `docs/PHASE-13-DEPLOYMENT-RUNBOOK.md`
4. Deploy to Phase 13 testnet
5. Execute post-deployment verification: `bash scripts/post_deployment_verification.sh`

**Timeline**: Deploy within 24 hours (while procedures are fresh)

---

### If 3/4 Tests Pass

**Status**: ⚠️ Conditional Go (Review Required)

**Analysis Required**:
- Which test failed and why?
- Is failure due to procedure error or system bug?
- Can issue be fixed quickly (<2 hours)?
- Does failure block deployment or is it acceptable risk?

**Decision Path**:
- **Procedure error**: Fix documentation, re-run failed test
- **Minor system bug**: Document workaround, create Phase 14 ticket, deploy
- **Major system bug**: Fix code, re-run full drill, delay deployment

---

### If 2/4 or Fewer Tests Pass

**Status**: 🔴 No-Go (Delay Deployment)

**Required Actions**:
1. Analyze all failures systematically
2. Identify root causes (bugs vs procedure gaps)
3. Create prioritized fix list
4. Fix critical issues
5. Re-run complete drill
6. Do not deploy until 4/4 tests pass

**Escalation**: If multiple tests fail, this indicates systemic issues. Consider:
- Code review of risk manager and audit trail
- Additional integration testing
- Consultation with external reviewer
- Extended testing period before deployment

---

## Emergency Procedures During Drill

### If System Hangs or Freezes

```bash
# Terminal 1: Check process status
ps aux | grep python

# If process is running but unresponsive:
pkill -TERM -f paper_trader
# Wait 10 seconds
sleep 10

# If still running:
pkill -9 -f paper_trader

# Restart from known state
python src/live/paper_trader.py --symbol BTCUSDT --side BUY --amount 100 &
```

### If Telegram Alerts Stop Working

**Immediate Actions**:
1. Check internet connectivity: `ping api.telegram.org`
2. Verify bot token hasn't expired
3. Check Telegram bot status: `python scripts/verify_telegram.py`

**Workaround**: Continue drill using log monitoring only, document Telegram failure as action item.

### If Database Corruption Detected

```bash
# Check integrity
sqlite3 positions.db "PRAGMA integrity_check;"

# If corrupted, restore from backup (if exists)
cp positions.db.backup positions.db

# If no backup, reinitialize (data loss)
rm positions.db
python -c "from src.models.position import PositionTracker; pt = PositionTracker()"
```

**Critical**: Database corruption during drill is a major red flag. Do not deploy until root cause is identified and fixed.

### If Audit Trail Corruption Detected

```bash
# Validate all lines
python -c "
import json
with open('logs/audit_trail.jsonl') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            print(f'Line {i} corrupted: {e}')
"

# If corruption found, this is CRITICAL
# Do not deploy until two-level locking is verified
grep -n "fcntl" src/risk/manager.py
```

---

## Tools Reference

| Tool | Purpose | Command |
|------|---------|---------|
| **Pre-flight Check** | Verify prerequisites | `bash scripts/dr_drill_preflight.sh` |
| **Drill Guide** | Step-by-step procedures | `cat scripts/disaster_recovery_drill.md` |
| **Pre-Deployment Validation** | Automated system checks | `bash scripts/pre_deployment_validation.sh` |
| **Post-Deployment Verification** | Automated health checks | `bash scripts/post_deployment_verification.sh` |
| **Deployment Checklist** | Complete deployment tracking | `docs/PHASE-13-DEPLOYMENT-CHECKLIST.md` |
| **Deployment Runbook** | Step-by-step deployment | `docs/PHASE-13-DEPLOYMENT-RUNBOOK.md` |
| **Operational Runbook** | Incident response procedures | `docs/OPERATIONAL-RUNBOOK.md` |

---

## Frequently Asked Questions

### Q: Can I run the drill on production?

**A**: ❌ NO. The drill includes intentional crashes (kill -9) and kill-switch toggling. Only run on testnet with no real funds at risk.

### Q: What if I don't have an open position?

**A**: You can skip Test 1 or create a small position first:
```bash
python src/live/paper_trader.py --symbol BTCUSDT --side BUY --amount 10
```

### Q: Can I automate the drill?

**A**: Partially. Steps 1-2 (kill-switch) can be automated, but human verification of Telegram alerts is required. Tests 3-4 (crash recovery, reconciliation) require judgment calls best made manually.

### Q: How often should we run this drill?

**A**:
- **Phase 13 (testnet)**: Monthly
- **Phase 14 (live)**: Weekly for first month, then bi-weekly
- **After incidents**: Within 48 hours to validate fixes

### Q: What if Telegram is down?

**A**: Continue drill using log monitoring only. Telegram failure doesn't invalidate other test results, but should be documented and investigated.

---

## Success Criteria

**Drill is considered successful if**:
- ✅ All 4 tests execute without crashing
- ✅ At least 3/4 tests pass
- ✅ All failures are documented with root causes
- ✅ Runbook deviations are minimal and documented
- ✅ System recovers cleanly from crash scenario
- ✅ Audit trail maintains integrity throughout

**Deployment is authorized if**:
- ✅ 4/4 tests pass, OR
- ✅ 3/4 tests pass with non-blocking failures documented

---

## Contact Information

**For Questions or Issues During Drill**:
- Primary: Review `docs/OPERATIONAL-RUNBOOK.md`
- Secondary: Check logs in `logs/paper_trader.log`
- Escalation: Document issue, complete remaining tests, analyze after drill

**Post-Drill Review**:
- Schedule 30-minute debrief within 24 hours
- Review all failures and action items
- Update procedures based on learnings
- Make deployment decision

---

## Appendix: Drill Timeline Template

```
DR Drill Execution Timeline - [DATE]

00:00 - START
00:05 - Pre-flight check complete
00:30 - Preparation complete, monitors setup
00:35 - Test 1 START (Kill-switch activation)
01:05 - Test 1 COMPLETE
01:10 - Test 2 START (Kill-switch deactivation)
01:40 - Test 2 COMPLETE
01:45 - Test 3 START (Crash recovery)
02:15 - Test 3 COMPLETE
02:20 - Test 4 START (Position reconciliation)
02:50 - Test 4 COMPLETE
02:55 - Documentation START
03:25 - Documentation COMPLETE
03:30 - DRILL COMPLETE

Results: [X/4 PASS]
Deployment Decision: [GO/NO-GO]
Readiness: 51% → [72%/unchanged]
```

---

**Document Created**: 2025-10-09
**Last Updated**: 2025-10-09
**Next Review**: After drill completion
**Owner**: Deployment Team
