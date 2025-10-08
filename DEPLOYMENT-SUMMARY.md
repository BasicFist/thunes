# THUNES Unified Monitoring - Deployment Summary

**Deployment Date**: 2025-10-08
**Status**: ✅ **OPERATIONAL**

## Deployed Services

| Service | Port | URL | Status |
|---------|------|-----|--------|
| **THUNES Metrics Server** (Flask) | 8000 | http://localhost:8000/metrics | ✅ Running |
| **Prometheus** | 9091 | http://localhost:9091 | ✅ Running |
| **Grafana** | 3001 | http://localhost:3001 | ✅ Running |

**Login Credentials**:
- Grafana: `admin` / `thunes123`

## Architecture

```
THUNES Scheduler (PID 643570)
  ├─ Flask Metrics Server :8000
  │   ├─ THUNES Trading Metrics (8 metrics)
  │   └─ LAB Infrastructure Metrics (3 metrics)
  │
  ↓ scrapes every 15s
  │
Prometheus Container :9091
  ├─ Stores metrics (30-day retention)
  ├─ Evaluates alert rules
  └─ Provides query API
  │
  ↓ queries
  │
Grafana Container :3001
  └─ THUNES Trading Overview Dashboard
      ├─ 8 THUNES panels
      └─ 3 LAB panels
```

## Verification

### 1. Check Services Status

```bash
# Containers
podman ps --filter "name=thunes-"

# Expected:
# thunes-prometheus  Up XX minutes  0.0.0.0:9091->9090/tcp
# thunes-grafana     Up XX minutes  0.0.0.0:3001->3000/tcp

# Scheduler process
ps aux | grep run_scheduler.py
```

### 2. Test Metrics Endpoint

```bash
# From Prometheus container (validates host connectivity)
podman exec thunes-prometheus wget -q -O- http://host.containers.internal:8000/metrics | grep -E "(thunes|lab)_" | head -10
```

**Expected output:**
```
thunes_kill_switch_active 0.0
thunes_daily_pnl_used 0.0
thunes_open_positions 0.0
lab_mcp_server_health{...}
lab_worktree_status{...}
```

### 3. Verify Prometheus Scraping

```bash
# Check targets status
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[0].health'

# Expected: "up"
```

### 4. Access Grafana Dashboard

1. Open browser: http://localhost:3001
2. Login: `admin` / `thunes123`
3. Navigate: **Dashboards** → **THUNES Trading Overview**
4. Verify: 11 panels displaying data

## Logs

```bash
# Scheduler logs (includes metrics server + LAB metrics job)
tail -f logs/scheduler.log

# Container logs
podman logs -f thunes-prometheus
podman logs -f thunes-grafana
```

## Key Metrics Exposed

### THUNES Trading (8 metrics)
- `thunes_kill_switch_active` - Kill-switch status
- `thunes_daily_pnl_used` - Daily PnL fraction
- `thunes_open_positions` - Position count
- `thunes_circuit_breaker_state{breaker_name}` - Circuit breaker state
- `thunes_orders_placed_total{venue,order_type,side}` - Order counter
- `thunes_order_latency_ms` - Latency histogram
- `thunes_ws_connected{symbol}` - WebSocket status
- `thunes_ws_gap_seconds` - Message gap histogram

### LAB Infrastructure (3 metrics)
- `lab_mcp_server_health{server_name}` - 18 MCP servers
- `lab_worktree_status{worktree_name}` - 5 worktrees
- `lab_worktree_test_status{worktree_name}` - Test status

## Alert Rules

**Total**: 11 rules across 3 groups

**Critical**:
- `KillSwitchActive` - Trading halted
- `ThunesBlockedWithMCPFailure` - Kill-switch + RAG server down
- `CriticalSystemsDown` - Trading fault + 3+ MCP failures

**Warning** (8 rules):
- Circuit breaker, WebSocket, latency, infrastructure correlation alerts

