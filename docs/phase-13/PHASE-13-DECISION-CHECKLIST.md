# Phase 13 Decision Checklist
## Quick Reference for Testnet Rodage & Phase 14 Go/No-Go

*Generated: 2025-10-07*
*Source: Reddit + GitHub Research (400+ posts, 47 repos, 150k+ stars)*

---

## ✅ Phase 13 Completion Criteria (7-Day Minimum)

### Technical Validation (MUST PASS)

- [ ] **Uptime**: 99%+ over 7 days (max 1.7 hours downtime)
- [ ] **WebSocket**: Zero disconnections >10 seconds (reconnection working)
- [ ] **Order Filters**: Zero -1013 rejections (tick/step/notional validated)
- [ ] **Kill-Switch**: Triggers correctly on simulated -2% daily loss
- [ ] **Cool-Down**: Activates after loss, prevents trading for 60min
- [ ] **Position Limits**: Prevents 4th position (max 3)
- [ ] **Telegram Alerts**: All critical events received (kill-switch, daily summary)
- [ ] **Audit Trail**: Every trade logged to logs/audit_trail.jsonl
- [ ] **CI/CD**: All 228 tests passing, green for 7+ days
- [ ] **Logs**: No CRITICAL errors in logs/paper_trader.log

**Pass Criteria**: 10/10 checklist items ✅

### Performance Validation (INFORMATIONAL ONLY)

- [ ] Sharpe Ratio: _____ (any value acceptable, SMA is placeholder)
- [ ] Win Rate: _____ (any value acceptable)
- [ ] Max Drawdown: _____ (target <20%, not critical)
- [ ] Execution Latency: _____ ms (target <100ms)
- [ ] Trades Executed: _____ (minimum 10 for validation)

**Note**: Performance metrics NOT required to pass Phase 13. SMA strategy is placeholder.

---

## 🚨 Go/No-Go Decision for Phase 14

### GO Criteria (Proceed to Live Trading)

**MUST** have all of:
1. ✅ All technical validation passed (10/10)
2. ✅ 7 consecutive days without manual intervention
3. ✅ Team confidence in kill-switch (tested manually)
4. ✅ Audit trail reviewed and validated
5. ✅ $10-50 capital available (minimal risk)

