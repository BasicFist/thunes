# Quick Start: Unified LAB + THUNES Monitoring

**Last Updated**: 2025-10-08
**Status**: ✅ Production Ready
**Test Results**: See `TEST-RESULTS-UNIFIED-MONITORING.md`

## 🚀 5-Minute Deployment

### Step 1: Start Monitoring Stack (30 seconds)

```bash
cd ~/LAB/projects/THUNES

# Start Prometheus + Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Verify services running
docker-compose -f docker-compose.monitoring.yml ps
# Expected: prometheus (port 9090), grafana (port 3000) both "Up"
```

### Step 2: Start THUNES Scheduler (15 seconds)

```bash
# Activate Python environment
source .venv/bin/activate

# Start scheduler (runs metrics server + LAB metrics updates)
python src/orchestration/run_scheduler.py

# Expected log output:
# [INFO] Starting Prometheus metrics server on port 8000...
# [INFO] Metrics server started: http://0.0.0.0:8000/metrics
# [INFO] Scheduled LAB metrics updates every 30 seconds
# [INFO] Scheduler started successfully
```

**Keep this terminal open** (scheduler runs in foreground) or run in background:
```bash
nohup python src/orchestration/run_scheduler.py > logs/scheduler.log 2>&1 &
echo $! > logs/scheduler.pid
```

### Step 3: Verify Metrics (30 seconds)

```bash
# Test metrics endpoint
curl http://localhost:8000/metrics | grep -E "(thunes|lab)_" | head -10

# Expected output (sample):
# thunes_kill_switch_active 0.0
# thunes_daily_pnl_used 0.15
# thunes_open_positions 1.0
# lab_mcp_server_health{server_name="rag-query"} 1.0
# lab_worktree_status{worktree_name="thunes"} 1.0
# lab_worktree_test_status{worktree_name="main"} 1.0
```

### Step 4: Access Grafana (1 minute)

```bash
# Open Grafana in browser
open http://localhost:3000

# Or manually navigate to: http://localhost:3000
```

**Login**:
- Username: `admin`
- Password: `admin` (will prompt to change on first login)

**View Dashboard**:
1. Click "Dashboards" (left sidebar)
2. Select "THUNES Trading Overview"
3. Dashboard will auto-refresh every 10 seconds

**Expected**: 11 panels displaying data (8 THUNES + 3 LAB)

### Step 5: Verify Alerts (Optional, 30 seconds)

```bash
# Check alert rules loaded
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[] | .name'

# Expected output:
# "thunes_critical_alerts"
# "thunes_risk_alerts"
# "cross_stack_alerts"

# View active alerts (should be empty if system healthy)
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | .labels.alertname'
```

## 📊 What You'll See

### Grafana Dashboard (11 Panels)

**THUNES Trading Panels (8)**:
1. Daily PnL Usage - Graph showing PnL fraction with 80% threshold
2. Open Positions - Current position count (green/yellow/red)
3. Kill-Switch Status - Active/inactive indicator
4. Circuit Breaker State - Per-breaker status
5. Order Latency - p50/p95/p99 latency trends
6. WebSocket Health - Connection status per symbol
7. Orders Placed (24h) - 24-hour order volume
8. WebSocket Message Gap - p95 message gap

**LAB Infrastructure Panels (3)** - TIER 3:
9. MCP Server Health - 18 MCP servers (green: UP, red: DOWN, yellow: NOT_CFG)
10. Worktree Status - 5 worktrees (green: COMPLETE/WORKING, yellow: TESTING, red: BLOCKED)
11. Worktree Test Status - Test results (gray: UNKNOWN, green: PASSING, red: FAILING)

### Prometheus Alerts (11 Rules)

