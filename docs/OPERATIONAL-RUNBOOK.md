# THUNES Operational Runbook

**Version**: 1.0
**Last Updated**: 2025-10-03
**Owner**: System Administrator
**Purpose**: Disaster recovery, incident response, and operational procedures

---

## 📋 Table of Contents

1. [System Architecture](#system-architecture)
2. [Failure Scenarios & Response](#failure-scenarios--response)
3. [API Key Management](#api-key-management)
4. [Monitoring Checklist](#monitoring-checklist)
5. [Emergency Contacts](#emergency-contacts)
6. [Appendix: Common Commands](#appendix-common-commands)

---

## System Architecture

### Component Map

```
┌─────────────────────────────────────────────────────────┐
│                    THUNES Architecture                   │
└─────────────────────────────────────────────────────────┘

External Services:
├── Binance API (spot trading)
│   ├── REST: https://testnet.binance.vision (testnet)
│   ├── WebSocket: wss://testnet.binance.vision/ws (real-time)
│   └── Rate Limits: 1200 req/min (REST), 5 connections (WS)
│
└── Telegram Bot API
    └── https://api.telegram.org/bot<token>/

Core Components:
├── Orchestrator (src/orchestration/scheduler.py)
│   ├── Signal Check Job (every 10 min)
│   ├── Daily Summary Job (23:00 UTC)
│   └── APScheduler (single-threaded)
│
├── Trading Engine (src/live/paper_trader.py)
│   ├── Strategy: SMA Crossover / RSI
│   ├── Data: WebSocket (primary) + REST (fallback)
│   └── Order Execution: Binance market orders
│
├── Risk Manager (src/risk/manager.py)
│   ├── Kill-Switch: Daily loss limit
│   ├── Position Limits: Max 3 concurrent
│   ├── Cool-Down: 60 min after loss
│   └── Audit Trail: logs/audit_trail.jsonl
│
├── Circuit Breaker (src/utils/circuit_breaker.py)
│   ├── Threshold: 5 failures in 60s
│   ├── Open Duration: 60s
│   └── Protected: Binance API calls
│
└── Position Tracker (src/models/position.py)
    └── SQLite: logs/positions.db

Data Flow:
WebSocket → Strategy → Risk Manager → Exchange Filters → Binance API
```

### Critical Dependencies

| Dependency | Version | Purpose | Failure Impact |
|------------|---------|---------|----------------|
| python-binance | 1.0.19 | Exchange API wrapper | CRITICAL - trading stops |
| APScheduler | 3.10.4 | Job scheduling | CRITICAL - autonomous operation fails |
| websockets | 12.0 | Real-time data | HIGH - falls back to REST |
| pybreaker | 1.4.1 | Circuit breaker | MEDIUM - no fault tolerance |
| SQLite | 3.x | Position persistence | MEDIUM - positions lost on restart |

### External Service SLAs

| Service | SLA | Monitored By | Fallback |
|---------|-----|--------------|----------|
| Binance API | 99.9% | Circuit breaker | None (manual) |
| Binance WebSocket | 99.5% | Watchdog thread | REST API |
| Telegram API | 99.0% | Graceful failure | Logs only |

---

## Failure Scenarios & Response

### 🔴 CRITICAL: Kill-Switch Activation

**Trigger**: Daily loss ≥ `MAX_DAILY_LOSS` (default: 20 USDT)

**Automatic Response**:
1. Block all new BUY orders
2. Allow SELL orders (to exit positions)
3. Send Telegram alert
4. Log to audit trail

**Detection**:
```bash
# Check kill-switch status
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
print(f'Kill-Switch Active: {rm.kill_switch_active}')
print(f'Daily PnL: {rm.get_daily_pnl():.2f} USDT')
"
```

**Manual Investigation**:
1. Review audit trail for rejected trades:
   ```bash
   grep "KILL_SWITCH" logs/audit_trail.jsonl | tail -20
   ```

2. Analyze losing trades:
   ```python
   from src.models.position import PositionTracker
   tracker = PositionTracker()
   losses = [p for p in tracker.get_closed_positions_today() if p.pnl < 0]
   for p in losses:
       print(f"{p.symbol}: PnL={p.pnl:.2f}, Entry={p.entry_price}, Exit={p.exit_price}")
   ```

3. Check if market condition changed (volatility spike, flash crash)

**Deactivation** (⚠️ Only after root cause identified):
```python
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

rm = RiskManager(position_tracker=PositionTracker())
rm.deactivate_kill_switch()  # Requires manual confirmation
print("Kill-switch deactivated - trading resumed")
```

**Root Cause Checklist**:
- [ ] Strategy parameters no longer optimal (market regime change)?
- [ ] Binance API issues causing bad fills?
- [ ] Bug in strategy logic (look-ahead bias, filter bypass)?
- [ ] Position sizing too aggressive for volatility?

---

### ⚠️ HIGH: WebSocket Disconnection

**Trigger**: No messages received for >60 seconds

**Automatic Response**:
1. Watchdog thread detects stale connection
2. Queue reconnection request to control thread
3. Exponential backoff (1s, 2s, 4s, 8s, 16s)
4. Max 5 reconnection attempts
5. If all fail → fall back to REST API

**Detection**:
```bash
# Check WebSocket logs
tail -f logs/paper_trader.log | grep -i "websocket\|watchdog"

# Look for:
# - "WebSocket unhealthy: no messages for 60s"
# - "Attempting reconnection (attempt X/5)"
# - "WebSocket reconnected successfully"
```

**Manual Recovery** (if automatic fails):
```bash
# 1. Check network connectivity
ping binance.com

# 2. Verify WebSocket endpoint accessible
curl -I https://testnet.binance.vision

# 3. Restart scheduler (will reinitialize WebSocket)
pkill -f run_scheduler
python -m src.orchestration.run_scheduler &
```

**Fallback Validation**:
```bash
# Verify REST API fallback working
tail logs/paper_trader.log | grep "REST fallback"
# Should see: "Using REST fallback for price data"
```

**Escalation**: If WebSocket fails repeatedly (>5 times/hour):
1. Check Binance status: https://www.binance.com/en/support/announcement
2. Check local firewall rules
3. Switch to REST-only mode (edit `paper_trader.py:65` to disable WebSocket)

---

### ⚡ MEDIUM: Circuit Breaker Trip

**Trigger**: 5 consecutive API errors within 60 seconds

**Automatic Response**:
1. Circuit opens (blocks all API calls)
2. Wait 60 seconds (reset timeout)
3. Transition to HALF_OPEN (test with 1 request)
4. If successful → CLOSED, if fail → OPEN again

**Detection**:
```bash
# Check circuit breaker status
python -c "
from src.utils.circuit_breaker import circuit_monitor
status = circuit_monitor.get_status()
for name, info in status.items():
    print(f'{name}: {info[\"state\"]} ({info[\"fail_counter\"]}/{info[\"fail_max\"]} failures)')
"
```

**Manual Investigation**:
1. Check Binance API status:
   ```bash
   curl -X GET "https://testnet.binance.vision/api/v3/ping"
   # Expected: {}
   ```

2. Review error logs:
   ```bash
   grep "Circuit breaker" logs/paper_trader.log | tail -20
   ```

3. Check for client errors (4xx) vs server errors (5xx):
   ```bash
   # Client errors DON'T trip circuit (e.g., invalid order params)
   # Server errors DO trip circuit (e.g., 503 Service Unavailable)
   grep "BinanceAPIException" logs/paper_trader.log | tail -10
   ```

**Manual Reset** (⚠️ Use cautiously):
```python
from src.utils.circuit_breaker import circuit_monitor
circuit_monitor.reset_all()
print("All circuit breakers reset to CLOSED state")
```

**Prevention**:
- Circuit breaker is **working as designed** - prevents cascading failures
- If tripping frequently (>3 times/day), investigate root cause:
  - Binance API degradation?
  - Network issues?
  - Bug in order placement logic?

---

### 🛠️ MEDIUM: Scheduler Crash

**Trigger**: Scheduler process terminates unexpectedly

**Detection**:
```bash
# Check if scheduler running
ps aux | grep "run_scheduler" | grep -v grep

# If no output → scheduler crashed

# Check for crash logs
tail -100 logs/paper_trader.log | grep -i "error\|exception\|traceback"
```

**Root Causes**:
1. **Unhandled exception in job**: Check logs for Python tracebacks
2. **Out of memory**: Check system resources (`free -h`, `df -h`)
3. **SQLite lock timeout**: Concurrent writes to `logs/jobs.db`

**Manual Recovery**:
```bash
# 1. Archive crash logs for analysis
cp logs/paper_trader.log "logs/crash-$(date +%Y%m%d-%H%M%S).log"

# 2. Check disk space (common cause)
df -h logs/

# 3. Restart scheduler
python -m src.orchestration.run_scheduler &

# 4. Verify startup
tail -f logs/paper_trader.log
# Look for: "Scheduler started successfully"
```

**Automated Recovery** (systemd - Phase 14):
```ini
# /etc/systemd/system/thunes-scheduler.service
[Unit]
Description=THUNES Trading Scheduler
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/THUNES
ExecStart=/home/trader/THUNES/.venv/bin/python -m src.orchestration.run_scheduler
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Enable auto-restart:
```bash
sudo systemctl enable thunes-scheduler
sudo systemctl start thunes-scheduler
```

---

### 📊 MEDIUM: Position Desync

**Trigger**: Local SQLite positions don't match exchange balances

**Scenario**: System places BUY order, receives confirmation, crashes before updating SQLite

**Detection**:
```python
# Manual reconciliation check
from binance.client import Client
from src.config import settings
from src.models.position import PositionTracker

client = Client(settings.api_key, settings.api_secret, testnet=True)
tracker = PositionTracker()

# 1. Get exchange balances
account = client.get_account()
exchange_holdings = {
    b["asset"]: float(b["free"]) + float(b["locked"])
    for b in account["balances"]
    if float(b["free"]) > 0 or float(b["locked"]) > 0
}

# 2. Get local positions
local_positions = tracker.get_all_open_positions()
local_holdings = {pos.symbol[:-4]: float(pos.quantity) for pos in local_positions}

# 3. Compare
print("Exchange Holdings:", exchange_holdings)
print("Local Positions:", local_holdings)

# Flag discrepancies
for asset, qty in exchange_holdings.items():
    if asset not in ["USDT", "BNB"]:  # Ignore quote currencies
        local_qty = local_holdings.get(asset, 0.0)
        if abs(qty - local_qty) > 0.00001:
            print(f"⚠️ MISMATCH: {asset} - Exchange: {qty}, Local: {local_qty}")
```

**Manual Recovery**:
```python
# If exchange has MORE than local (failed SELL detection):
tracker.close_position(
    symbol="BTCUSDT",
    exit_price=current_market_price,
    exit_order_id="MANUAL_RECONCILIATION"
)

# If local has MORE than exchange (orphaned OPEN position):
# Review audit trail to find when position should have closed
tracker.mark_position_closed(position_id=123)
```

**Prevention** (Phase 14 enhancement):
- Implement hourly reconciliation job
- Send Telegram alert on discrepancy
- See: `src/monitoring/reconciliation.py` (to be implemented)

---

### 🔐 CRITICAL: API Key Compromise

**Indicators**:
- Unexpected trades in Binance order history
- Positions opened outside scheduler hours
- Unusual asset holdings

**Immediate Response** (within 5 minutes):
```bash
# 1. DISABLE API KEY (via Binance web UI)
# https://testnet.binance.vision/ → API Management → Delete Key

# 2. STOP SCHEDULER (prevent further access attempts)
pkill -f run_scheduler

# 3. ROTATE TO NEW KEY
# - Generate new key with same permissions
# - Update .env file
# - Restart scheduler with new credentials

# 4. REVIEW AUDIT TRAIL
grep "TRADE_APPROVED\|TRADE_REJECTED" logs/audit_trail.jsonl | \
  jq -r 'select(.timestamp >= "2025-10-03T00:00:00")'

# 5. COMPARE WITH BINANCE ORDER HISTORY
# Download CSV from Binance → check for unauthorized trades
```

**Forensic Analysis**:
1. Check git history for accidental key commits:
   ```bash
   git log -S "BINANCE_.*_API_KEY" --all
   ```

2. Review system access logs:
   ```bash
   sudo last | grep trader
   ```

3. Scan for malware:
   ```bash
   sudo rkhunter --check
   ```

**Post-Incident**:
- Update `.env.example` to use placeholder values
- Add pre-commit hook for secret detection
- Enable Binance IP whitelist (requires static IP)

---

## API Key Management

### Key Permissions (Principle of Least Privilege)

**Required Permissions**:
- ✅ **Enable Spot & Margin Trading**: ON
- ✅ **Enable Reading**: ON

**Prohibited Permissions** (⚠️ NEVER ENABLE):
- ❌ **Enable Withdrawals**: OFF (critical security control)
- ❌ **Enable Futures**: OFF (not needed for spot trading)
- ❌ **Enable Internal Transfer**: OFF (prevents fund movement)

### Rotation Schedule

| Environment | Rotation Frequency | Next Due | Responsible |
|-------------|-------------------|----------|-------------|
| **Testnet** | Every 90 days | 2026-01-02 | System Owner |
| **Production** | Every 30 days | TBD | System Owner |
| **After Incident** | Immediate | N/A | System Owner |

### Rotation Procedure

```bash
# 1. Generate new key via Binance web UI
# testnet: https://testnet.binance.vision/
# production: https://www.binance.com/en/my/settings/api-management

# 2. Update .env file
cd ~/THUNES
nano .env
# Replace BINANCE_*_API_KEY and BINANCE_*_API_SECRET

# 3. Verify new credentials
python -c "
from binance.client import Client
from src.config import settings
client = Client(settings.api_key, settings.api_secret, testnet=True)
print(client.get_account()['canTrade'])  # Should print: True
"

# 4. Restart scheduler with new credentials
pkill -f run_scheduler
python -m src.orchestration.run_scheduler &

# 5. Delete old key from Binance web UI

# 6. Document rotation in runbook
echo "$(date): API key rotated" >> docs/key-rotation-log.txt
```

### Key Storage Security

**Current** (Testnet):
- Location: `.env` file (git-ignored)
- Permissions: `chmod 600 .env` (owner read/write only)
- Backup: Encrypted password manager (1Password, Bitwarden)

**Production** (Phase 14):
- **Option 1**: AWS Secrets Manager
  ```python
  import boto3
  secrets = boto3.client('secretsmanager')
  api_key = secrets.get_secret_value(SecretId='thunes/binance_api_key')['SecretString']
  ```

- **Option 2**: HashiCorp Vault
  ```bash
  vault kv get -field=api_key secret/thunes/binance
  ```

- **Option 3**: Encrypted `.env` with `python-dotenv` + `cryptography`

---

## Monitoring Checklist

### Daily (10-15 minutes)

**Time**: 09:00 UTC (before market volatility)

```bash
# 1. Check Telegram for overnight alerts
# Look for:
# - Kill-switch activations
# - Circuit breaker trips
# - Position reconciliation mismatches

# 2. Verify scheduler is running
ps aux | grep run_scheduler | grep -v grep
# Expected: 1 process

# 3. Review daily summary (sent by Telegram at 23:00 UTC)
# Metrics to check:
# - Daily PnL (should be within ±5% of expected)
# - Win rate (should be 40-60%)
# - Open positions count (should be 0-3)

# 4. Spot-check logs for errors
tail -100 logs/paper_trader.log | grep -i "error\|exception" | wc -l
# Expected: <5 errors/day

# 5. Check disk space
df -h logs/
# Expected: <50% usage
```

### Weekly (30-45 minutes)

**Time**: Monday 10:00 UTC

```bash
# 1. Calculate rolling Sharpe ratio
python -c "
from src.monitoring.performance_tracker import PerformanceTracker
tracker = PerformanceTracker()
sharpe = tracker.calculate_sharpe_ratio(window_days=7)
print(f'7-Day Sharpe Ratio: {sharpe:.2f}')
"
# Expected: >1.0 (good), >1.5 (excellent), <0.5 (investigate)

# 2. Review circuit breaker trip count
grep "Circuit breaker" logs/paper_trader.log | grep "state changed" | wc -l
# Expected: <5 trips/week

# 3. Audit trail integrity check
python scripts/validate_audit_trail.py
# Expected: ✅ JSONL format valid

# 4. Check for security scan findings (GitHub Actions)
# Navigate to: https://github.com/<user>/THUNES/actions
# Review: Security Audit workflow results

# 5. Review open positions age
python -c "
from src.models.position import PositionTracker
from datetime import datetime
tracker = PositionTracker()
for pos in tracker.get_all_open_positions():
    age_hours = (datetime.utcnow() - pos.entry_time).total_seconds() / 3600
    print(f'{pos.symbol}: {age_hours:.1f}h old')
"
# Flag if any position >72h old (stale position)
```

### Monthly (2-3 hours)

**Time**: First Monday of month, 14:00 UTC

```bash
# 1. Full audit trail analysis
python -c "
import json
events = []
with open('logs/audit_trail.jsonl') as f:
    events = [json.loads(line) for line in f]

approved = len([e for e in events if e['event'] == 'TRADE_APPROVED'])
rejected = len([e for e in events if e['event'] == 'TRADE_REJECTED'])

print(f'Total events: {len(events)}')
print(f'Approved trades: {approved}')
print(f'Rejected trades: {rejected}')
print(f'Rejection rate: {rejected/(approved+rejected)*100:.1f}%')
"
# Expected rejection rate: 10-30% (safety controls working)

# 2. Performance review
python -c "
from src.monitoring.performance_tracker import PerformanceTracker
tracker = PerformanceTracker()
print(f'30-Day Sharpe: {tracker.calculate_sharpe_ratio(window_days=30):.2f}')
print(f'30-Day Return: {tracker.calculate_total_return(window_days=30):.2f}%')
print(f'Max Drawdown: {tracker.calculate_max_drawdown():.2f}%')
"

# 3. API key rotation (if due)
# See: API Key Management → Rotation Schedule

# 4. Dependency updates
pip list --outdated
# Review for security patches, test on testnet before upgrading

# 5. Backup critical data
tar -czf "backup-$(date +%Y%m%d).tar.gz" \
  logs/audit_trail.jsonl \
  logs/positions.db \
  .env
# Store backup in secure location (encrypted S3, external drive)
```

---

## Emergency Contacts

### Internal

| Role | Contact | Availability |
|------|---------|--------------|
| **System Owner** | [Your Name/Email] | 24/7 |
| **Backup Admin** | [Backup Contact] | Business hours |

### External

| Service | Support | URL |
|---------|---------|-----|
| **Binance Support** | support@binance.com | https://www.binance.com/en/support |
| **Binance Status** | N/A | https://www.binance.com/en/support/announcement |
| **Telegram Bot Issues** | @BotFather | https://t.me/botfather |

### Escalation Path

```
Level 1: Automated recovery (circuit breaker, WebSocket reconnect)
   ↓
Level 2: Manual investigation (check logs, validate state)
   ↓
Level 3: Service restart (scheduler, WebSocket)
   ↓
Level 4: Emergency shutdown (kill-switch, stop all trading)
   ↓
Level 5: External support (Binance, GitHub issues)
```

---

## Appendix: Common Commands

### System Health

```bash
# Check all critical processes
ps aux | grep -E "(run_scheduler|python.*paper_trader)"

# Monitor logs in real-time
tail -f logs/paper_trader.log logs/audit_trail.jsonl

# Check system resources
free -h && df -h && uptime
```

### Trading Operations

```bash
# Get current account balance
python -c "
from src.live.paper_trader import PaperTrader
trader = PaperTrader()
print(f'USDT: {trader.get_account_balance(\"USDT\")}')
"

# List open positions
python -c "
from src.models.position import PositionTracker
tracker = PositionTracker()
for pos in tracker.get_all_open_positions():
    print(f'{pos.symbol}: {pos.quantity} @ {pos.entry_price}')
"

# Calculate current PnL
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
print(f'Daily PnL: {rm.get_daily_pnl():.2f} USDT')
"
```

### Troubleshooting

```bash
# Test Binance API connectivity
curl -X GET "https://testnet.binance.vision/api/v3/ping"

# Test Telegram bot
python scripts/verify_telegram.py

# Validate configuration
python -c "
from src.config import settings
print(f'Environment: {settings.environment}')
print(f'Symbol: {settings.default_symbol}')
print(f'Testnet: {settings.is_testnet}')
"

# Run full test suite
pytest -v --tb=short

# Run specific component tests
pytest tests/test_risk_manager.py -v
pytest tests/test_ws_stream.py -v
```

---

**End of Runbook**

**Next Review**: 2025-11-03 (monthly)
**Change Log**: See git history for `docs/OPERATIONAL-RUNBOOK.md`
