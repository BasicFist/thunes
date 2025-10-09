# Disaster Recovery Drill - Quick Start

**⏱️ Duration**: 2.5 hours | **📍 Status**: Deployment Blocker | **📈 Impact**: 51% → 72% readiness

---

## TL;DR

Execute the disaster recovery drill to validate operational procedures. This is the **only remaining blocker** for Phase 13 deployment.

---

## Prerequisites (5 minutes)

```bash
cd ~/LAB/projects/THUNES
source .venv/bin/activate

# Run pre-flight check
bash scripts/dr_drill_preflight.sh
```

**Expected**: `✅ PRE-FLIGHT CHECK PASSED`

**If failed**: Fix issues, re-run. Do not proceed until all checks pass.

---

## Execute Drill (2 hours)

Follow step-by-step:

```bash
# Open the drill guide
cat scripts/disaster_recovery_drill.md | less
```

**4 Tests to Execute**:
1. **Kill-Switch Activation** (30 min) - Manual trigger + Telegram verification
2. **Kill-Switch Deactivation** (30 min) - Runbook procedure validation
3. **Crash Recovery** (30 min) - Simulated kill -9 + state recovery
4. **Position Reconciliation** (30 min) - Local vs Binance validation

**Critical**: Record results in the drill document as you go.

---

## Post-Drill (30 minutes)

1. **Update drill results** in `scripts/disaster_recovery_drill.md`
2. **Update progress report** in `docs/PHASE-13-PREDEPLOYMENT-PROGRESS-2025-10-09.md`
3. **Commit results**:

```bash
git add scripts/disaster_recovery_drill.md docs/PHASE-13-PREDEPLOYMENT-PROGRESS-2025-10-09.md
git commit -m "docs: disaster recovery drill execution complete

Results: [X/4 tests passed]
Deployment readiness: 51% → 72%"
```

---

## Next Steps

### If 4/4 or 3/4 Tests Pass ✅

**You are GO for deployment!**

```bash
# Pre-deployment validation
bash scripts/pre_deployment_validation.sh

# Follow deployment runbook
cat docs/PHASE-13-DEPLOYMENT-RUNBOOK.md

# Post-deployment verification
bash scripts/post_deployment_verification.sh
```

### If ≤2/4 Tests Pass 🔴

**DO NOT DEPLOY**

1. Analyze all failures
2. Fix critical issues
3. Re-run complete drill
4. Review with team before proceeding

---

## Emergency Contacts

- **Runbook**: `docs/OPERATIONAL-RUNBOOK.md`
- **Logs**: `tail -f logs/paper_trader.log`
- **Audit Trail**: `tail -f logs/audit_trail.jsonl | jq '.'`

---

## Resources

| Document | Purpose |
|----------|---------|
| `scripts/dr_drill_preflight.sh` | Pre-flight checks (5 min) |
| `scripts/disaster_recovery_drill.md` | Detailed procedures (2 hours) |
| `docs/DR-DRILL-EXECUTION-GUIDE.md` | Complete execution guide |
| `docs/PHASE-13-DEPLOYMENT-RUNBOOK.md` | Deployment procedures |

---

**Ready?** Run `bash scripts/dr_drill_preflight.sh` to begin.

**Questions?** See `docs/DR-DRILL-EXECUTION-GUIDE.md` for comprehensive guidance.

**Stuck?** Check `docs/OPERATIONAL-RUNBOOK.md` for troubleshooting.