**THUNES Alerts (6)**:
- `KillSwitchActive` [critical] - Kill-switch active >5min
- `CircuitBreakerOpen` [warning] - Circuit breaker open >10min
- `WebSocketDisconnected` [warning] - WebSocket down >2min
- `HighOrderLatency` [warning] - p95 latency >500ms for >5min
- `DailyPnLLimitApproaching` [info] - Daily PnL >80%
- `MaxPositionsReached` [info] - 3 positions open

**Cross-Stack Alerts (5)** - TIER 3:
- `ThunesBlockedWithMCPFailure` [critical] - Kill-switch + RAG down (2min)
- `CircuitBreakerWithInfraIssues` [warning] - Circuit breaker + 3+ MCP down (5min)
- `WorktreeBlockedDuringTrading` [warning] - THUNES worktree blocked with positions (5min)
- `InfrastructureDegradation` [warning] - 5+ MCP down OR 2+ worktrees failing (10min)
- `CriticalSystemsDown` [critical] - Trading halt + 3+ MCP down (5min)

## 🔍 Monitoring Workflows

### Workflow 1: Check System Health

```bash
# 1. Open Grafana dashboard
open http://localhost:3000

# 2. Review panels top to bottom:
#    - THUNES panels (1-8): Trading system health
#    - LAB panels (9-11): Infrastructure health

# 3. Check for red indicators:
#    - Panel 3: Kill-switch (should be green "OK")
#    - Panel 4: Circuit breaker (should be green "CLOSED")
#    - Panel 9: MCP servers (most should be green "UP")
#    - Panel 11: Worktree tests (should be green "PASSING")
```

### Workflow 2: Debug Trading System Halt

**Scenario**: Kill-switch activated unexpectedly

```bash
# 1. Open Grafana → Panel 3: Kill-Switch Status
#    - If RED "ACTIVE": System halted due to daily loss limit

# 2. Check Panel 9: MCP Server Health
#    - If RAG server DOWN: Possible correlation
#    - Alert "ThunesBlockedWithMCPFailure" may fire

# 3. Check Panel 10: Worktree Status
#    - If THUNES worktree BLOCKED: Deployment in progress?

# 4. Review Prometheus alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts'

# 5. Investigate root cause:
#    - Fix MCP server issues first
#    - Review trading logs: tail -f logs/paper_trader.log
#    - Deactivate kill-switch if appropriate
```

### Workflow 3: Investigate Infrastructure Issues

**Scenario**: Multiple MCP servers showing DOWN

```bash
# 1. Check Panel 9: MCP Server Health
#    - Count DOWN servers
#    - Alert "InfrastructureDegradation" fires if ≥5 down

# 2. Restart failed servers
for server in rag-query jupyter context7; do
    ~/LAB/bin/mcp-$server &
done

# 3. Verify health recovery
python3 scripts/update-lab-metrics.py

# 4. Check dashboard (should update in 30s)
#    - Panels refresh automatically
```

## 🛠️ Troubleshooting

### Issue: Metrics Not Updating

**Symptom**: Grafana shows "No data" or stale values

**Diagnosis**:
```bash
# 1. Check scheduler running
ps aux | grep run_scheduler.py

# 2. Check metrics endpoint
curl http://localhost:9090/metrics | head -20

# 3. Check Prometheus scraping
curl http://localhost:9090/api/v1/targets
```

**Fix**:
```bash
# Restart scheduler
pkill -f run_scheduler.py
python src/orchestration/run_scheduler.py
```

### Issue: LAB Metrics Missing

**Symptom**: THUNES metrics work, LAB metrics don't appear

**Diagnosis**:
```bash
# Test LAB metrics script
python3 scripts/update-lab-metrics.py

# Check for errors
echo $?  # Should be 0
```

**Fix**:
```bash
# Verify worktree files exist
ls -la ~/LAB/worktrees/*/.worktree

# Initialize if missing
~/LAB/scripts/worktree-context.sh init ~/LAB/worktrees/dev
```

### Issue: Dashboard Not Loading

**Symptom**: Grafana shows empty dashboard