See `monitoring/prometheus/rules.yml` for full configuration.

## Troubleshooting

### Metrics Not Updating

**Check scheduler running**:
```bash
ps aux | grep run_scheduler.py
tail -20 logs/scheduler.log
```

**Restart if needed**:
```bash
pkill -f run_scheduler.py
PYTHONPATH=/home/miko/LAB/projects/THUNES python src/orchestration/run_scheduler.py > logs/scheduler.log 2>&1 &
```

### Prometheus Not Scraping

**Check target health**:
```bash
curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets[].health'
```

**Restart Prometheus**:
```bash
podman restart thunes-prometheus
```

### Grafana Connection Issues

**Restart Grafana**:
```bash
podman restart thunes-grafana
```

**Check datasource**:
- Grafana UI → Configuration → Data Sources → Prometheus
- URL should be: `http://thunes-prometheus:9090`

## Port Configuration Notes

**Non-standard ports used** to avoid conflicts with existing monitoring infrastructure:

| Standard Port | THUNES Port | Reason |
|--------------|-------------|---------|
| 9090 (Prometheus UI) | 9091 | Port 9090 in use by `observability_prometheus_1` |
| 3000 (Grafana) | 3001 | Port 3000 in use by `observability_grafana_1` |
| N/A | 8000 | Flask metrics server (custom, no standard) |

**Container→Host Communication**: Uses `host.containers.internal` (Podman/Docker feature) to allow Prometheus container to scrape metrics from Flask server running on the host.

## Deployment Commands

### Start All Services

```bash
# 1. Start containers
podman run -d \
  --name thunes-prometheus \
  --add-host=host.containers.internal:host-gateway \
  -v ./monitoring/prometheus:/etc/prometheus:ro,Z \
  -v prometheus-data:/prometheus \
  -p 9091:9090 \
  --network thunes-monitoring \
  docker.io/prom/prometheus:v2.48.0 \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=30d \
  --web.enable-lifecycle

podman run -d \
  --name thunes-grafana \
  --user 1000:1000 \
  -e GF_SECURITY_ADMIN_PASSWORD=thunes123 \
  -e GF_USERS_ALLOW_SIGN_UP=false \
  -v grafana-data:/var/lib/grafana \
  -v ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro \
  -v ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro \
  -p 3001:3000 \
  --network thunes-monitoring \
  docker.io/grafana/grafana:10.2.2

# 2. Start scheduler (metrics server + LAB metrics)
source .venv/bin/activate
PYTHONPATH=/home/miko/LAB/projects/THUNES python src/orchestration/run_scheduler.py > logs/scheduler.log 2>&1 &
echo "Scheduler PID: $!"
```

### Stop All Services

```bash
# Stop scheduler
pkill -f run_scheduler.py

# Stop containers
podman stop thunes-prometheus thunes-grafana
podman rm thunes-prometheus thunes-grafana
```

## Next Steps

1. ✅ **Production Ready** - All components validated
2. ⏳ **LAB Metrics Optimization** - Reduce collection time from 30s to <10s (parallel health checks)
3. ⏳ **Telegram Integration** - Configure Alertmanager for cross-stack alerts
4. ⏳ **Historical Analysis** - Enable long-term metrics storage for trend analysis
5. ⏳ **Dashboard Expansion** - Add per-worktree focused dashboards

## Documentation

- **Quick Start**: `QUICK-START-UNIFIED-MONITORING.md`
- **Architecture**: `docs/UNIFIED-MONITORING-DASHBOARD.md`
- **Test Results**: `TEST-RESULTS-UNIFIED-MONITORING.md`
- **Completion Report**: `docs/LAB-WORKFLOW-INTELLIGENCE-COMPLETE.md`
- **TIER 3 Summary**: `TIER-3-UNIFIED-MONITORING-COMPLETE.md`

---

**Deployed by**: Claude Code (Sonnet 4.5)
**Last Updated**: 2025-10-08