**Recommended** to have:
6. 📊 Prometheus metrics deployed (Phase 11)
7. 📊 Decision on CCXT integration (Recommendation #1)
8. 📊 Phase 15 meta-labeling plan documented

### NO-GO Criteria (Extend Testnet)

**STOP** if any of:
1. ❌ Kill-switch failed to trigger on simulated loss
2. ❌ Order filters allowed -1013 rejection
3. ❌ WebSocket disconnection >10 seconds without reconnect
4. ❌ Audit trail incomplete or corrupted
5. ❌ Manual intervention required to keep running
6. ❌ Unresolved CRITICAL errors in logs

**Extend testnet by 7 days if NO-GO**

---

## 📋 Phase 14 Deployment Checklist

### Pre-Deployment (Day 0)

- [ ] Withdraw testnet funds, switch to mainnet API keys
- [ ] Verify API keys are **withdrawal-disabled** (security)
- [ ] Update .env with live credentials
- [ ] Set ENVIRONMENT=live in config
- [ ] Fund account with $10-50 (minimal capital)
- [ ] Verify 2FA enabled on exchange
- [ ] Test Telegram alerts with live bot
- [ ] Backup audit trail and database
- [ ] Document initial account balance: $______

### Week 1 Monitoring (Daily Checks)

- [ ] Day 1: Review first trades, verify order execution
- [ ] Day 2: Check kill-switch never triggered
- [ ] Day 3: Verify cool-down working if loss occurred
- [ ] Day 4: Review audit trail completeness
- [ ] Day 5: Check Telegram alerts received
- [ ] Day 6: Verify no manual interventions needed
- [ ] Day 7: Calculate Week 1 PnL: $______

**Week 1 Success**: No kill-switch triggers, no manual interventions

### Week 2-4 Monitoring (Weekly Checks)

- [ ] Week 2: PnL: $______, Sharpe: ______, Max DD: ______
- [ ] Week 3: PnL: $______, Sharpe: ______, Max DD: ______
- [ ] Week 4: PnL: $______, Sharpe: ______, Max DD: ______

**30-Day Success Criteria**:
- Zero kill-switch triggers
- Zero manual interventions
- PnL: -$10 to +$10 acceptable (learning phase)
- Risk management functioning correctly

### Scale-Up Decision (After 30 Days)

**IF** 30-day success AND all of:
1. ✅ Zero kill-switch triggers
2. ✅ Zero manual interventions
3. ✅ Audit trail complete
4. ✅ PnL > -20% (-$10 max loss)

**THEN** scale to $100-500 for Month 2

**IF** any NO-GO criteria:
- Return to testnet for additional 30 days
- Review logs for failure patterns
- Fix issues before retry

---

## 🎯 Critical Recommendations (From Research)

### HIGH Priority (Decide by End Phase 13)

**#1: CCXT Integration**
- [ ] Decision: YES / NO / DEFER
- [ ] Rationale: _________________________________________________
- [ ] If YES: Allocate 2-3 weeks in Phase 14
- [ ] If NO: Document reason for future review
- [ ] If DEFER: Set review date: __________

**Recommendation**: YES (39k stars, 100+ exchanges, battle-tested)

**#2: Prometheus Metrics (Phase 11)**
- [ ] Status: COMPLETE / IN-PROGRESS / BLOCKED
- [ ] If INCOMPLETE: Target completion date: __________
- [ ] Grafana dashboards deployed: YES / NO

**Recommendation**: COMPLETE before Phase 14

### MEDIUM Priority (Plan for Phase 15)

**#3: Meta-Labeling Implementation**
- [ ] Option A: FreqAI integration (6-8 weeks) - EVALUATE
- [ ] Option B: Custom implementation (4-6 weeks) - EVALUATE
- [ ] Decision deadline: End of Phase 14 (after 30 days live)
- [ ] Rationale: _________________________________________________

**Recommendation**: Evaluate both, decide based on license + timeline

**#4: Strategy Module System**
- [ ] Current: Hardcoded SMA ✅ (acceptable for MVP)
- [ ] Future: Pluggable framework (3-4 weeks) - PLAN
- [ ] Priority: After meta-labeling (Phase 15+)

---

## ⚠️ Anti-Patterns to Watch For

### During Phase 13-14

- [ ] ❌ Extending testnet beyond 14 days (over-engineering)
- [ ] ❌ Adding indicators to SMA strategy (indicator accumulation)
- [ ] ❌ Upgrading infrastructure before profitability
- [ ] ❌ Considering Rust rewrite (language switching)
- [ ] ❌ Implementing ML price prediction (vs meta-labeling)

**Self-Check**: If any checked, review anti-patterns in CRITICAL-FINDINGS-RECOMMENDATIONS-OCT-2025.md

### Red Flags (Stop and Review)

- [ ] 🚩 Spending >4 hours/day on trading (work-life balance risk)
- [ ] 🚩 Manual interventions needed >1 per week
- [ ] 🚩 Infrastructure costs >$150/month before profitability
- [ ] 🚩 Considering major architecture changes before Phase 14 complete
- [ ] 🚩 Setting unrealistic profit expectations for Year 1

**If any red flags**: Take 24-hour break, review research findings

---

## 📊 Expected Performance (Validated by Research)

### Phase 14 (Month 1-3, $10-50 capital)

**Realistic Expectations**:
- PnL: -20% to +10% (learning phase)
- Sharpe: -0.5 to +0.5 (acceptable)
- Win Rate: 40-60% (typical)
- Max Drawdown: 10-20% (acceptable)

**Success Definition**: Risk management working, no manual interventions

### Phase 15+ (Months 4-12, with meta-labeling)

**Target After Meta-Labeling**:
- Sharpe: 1.0-1.5 (out-of-sample)
- Win Rate: 50-65%
- Max Drawdown: 8-12%
- Sharpe Improvement: +15-20% vs baseline

**Critical**: Only deploy meta-labeling if out-of-sample Sharpe > 1.0

### Year 1-3 Timeline (Conservative Scenario, 80% probability)

```
Year 1 (2025-2026): -20% to -5% returns
  - Phase 13-14: Learning deployment
  - Phase 15: Meta-labeling implementation
  - Q4 2025: Negative returns expected

Year 2 (2026-2027): -10% to +10% returns
  - Phase 16: Strategy diversification
  - Q2 2026: Possible break-even
  - Q4 2026: Early profitability possible

Year 3 (2027-2028): 0% to +20% returns
  - Phase 17-18: Advanced features
  - Q2 2027: Break-even likely (18-24 months)
  - Q4 2027: Consistent profitability possible
```

**Break-Even**: 30-36 months from Phase 14 start (Q2-Q3 2027)

---

## 🔄 Weekly Review Template

**Week of**: __________
**Phase**: 13 / 14 / 15 / Other: ______

### Technical Health
- Uptime: ______%
- WebSocket disconnects: ______
- Order rejections: ______
- Kill-switch triggers: ______
- Manual interventions: ______

### Performance
- Trades executed: ______
- Win rate: ______%
- PnL: $______
- Sharpe: ______
- Max drawdown: ______%

### Action Items
- [ ] Item 1: _________________________________________________
- [ ] Item 2: _________________________________________________
- [ ] Item 3: _________________________________________________

### Lessons Learned
- _________________________________________________________________
- _________________________________________________________________
- _________________________________________________________________

### Decisions Made
- _________________________________________________________________
- _________________________________________________________________

### Next Week Focus
- _________________________________________________________________
- _________________________________________________________________

---

## 📞 Emergency Contacts

**Kill-Switch Manual Activation**:
```bash
# SSH into production
ssh user@production-server

# Stop trading
docker stop thunes

# Verify stopped
docker ps | grep thunes

# Review audit trail
tail -100 /app/logs/audit_trail.jsonl

# Deactivate kill-switch (in Python shell)
from src.risk.manager import RiskManager
rm = RiskManager.load_from_db()
rm.deactivate_kill_switch(reason="manual review complete")
```

**Telegram Bot**:
- Test message: `/status`
- Emergency alert: Available 24/7

**Binance Support**:
- Testnet: testnet.binance.vision
- Live: https://www.binance.com/en/support

---

## 📚 Quick Reference Links

**Research Documents**:
- Critical Findings: `/docs/research/CRITICAL-FINDINGS-RECOMMENDATIONS-OCT-2025.md`
- Reddit Analysis: `/docs/research/REDDIT-DEEP-DIVE-SYNTHESIS-OCT-2025.md`
- GitHub Analysis: `/docs/research/GITHUB-ECOSYSTEM-ANALYSIS-OCT-2025.md`

**Project Docs**:
- Operational Runbook: `/docs/OPERATIONAL-RUNBOOK.md`
- CLAUDE.md: Project context
- Phase 13 Sprint: Current status

**External Resources**:
- freqtrade docs: https://www.freqtrade.io
- hummingbot docs: https://hummingbot.org
- CCXT docs: https://docs.ccxt.com

---

**Status**: 🚨 ACTIVE - Complete before Phase 14 deployment
**Last Updated**: 2025-10-07
**Next Review**: After Phase 13 completion (7 days)