**Diagnosis**:
```bash
# 1. Check Grafana running
docker ps | grep grafana

# 2. Check dashboard file
ls -lh monitoring/grafana/dashboards/trading_overview.json
```

**Fix**:
```bash
# Restart Grafana
docker-compose -f docker-compose.monitoring.yml restart grafana

# Re-import dashboard if needed
# Grafana UI → Dashboards → Import → Upload JSON
# File: monitoring/grafana/dashboards/trading_overview.json
```

### Issue: Alerts Not Firing

**Symptom**: Expected alerts don't trigger

**Diagnosis**:
```bash
# Check alert rules loaded
curl http://localhost:9090/api/v1/rules | jq '.data.groups[].name'
```

**Fix**:
```bash
# Reload Prometheus config
curl -X POST http://localhost:9090/-/reload
```

## 📈 Optional: THUNES Metrics → Worktree Sync

Auto-sync THUNES Prometheus metrics to worktree context every 5 minutes:

```bash
# Add to crontab
crontab -e

# Add this line:
*/5 * * * * ~/LAB/scripts/thunes-metrics-to-worktree.sh >> ~/LAB/logs/thunes-metrics-sync.log 2>&1

# Verify cron job
crontab -l | grep thunes-metrics

# Test manually
~/LAB/scripts/thunes-metrics-to-worktree.sh
```

**What it does**:
- Queries THUNES Prometheus metrics (kill-switch, circuit breaker, positions, PnL)
- Maps to worktree status (blocked/testing/working)
- Updates `~/LAB/worktrees/thunes/.worktree` file
- TMux displays updated context automatically

## 🎯 Success Checklist

After deployment, verify:

- [ ] Prometheus accessible: http://localhost:9090
- [ ] Grafana accessible: http://localhost:3000
- [ ] Metrics endpoint responding: `curl http://localhost:8000/metrics`
- [ ] All 11 panels displaying data in Grafana
- [ ] Alert rules loaded: `curl http://localhost:9090/api/v1/rules`
- [ ] LAB metrics updating (check Panel 9-11)
- [ ] No errors in logs: `tail -f logs/scheduler.log`
- [ ] THUNES → worktree sync configured (optional)

## 📚 Documentation Links

**Complete Guides**:
- `UNIFIED-MONITORING-DASHBOARD.md` - Full deployment guide (1,200 lines)
- `TEST-RESULTS-UNIFIED-MONITORING.md` - Test results (100% coverage)
- `LAB-WORKFLOW-INTELLIGENCE-COMPLETE.md` - Project completion report
- `TIER-3-UNIFIED-MONITORING-COMPLETE.md` - Quick reference

**System Documentation**:
- `docs/WORKTREE-CONTEXT-SYSTEM.md` - Worktree metadata system
- `docs/monitoring/PROMETHEUS-DEPLOYMENT.md` - THUNES observability

**Support**:
- GitHub Issues: https://github.com/anthropics/claude-code/issues
- Discord: (if available)

## 🚨 Emergency Procedures

### Stop All Services

```bash
# Stop scheduler
pkill -f run_scheduler.py

# Stop Docker stack
docker-compose -f docker-compose.monitoring.yml down
```

### Restart All Services

```bash
# Start Docker stack
docker-compose -f docker-compose.monitoring.yml up -d

# Wait 10 seconds
sleep 10

# Start scheduler
nohup python src/orchestration/run_scheduler.py > logs/scheduler.log 2>&1 &
```

### Reset to Clean State

```bash
# Stop everything
pkill -f run_scheduler.py
docker-compose -f docker-compose.monitoring.yml down -v

# Remove state
rm -rf logs/jobs.db

# Restart
docker-compose -f docker-compose.monitoring.yml up -d
python src/orchestration/run_scheduler.py
```

---

**Quick Start Version**: 1.0
**Last Updated**: 2025-10-08
**Deployment Time**: ~5 minutes
**Support**: See documentation links above
