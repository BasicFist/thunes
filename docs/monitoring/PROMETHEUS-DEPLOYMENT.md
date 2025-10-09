# Prometheus Observability Stack - Deployment Guide

**Phase 11 Deliverable** | **Sprint 2.3 Implementation** | **Last Updated**: 2025-10-08

This guide documents the deployment and operation of THUNES' Prometheus + Grafana monitoring stack, implementing the observability requirements from `PHASE_13_SPRINTS.md`.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [Metrics Reference](#metrics-reference)
- [Alert Configuration](#alert-configuration)
- [Grafana Dashboard](#grafana-dashboard)
- [Testing & Validation](#testing--validation)
- [Integration with Phase 13 Rodage](#integration-with-phase-13-rodage)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

### Components

```
THUNES Scheduler (Port 9090)
    ↓ exposes /metrics
Prometheus (Port 9090) ← scrapes every 15s
    ↓ stores time-series
    ↓ evaluates alert rules
Grafana (Port 3000) ← queries Prometheus
    ↓ renders dashboards
```

### Data Flow

1. **Metrics Collection**: 8 Prometheus metrics exposed via Flask `/metrics` endpoint in scheduler
2. **Scraping**: Prometheus scrapes `localhost:9090/metrics` every 15 seconds
3. **Alerting**: Prometheus evaluates 6 alert rules every 30 seconds
4. **Visualization**: Grafana queries Prometheus and renders 8-panel trading dashboard

### Files Created

- `src/monitoring/prometheus_metrics.py` - Core metrics module (8 metrics)
- `monitoring/prometheus/prometheus.yml` - Prometheus config (15s scrape)
- `monitoring/prometheus/rules.yml` - Alert rules (6 alerts)
- `monitoring/grafana/dashboards/trading_overview.json` - Dashboard (8 panels)
- `monitoring/grafana/datasources/prometheus.yml` - Datasource provisioning
- `monitoring/grafana/dashboards/dashboards.yml` - Dashboard provisioning
- `docker-compose.monitoring.yml` - Docker Compose stack

## Quick Start

### 1. Start the Monitoring Stack

```bash
cd /home/miko/LAB/projects/THUNES

# Start Prometheus + Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Verify containers are running
docker-compose -f docker-compose.monitoring.yml ps

# Expected output:
# NAME                 STATUS              PORTS
# thunes-prometheus    Up 30 seconds       0.0.0.0:9090->9090/tcp
# thunes-grafana       Up 30 seconds       0.0.0.0:3000->3000/tcp
```

### 2. Start the THUNES Scheduler

The scheduler automatically starts the Flask metrics server on port 9090:

```bash
# Test mode (1 hour)
python src/orchestration/run_scheduler.py --test-mode --duration=3600

# Production mode (indefinitely)
python src/orchestration/run_scheduler.py

# Expected log output:
# INFO - Starting Prometheus metrics server on port 9090...
# INFO - Metrics server started: http://0.0.0.0:9090/metrics
```

### 3. Verify Metrics Endpoint

```bash
# Check metrics endpoint is responding
curl http://localhost:9090/metrics | grep thunes_

# Expected output (sample):
# thunes_kill_switch_active 0.0
# thunes_circuit_breaker_state{breaker_name="BinanceAPI"} 0.0
# thunes_daily_pnl_used 0.0
# thunes_open_positions 0.0
# thunes_orders_placed_total{venue="binance",order_type="MARKET",side="BUY"} 0.0
```

### 4. Access Grafana Dashboard

1. Open browser: `http://localhost:3000`
2. Login credentials:
   - **Username**: `admin`
   - **Password**: `thunes123`
3. Navigate to: **Dashboards → Trading → THUNES Trading Overview**

## Metrics Reference

### Core Metrics (8 Total)

| Metric | Type | Description | Labels | Integration Point |
|--------|------|-------------|--------|------------------|
| `thunes_kill_switch_active` | Gauge | Kill-switch status (0=inactive, 1=active) | - | `RiskManager.activate_kill_switch()` |
| `thunes_circuit_breaker_state` | Gauge | Circuit breaker state (0=CLOSED, 1=OPEN, 0.5=HALF_OPEN) | `breaker_name` | `CircuitBreakerListener.state_change()` |
| `thunes_daily_pnl_used` | Gauge | Daily PnL as fraction of limit (0.0-1.0+) | - | `RiskManager.validate_trade()` |
| `thunes_open_positions` | Gauge | Number of open positions (0-3) | - | `RiskManager.validate_trade()` |
| `thunes_orders_placed_total` | Counter | Total orders placed (cumulative) | `venue`, `order_type`, `side` | `PaperTrader.place_market_order()` |
| `thunes_order_latency_ms` | Histogram | Order placement latency (5-1000ms buckets) | - | `PaperTrader.place_market_order()` |
| `thunes_ws_gap_seconds` | Histogram | WebSocket message gap (0.1-60s buckets) | - | Future: WebSocket stream |
| `thunes_ws_connected` | Gauge | WebSocket connection status (0=disconnected, 1=connected) | `symbol` | Future: WebSocket stream |

### Metric Helpers

```python
from src.monitoring import prometheus_metrics

# Kill-switch
prometheus_metrics.update_kill_switch_metric(active=True)

# Circuit breaker
prometheus_metrics.update_circuit_breaker_metric(breaker_name="BinanceAPI", state="open")

# Risk metrics
prometheus_metrics.update_risk_metrics(
    daily_pnl=15.0,
    max_daily_loss=20.0,
    position_count=2,
)

# Order tracking
prometheus_metrics.record_order_placed(
    venue="binance",
    order_type="MARKET",
    side="BUY",
    latency_ms=125.5,
)

# WebSocket (future)
prometheus_metrics.record_ws_message_gap(symbol="BTCUSDT", gap_seconds=1.2)
prometheus_metrics.update_ws_connection(symbol="BTCUSDT", connected=True)
```

## Alert Configuration

### Alert Rules (6 Total, 4 Required + 2 Bonus)

#### 1. **KillSwitchActive** (CRITICAL)

```yaml
alert: KillSwitchActive
expr: thunes_kill_switch_active == 1
for: 5m
labels:
  severity: critical
annotations:
  summary: "THUNES kill-switch activated"
  description: "Trading halted due to daily loss exceeding MAX_DAILY_LOSS"
```

**Action**: Check `logs/audit_trail.jsonl` for trigger reason, review daily PnL

#### 2. **CircuitBreakerOpen** (WARNING)

```yaml
alert: CircuitBreakerOpen
expr: thunes_circuit_breaker_state{breaker_name="BinanceAPI"} == 1
for: 10m
labels:
  severity: warning
```

**Action**: Check Binance API status, verify network connectivity

#### 3. **WebSocketDisconnected** (WARNING)

```yaml
alert: WebSocketDisconnected
expr: thunes_ws_connected == 0
for: 2m
```

**Action**: Check WebSocket logs, verify API keys not expired

#### 4. **HighOrderLatency** (WARNING)

```yaml
alert: HighOrderLatency
expr: histogram_quantile(0.95, rate(thunes_order_latency_ms_bucket[5m])) > 500
for: 5m
```

**Action**: Check network latency, consider switching testnet regions

#### 5. **DailyPnLLimitApproaching** (INFO, Bonus)

```yaml
alert: DailyPnLLimitApproaching
expr: thunes_daily_pnl_used > 0.8
for: 5m
labels:
  severity: info
```

**Action**: Monitor closely, prepare for kill-switch activation

#### 6. **MaxPositionsReached** (INFO, Bonus)

```yaml
alert: MaxPositionsReached
expr: thunes_open_positions >= 3
for: 1m
labels:
  severity: info
```

**Action**: Normal operation, no new positions until one closes

### Alert Firing Check

```bash
# Check Prometheus alerts page
open http://localhost:9090/alerts

# Query specific alert
curl -s 'http://localhost:9090/api/v1/query?query=ALERTS{alertname="KillSwitchActive"}'
```

## Grafana Dashboard

### Panels (8 Total, 6 Required + 2 Bonus)

#### 1. **Daily PnL Usage** (Graph with threshold)
- **Metric**: `thunes_daily_pnl_used`
- **Format**: Percent (0-100%)
- **Alert Threshold**: Red zone at 80%
- **Purpose**: Visual warning when approaching daily loss limit

#### 2. **Open Positions** (Stat)
- **Metric**: `thunes_open_positions`
- **Color Thresholds**: Green (0-1), Yellow (2), Red (3)
- **Purpose**: Current position count with visual status

#### 3. **Kill-Switch Status** (Stat)
- **Metric**: `thunes_kill_switch_active`
- **Mapping**: 0 → "OK" (Green), 1 → "ACTIVE" (Red)
- **Purpose**: Instant visual kill-switch state

#### 4. **Circuit Breaker State** (Stat)
- **Metric**: `thunes_circuit_breaker_state{breaker_name="BinanceAPI"}`
- **Mapping**: 0 → "CLOSED", 0.5 → "HALF-OPEN", 1 → "OPEN"
- **Purpose**: Circuit breaker fault tolerance state

#### 5. **Order Latency** (Graph)
- **Metric**: `histogram_quantile(0.5|0.95|0.99, rate(thunes_order_latency_ms_bucket[5m]))`
- **Lines**: p50 (median), p95, p99
- **Purpose**: Order execution performance monitoring

#### 6. **WebSocket Health** (Stat per symbol)
- **Metric**: `thunes_ws_connected{symbol="BTCUSDT"}`
- **Format**: 0 → "DISCONNECTED", 1 → "CONNECTED"
- **Purpose**: Real-time data feed status

#### 7. **Orders Placed (24h)** (Bonus Stat)
- **Metric**: `increase(thunes_orders_placed_total[24h])`
- **Purpose**: Daily trading activity summary

#### 8. **WebSocket Message Gap** (Bonus Graph)
- **Metric**: `histogram_quantile(0.95, rate(thunes_ws_gap_seconds_bucket[5m]))`
- **Purpose**: Data feed latency monitoring

### Dashboard Access

1. Navigate to: `http://localhost:3000/d/thunes-trading-overview`
2. Time range selector: Last 1 hour (default)
3. Auto-refresh: 15 seconds (recommended for live monitoring)

## Testing & Validation

### 1. Smoke Test (All Components)

```bash
# Start stack
docker-compose -f docker-compose.monitoring.yml up -d

# Start scheduler
python src/orchestration/run_scheduler.py --test-mode --duration=600

# Wait 30 seconds for metrics to populate

# Verify metrics
curl http://localhost:9090/metrics | grep -E "thunes_(kill_switch|circuit_breaker|daily_pnl|open_positions)"

# Expected: All metrics present with initial values
```

### 2. Kill-Switch Alert Test

Manually trigger kill-switch to verify alert fires:

```python
# In Python shell
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

rm = RiskManager(position_tracker=PositionTracker())

# Manually trigger kill-switch
rm.activate_kill_switch(reason="Test: Manual activation for alert testing")

# Verify metric updated
# curl http://localhost:9090/metrics | grep kill_switch
# Expected: thunes_kill_switch_active 1.0

# Check Prometheus alert (wait 5 minutes)
# open http://localhost:9090/alerts
# Expected: KillSwitchActive alert FIRING

# Deactivate
rm.deactivate_kill_switch()
```

### 3. Circuit Breaker Alert Test

Trigger circuit breaker to verify state tracking:

```python
# In Python shell
from src.utils.circuit_breaker import binance_api_breaker

# Open circuit manually (simulates 5 consecutive failures)
for _ in range(5):
    try:
        binance_api_breaker.call(lambda: (_ for _ in ()).throw(Exception("Test error")))
    except:
        pass

# Verify metric
# curl http://localhost:9090/metrics | grep circuit_breaker
# Expected: thunes_circuit_breaker_state{breaker_name="BinanceAPI"} 1.0

# Check alert (wait 10 minutes)
# open http://localhost:9090/alerts
# Expected: CircuitBreakerOpen alert FIRING

# Close circuit (wait 60s for reset timeout)
binance_api_breaker.close()
```

### 4. Order Latency Test

Place test orders to verify latency tracking:

```bash
# Run paper trader with test trades
pytest tests/test_paper_trader_integration.py::test_place_market_order -v

# Query latency metrics
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95, rate(thunes_order_latency_ms_bucket[5m]))'

# Expected: p95 latency value (should be < 500ms for testnet)
```

### 5. Grafana Dashboard Test

1. Navigate to `http://localhost:3000/d/thunes-trading-overview`
2. Verify all 8 panels render without errors
3. Check data points appear in graphs (may need to wait 1-2 minutes)
4. Test time range selector (Last 1h, Last 6h, Last 24h)
5. Verify alert annotations appear on graphs (if alerts fired)

## Integration with Phase 13 Rodage

### Pre-Rodage Checklist

**Before starting 7-day testnet rodage, verify:**

- [ ] Monitoring stack starts cleanly: `docker-compose -f docker-compose.monitoring.yml up -d`
- [ ] Scheduler exposes metrics: `curl http://localhost:9090/metrics | grep thunes_`
- [ ] Prometheus scraping works: Check `http://localhost:9090/targets` (status: UP)
- [ ] Grafana dashboard renders: `http://localhost:3000/d/thunes-trading-overview`
- [ ] Kill-switch alert fires: Manual test passes (see Testing section)
- [ ] All 6 alert rules present: `http://localhost:9090/rules`

### During Rodage Monitoring

**Daily checks (7-day rodage):**

```bash
# Morning check (09:00)
docker-compose -f docker-compose.monitoring.yml ps  # Verify containers UP
curl http://localhost:9090/-/healthy                # Prometheus health
curl http://localhost:3000/api/health               # Grafana health

# Review Grafana dashboard
open http://localhost:3000/d/thunes-trading-overview

# Check alert status
open http://localhost:9090/alerts

# Export metrics for analysis
curl -s 'http://localhost:9090/api/v1/query?query={__name__=~"thunes_.*"}' > logs/metrics_$(date +%Y%m%d_%H%M).json
```

**Key metrics to monitor:**

| Metric | Normal Range | Action Threshold |
|--------|--------------|------------------|
| `thunes_daily_pnl_used` | 0.0 - 0.6 | > 0.8 → Prepare for kill-switch |
| `thunes_open_positions` | 0 - 2 | 3 → Max capacity reached |
| `thunes_order_latency_ms` (p95) | < 250ms | > 500ms → Network issues |
| `thunes_circuit_breaker_state` | 0.0 (CLOSED) | 1.0 (OPEN) → API issues |
| `thunes_kill_switch_active` | 0.0 | 1.0 → Trading halted |

### Post-Rodage Analysis

After 7-day rodage, analyze metrics for Phase 14 planning:

```bash
# Export full metrics history
curl -s 'http://localhost:9090/api/v1/query_range?query=thunes_daily_pnl_used&start=$(date -d "7 days ago" +%s)&end=$(date +%s)&step=300' > logs/pnl_history_7d.json

# Generate summary statistics
python scripts/analyze_rodage_metrics.py logs/pnl_history_7d.json

# Check alert frequency
curl -s 'http://localhost:9090/api/v1/query?query=ALERTS{alertname=~".*"}' > logs/alerts_summary.json
```

**Success criteria for Phase 13:**
- No kill-switch activations (unless manually tested)
- Circuit breaker state = CLOSED (99%+ uptime)
- Order latency p95 < 500ms
- Zero missed WebSocket messages (when implemented)
- All alerts fire correctly (verified via manual testing)

## Troubleshooting

### Prometheus Not Scraping

**Symptom**: Grafana shows "No data" in all panels

**Diagnosis**:
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'

# Expected: health="up", lastError=""
```

**Fix**:
```bash
# Verify scheduler metrics endpoint is running
curl http://localhost:9090/metrics | head -5

# If no response, restart scheduler
python src/orchestration/run_scheduler.py --test-mode

# If still failing, check Prometheus logs
docker-compose -f docker-compose.monitoring.yml logs prometheus | grep error
```

### Grafana Datasource Not Connected

**Symptom**: Grafana shows "Datasource not found"

**Diagnosis**:
```bash
# Check Grafana datasources
curl -s http://admin:thunes123@localhost:3000/api/datasources | jq '.'

# Expected: Name="Prometheus", url="http://prometheus:9090"
```

**Fix**:
```bash
# Recreate Grafana container (preserves data via volumes)
docker-compose -f docker-compose.monitoring.yml restart grafana

# Wait 30s, refresh dashboard
```

### Metrics Not Updating

**Symptom**: Metrics show stale values (e.g., positions = 0 after trade)

**Diagnosis**:
```bash
# Check if metric helper is called
tail -f logs/paper_trader.log | grep "Order executed"

# Verify metric value updates
watch -n 1 'curl -s http://localhost:9090/metrics | grep thunes_orders_placed_total'
```

**Fix**: Verify integration points in code:
- `RiskManager.validate_trade()` → calls `update_risk_metrics()`
- `PaperTrader.place_market_order()` → calls `record_order_placed()`
- `CircuitBreakerListener.state_change()` → calls `update_circuit_breaker_metric()`

### Alerts Not Firing

**Symptom**: KillSwitchActive alert doesn't fire when kill-switch activates

**Diagnosis**:
```bash
# Check alert evaluation
curl -s 'http://localhost:9090/api/v1/query?query=thunes_kill_switch_active'

# Expected: value="1" when kill-switch active

# Check alert rule status
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[] | select(.name=="thunes_critical_alerts") | .rules[] | select(.name=="KillSwitchActive")'
```

**Fix**:
```bash
# Reload Prometheus rules
docker-compose -f docker-compose.monitoring.yml restart prometheus

# Verify rules loaded
curl http://localhost:9090/api/v1/rules | jq '.data.groups[].name'
```

### Container Health Check Failures

**Symptom**: `docker-compose ps` shows "unhealthy" status

**Diagnosis**:
```bash
# Check container logs
docker-compose -f docker-compose.monitoring.yml logs prometheus | tail -20
docker-compose -f docker-compose.monitoring.yml logs grafana | tail -20

# Check health endpoint
docker exec thunes-prometheus wget --spider http://localhost:9090/-/healthy
```

**Fix**:
```bash
# Restart unhealthy container
docker-compose -f docker-compose.monitoring.yml restart prometheus

# If still failing, check resource limits
docker stats thunes-prometheus thunes-grafana
```

---

## Next Steps

After deployment and validation:

1. **Phase 11 Sprint 2.4**: Integrate WebSocket metrics (ws_gap_seconds, ws_connected)
2. **Phase 11 Sprint 2.5**: Add Loki log aggregation (optional)
3. **Phase 13 Rodage**: 7-day monitoring with alert verification
4. **Phase 14 Pre-Live**: Export rodage metrics for audit trail

## Related Documentation

- `PHASE_13_SPRINTS.md` - Sprint 2.3 specification
- `src/monitoring/prometheus_metrics.py` - Metrics implementation
- `monitoring/prometheus/rules.yml` - Alert rules reference
- `docs/OPERATIONAL-RUNBOOK.md` - Disaster recovery procedures

---

**Version**: 1.0.0
**Author**: Claude Code
**Phase**: 11 (Observability)
**Status**: ✅ Complete
