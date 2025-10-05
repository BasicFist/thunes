# THUNES Phase 14: Micro-Live Production

**Version**: 1.0
**Last Updated**: 2025-10-05
**Duration**: 4 weeks (160 hours)
**Prerequisites**: Phase 13 GO decision ✅
**Capital at Risk**: €10-50 (start €10, increase to €20 after Week 2)

---

## Overview

Phase 14 transitions from paper trading to live production with real capital. This phase focuses on **risk mitigation** through:

1. **Minimal Capital Exposure**: Start with €10 (micro-live)
2. **Enhanced Monitoring**: Position reconciliation, chaos testing
3. **Production Infrastructure**: Secrets manager, systemd, log rotation
4. **Gradual Scaling**: Increase capital only after validation milestones

---

## Week 1: Production Infrastructure Setup (40h)

### Day 1-2: Binance Live API & Secrets Management (16h)

#### Binance Live API Keys (4h)

**Prerequisites**:
- Binance account verified (KYC complete)
- 2FA enabled (mandatory for live trading)
- Initial deposit: €50 (€10 for trading, €40 reserve)

**API Key Configuration**:

1. Generate new API key: https://www.binance.com/en/my/settings/api-management

2. **Required Permissions**:
   - ✅ **Enable Spot & Margin Trading**: ON
   - ✅ **Enable Reading**: ON

3. **Prohibited Permissions** (⚠️ NEVER ENABLE):
   - ❌ **Enable Withdrawals**: OFF (critical security control)
   - ❌ **Enable Futures**: OFF (not needed for spot trading)
   - ❌ **Enable Internal Transfer**: OFF (prevents fund movement)

4. **IP Whitelist** (recommended):
   - Add production server IP
   - Test from whitelisted IP before going live

**API Key Rotation Schedule**:
- Production: Every 30 days
- Next due: Tracked in `docs/key-rotation-log.txt`

---

#### Secrets Manager Integration (12h)

**Option 1: AWS Secrets Manager** (recommended for AWS infrastructure):

```python
# src/config/secrets.py
import boto3
from botocore.exceptions import ClientError

class SecretsManager:
    """AWS Secrets Manager client."""

    def __init__(self, region_name="eu-west-1"):
        self.client = boto3.client("secretsmanager", region_name=region_name)

    def get_secret(self, secret_id: str) -> dict:
        """
        Retrieve secret from AWS Secrets Manager.

        Args:
            secret_id: Secret identifier (e.g., 'thunes/binance_api_key')

        Returns:
            Secret value as dict

        Raises:
            ClientError: If secret not found or access denied
        """
        try:
            response = self.client.get_secret_value(SecretId=secret_id)
            return json.loads(response["SecretString"])
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                raise ValueError(f"Secret {secret_id} not found")
            raise

# Usage in src/config.py
secrets_manager = SecretsManager()
api_key = secrets_manager.get_secret("thunes/binance_api_key")["api_key"]
api_secret = secrets_manager.get_secret("thunes/binance_api_key")["api_secret"]
```

**Setup**:

```bash
# 1. Install AWS CLI
pip install awscli boto3

# 2. Configure AWS credentials
aws configure
# AWS Access Key ID: [Your Access Key]
# AWS Secret Access Key: [Your Secret]
# Default region name: eu-west-1

# 3. Create secret
aws secretsmanager create-secret \
  --name thunes/binance_api_key \
  --description "Binance production API credentials" \
  --secret-string '{
    "api_key": "YOUR_LIVE_API_KEY",
    "api_secret": "YOUR_LIVE_API_SECRET"
  }'

# 4. Verify secret
aws secretsmanager get-secret-value --secret-id thunes/binance_api_key

# 5. Test retrieval in Python
python -c "
from src.config.secrets import SecretsManager
sm = SecretsManager()
secret = sm.get_secret('thunes/binance_api_key')
print(f'API Key: {secret[\"api_key\"][:10]}...')
"
```

**Option 2: HashiCorp Vault** (recommended for on-premise/hybrid):

```bash
# 1. Install Vault
wget https://releases.hashicorp.com/vault/1.15.0/vault_1.15.0_linux_amd64.zip
unzip vault_1.15.0_linux_amd64.zip
sudo mv vault /usr/local/bin/

# 2. Start Vault server (dev mode for testing)
vault server -dev &

# 3. Set environment variable
export VAULT_ADDR='http://127.0.0.1:8200'

# 4. Store secret
vault kv put secret/thunes/binance_api_key \
  api_key="YOUR_LIVE_API_KEY" \
  api_secret="YOUR_LIVE_API_SECRET"

# 5. Retrieve secret
vault kv get -field=api_key secret/thunes/binance_api_key
```

```python
# src/config/secrets.py (Vault integration)
import hvac

class VaultSecretsManager:
    """HashiCorp Vault client."""

    def __init__(self, url="http://127.0.0.1:8200", token=None):
        self.client = hvac.Client(url=url, token=token)

    def get_secret(self, path: str) -> dict:
        """
        Retrieve secret from Vault.

        Args:
            path: Secret path (e.g., 'secret/thunes/binance_api_key')

        Returns:
            Secret data as dict
        """
        response = self.client.secrets.kv.v2.read_secret_version(path=path)
        return response["data"]["data"]
```

**Option 3: Encrypted .env** (fallback for local dev):

```bash
# 1. Install cryptography
pip install cryptography

# 2. Generate encryption key
python -c "
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(f'Encryption key: {key.decode()}')
# Save to ~/.thunes_key (chmod 600)
"

# 3. Encrypt .env file
python scripts/encrypt_env.py .env .env.encrypted
```

**Success Criteria**:
- ✅ API keys stored in secrets manager (not in `.env`)
- ✅ Test retrieval from production server
- ✅ Verify permissions: `chmod 600 ~/.aws/credentials` (if using AWS)

---

### Day 3: Systemd Service + Log Rotation (8h)

#### Systemd Service Configuration (4h)

**File**: `/etc/systemd/system/thunes-scheduler.service`

```ini
[Unit]
Description=THUNES Trading Scheduler (Production)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=thunes
Group=thunes
WorkingDirectory=/home/thunes/THUNES
Environment="THUNES_ENVIRONMENT=live"
Environment="PATH=/home/thunes/THUNES/.venv/bin:/usr/local/bin:/usr/bin"

ExecStart=/home/thunes/THUNES/.venv/bin/python -m src.orchestration.run_scheduler

# Restart policy
Restart=on-failure
RestartSec=30
TimeoutStartSec=90
TimeoutStopSec=30

# Resource limits
LimitNOFILE=10000
MemoryMax=1G
CPUQuota=80%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=thunes-scheduler

# Security (optional hardening)
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

**Installation**:

```bash
# 1. Create thunes user (if not exists)
sudo useradd -r -s /bin/bash -m -d /home/thunes thunes

# 2. Copy service file
sudo cp thunes-scheduler.service /etc/systemd/system/

# 3. Reload systemd
sudo systemctl daemon-reload

# 4. Enable auto-start on boot
sudo systemctl enable thunes-scheduler

# 5. Start service
sudo systemctl start thunes-scheduler

# 6. Check status
sudo systemctl status thunes-scheduler

# 7. View logs
sudo journalctl -u thunes-scheduler -f
```

**Monitoring**:

```bash
# Check if service is running
systemctl is-active thunes-scheduler
# Expected: active

# Check uptime
systemctl show thunes-scheduler --property=ActiveEnterTimestamp

# Restart service
sudo systemctl restart thunes-scheduler

# Stop service
sudo systemctl stop thunes-scheduler
```

---

#### Log Rotation Configuration (4h)

**File**: `/etc/logrotate.d/thunes`

```
/home/thunes/THUNES/logs/*.log {
    daily
    rotate 90
    compress
    delaycompress
    missingok
    notifempty
    create 0644 thunes thunes
    sharedscripts
    postrotate
        # Signal scheduler to reopen log files
        systemctl reload thunes-scheduler || true
    endscript
}

/home/thunes/THUNES/logs/audit_trail.jsonl {
    weekly
    rotate 52
    compress
    delaycompress
    missingok
    notifempty
    create 0644 thunes thunes
    # No postrotate needed (append-only file)
}
```

**Installation**:

```bash
# 1. Copy logrotate config
sudo cp thunes.logrotate /etc/logrotate.d/thunes

# 2. Test config
sudo logrotate -d /etc/logrotate.d/thunes
# Expected: No errors

# 3. Force rotation (test)
sudo logrotate -f /etc/logrotate.d/thunes

# 4. Verify rotated files
ls -lh /home/thunes/THUNES/logs/
# Expected: paper_trader.log.1.gz, audit_trail.jsonl.1.gz
```

**Success Criteria**:
- ✅ Systemd service starts on boot
- ✅ Logs rotate daily (paper_trader.log)
- ✅ Audit trail rotates weekly (audit_trail.jsonl)
- ✅ Compressed logs <10 MB/week

---

### Day 4-5: Position Reconciliation (16h)

**Goal**: Detect position desyncs (local SQLite vs exchange balances) within 1 hour

#### Implementation (`src/monitoring/reconciliation.py`, 12h):

```python
"""Hourly position reconciliation."""

import time
from decimal import Decimal
from typing import Optional
from binance.client import Client
from src.config import settings
from src.models.position import PositionTracker
from src.alerts.telegram import TelegramBot
from src.utils.logger import setup_logger

log = setup_logger(__name__)


class PositionReconciliation:
    """Reconcile local positions with exchange balances."""

    def __init__(
        self,
        client: Client,
        tracker: PositionTracker,
        telegram: Optional[TelegramBot] = None,
        tolerance: Decimal = Decimal("0.00001"),
    ):
        """
        Initialize reconciliation service.

        Args:
            client: Binance client
            tracker: Position tracker
            telegram: Telegram bot for alerts
            tolerance: Tolerance for balance mismatches (default: 0.00001)
        """
        self.client = client
        self.tracker = tracker
        self.telegram = telegram
        self.tolerance = tolerance

    def reconcile(self) -> dict:
        """
        Perform reconciliation check.

        Returns:
            {
                "timestamp": datetime,
                "mismatches": [
                    {"asset": "BTC", "exchange": 0.001, "local": 0.0005, "delta": 0.0005},
                    ...
                ],
                "total_mismatches": int,
            }
        """
        log.info("Starting position reconciliation")

        # 1. Get exchange balances
        account = self.client.get_account()
        exchange_holdings = {
            b["asset"]: Decimal(b["free"]) + Decimal(b["locked"])
            for b in account["balances"]
            if Decimal(b["free"]) > 0 or Decimal(b["locked"]) > 0
        }

        # 2. Get local positions
        local_positions = self.tracker.get_all_open_positions()
        local_holdings = {
            pos.symbol[:-4]: Decimal(str(pos.quantity)) for pos in local_positions
        }

        # 3. Compare
        mismatches = []
        for asset, exchange_qty in exchange_holdings.items():
            # Skip quote currencies and stable coins
            if asset in ["USDT", "BUSD", "USDC", "BNB"]:
                continue

            local_qty = local_holdings.get(asset, Decimal("0"))
            delta = abs(exchange_qty - local_qty)

            if delta > self.tolerance:
                mismatches.append({
                    "asset": asset,
                    "exchange": float(exchange_qty),
                    "local": float(local_qty),
                    "delta": float(delta),
                })
                log.warning(
                    f"Position mismatch: {asset} - Exchange: {exchange_qty}, Local: {local_qty}, Delta: {delta}"
                )

        # Also check for local positions not on exchange (orphaned)
        for asset, local_qty in local_holdings.items():
            if asset not in exchange_holdings and local_qty > self.tolerance:
                mismatches.append({
                    "asset": asset,
                    "exchange": 0.0,
                    "local": float(local_qty),
                    "delta": float(local_qty),
                })
                log.warning(
                    f"Orphaned local position: {asset} - Local: {local_qty}, Exchange: 0"
                )

        result = {
            "timestamp": time.time(),
            "mismatches": mismatches,
            "total_mismatches": len(mismatches),
        }

        # 4. Alert if mismatches found
        if mismatches:
            self._send_alert(mismatches)

        log.info(
            f"Reconciliation complete: {len(mismatches)} mismatches found"
        )

        return result

    def _send_alert(self, mismatches: list) -> None:
        """Send Telegram alert for mismatches."""
        if not self.telegram:
            return

        message = f"""⚠️ **THUNES Position Reconciliation Alert**

🔍 **Mismatches Detected**: {len(mismatches)}

"""
        for m in mismatches:
            message += f"""
**{m['asset']}**:
- Exchange: {m['exchange']:.8f}
- Local: {m['local']:.8f}
- Delta: {m['delta']:.8f}
"""

        message += """
🔧 **Action Required**:
1. Review audit trail for missing POSITION_CLOSED events
2. Check for manual trades not logged
3. Run manual reconciliation script if needed

Timestamp: {datetime.utcnow().isoformat()}
"""

        self.telegram.send_message_sync(message)

    def run_continuous(self, interval_hours: int = 1) -> None:
        """
        Run reconciliation continuously.

        Args:
            interval_hours: How often to reconcile (default: 1 hour)
        """
        while True:
            try:
                self.reconcile()
            except Exception as e:
                log.error(f"Reconciliation failed: {e}", exc_info=True)

            time.sleep(interval_hours * 3600)
```

**Integration** (`src/orchestration/scheduler.py`):

```python
def schedule_reconciliation(self, interval_hours: int = 1) -> None:
    """Schedule hourly position reconciliation."""
    from src.monitoring.reconciliation import PositionReconciliation

    reconciler = PositionReconciliation(
        client=self.paper_trader.client,
        tracker=self.paper_trader.position_tracker,
        telegram=self.telegram_bot,
    )

    self.scheduler.add_job(
        func=reconciler.reconcile,
        trigger="interval",
        hours=interval_hours,
        id="position_reconciliation",
        replace_existing=True,
        name="Position Reconciliation",
    )
    logger.info(f"Scheduled position reconciliation every {interval_hours} hour(s)")
```

**Testing** (4h):

```python
# tests/test_reconciliation.py
import pytest
from src.monitoring.reconciliation import PositionReconciliation
from src.models.position import PositionTracker
from decimal import Decimal
from unittest.mock import MagicMock

class TestReconciliation:
    """Test position reconciliation."""

    def test_no_mismatches(self):
        """Test reconciliation with matching balances."""
        client_mock = MagicMock()
        client_mock.get_account.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.001", "locked": "0.0"},
                {"asset": "USDT", "free": "1000.0", "locked": "0.0"},
            ]
        }

        tracker = PositionTracker()
        tracker.open_position(
            symbol="BTCUSDT",
            entry_price=Decimal("43000"),
            quantity=Decimal("0.001"),
            side="BUY",
            order_id="1",
            strategy_id="test",
        )

        reconciler = PositionReconciliation(client_mock, tracker)
        result = reconciler.reconcile()

        assert result["total_mismatches"] == 0

    def test_exchange_has_more(self):
        """Test mismatch: exchange has more than local (missed SELL)."""
        client_mock = MagicMock()
        client_mock.get_account.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.002", "locked": "0.0"},  # More than local
                {"asset": "USDT", "free": "1000.0", "locked": "0.0"},
            ]
        }

        tracker = PositionTracker()
        tracker.open_position(
            symbol="BTCUSDT",
            entry_price=Decimal("43000"),
            quantity=Decimal("0.001"),  # Less than exchange
            side="BUY",
            order_id="1",
            strategy_id="test",
        )

        reconciler = PositionReconciliation(client_mock, tracker)
        result = reconciler.reconcile()

        assert result["total_mismatches"] == 1
        assert result["mismatches"][0]["asset"] == "BTC"
        assert result["mismatches"][0]["delta"] == 0.001

    def test_orphaned_local_position(self):
        """Test mismatch: local has position not on exchange."""
        client_mock = MagicMock()
        client_mock.get_account.return_value = {
            "balances": [
                {"asset": "USDT", "free": "1000.0", "locked": "0.0"},
            ]
        }

        tracker = PositionTracker()
        tracker.open_position(
            symbol="BTCUSDT",
            entry_price=Decimal("43000"),
            quantity=Decimal("0.001"),  # Orphaned
            side="BUY",
            order_id="1",
            strategy_id="test",
        )

        reconciler = PositionReconciliation(client_mock, tracker)
        result = reconciler.reconcile()

        assert result["total_mismatches"] == 1
        assert result["mismatches"][0]["asset"] == "BTC"
        assert result["mismatches"][0]["exchange"] == 0.0
        assert result["mismatches"][0]["local"] == 0.001

    # Additional 5+ tests for edge cases
```

**Success Criteria**:
- ✅ Reconciliation runs hourly (via scheduler)
- ✅ Telegram alert fires within 5 minutes of mismatch
- ✅ Manual desync test: Create position manually on exchange, verify alert

---

### Day 5: Chaos Testing (8h)

**Goal**: Validate system resilience under failure scenarios

#### Test Scenarios:

**1. Scheduler Crash Mid-Trade** (2h):

```bash
# Trigger trade, kill scheduler immediately
python -c "
from src.live.paper_trader import PaperTrader
trader = PaperTrader(testnet=False)
trader.run_strategy('BTCUSDT', '1h', 10.0)
" &
PID=$!
sleep 0.5  # Let trade start
kill -9 $PID  # Kill scheduler

# Verify recovery:
# 1. Restart scheduler
systemctl restart thunes-scheduler

# 2. Check position reconciliation (should detect desync if order placed but not logged)
# 3. Review audit trail for POSITION_OPENED event
```

**2. Network Partition (WebSocket Disconnect)** (2h):

```bash
# Simulate network partition (firewall rule)
sudo iptables -A OUTPUT -d binance.com -j DROP

# Wait 90 seconds (watchdog timeout)
sleep 90

# Restore network
sudo iptables -D OUTPUT -d binance.com -j DROP

# Verify WebSocket reconnects
tail -f logs/paper_trader.log | grep "WebSocket reconnected"
```

**3. Kill-Switch Trigger** (2h):

```python
# Trigger kill-switch via manual PnL update
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

rm = RiskManager(position_tracker=PositionTracker())
rm._daily_pnl = -25.0  # Exceeds MAX_DAILY_LOSS=-20
rm._check_kill_switch()

# Verify:
# 1. Kill-switch active
assert rm.kill_switch_active

# 2. BUY rejected
is_valid, reason = rm.validate_trade("BTCUSDT", 10.0, "BUY", "test")
assert not is_valid
assert reason == "KILL_SWITCH"

# 3. SELL allowed
is_valid, reason = rm.validate_trade("BTCUSDT", 10.0, "SELL", "test")
assert is_valid  # SELL should be allowed to exit positions

# 4. Telegram alert sent
# Check Telegram for kill-switch activation message

# 5. Deactivate
rm.deactivate_kill_switch()
assert not rm.kill_switch_active
```

**4. Memory Stress Test (24h)** (2h setup):

```bash
# Run scheduler for 24 hours, monitor RSS
systemctl start thunes-scheduler

# Monitor memory usage every 10 minutes
while true; do
  RSS=$(ps aux | grep run_scheduler | grep -v grep | awk '{print $6/1024 " MB"}')
  echo "$(date): RSS=$RSS" >> logs/memory_stress.log
  sleep 600  # 10 minutes
done

# After 24 hours, check for memory leak
tail -100 logs/memory_stress.log
# Expected: RSS stable (<200 MB), no growth trend
```

**Success Criteria**:
- ✅ Scheduler recovers from crash (auto-restart via systemd)
- ✅ WebSocket reconnects after network partition (<120s)
- ✅ Kill-switch blocks BUY, allows SELL
- ✅ Memory stable over 24h (RSS <200 MB)

---

## Week 2-4: Live Trading (120h monitoring)

### Week 2: Initial Live Trading (€10 capital)

**Daily Operations** (30 min/day):

```bash
# 1. Check Telegram for overnight alerts
# Expected: 0-2 alerts/night

# 2. Review Grafana dashboards (http://localhost:3000)
# Panels to check:
# - Daily PnL (should be ±2 EUR max)
# - Open positions (0-2)
# - Kill-switch (0=OK)
# - Circuit breaker (0=CLOSED)
# - WebSocket (1=connected)
# - Order latency (p95 <100ms)

# 3. Position reconciliation check
tail -20 logs/reconciliation.log
# Expected: "total_mismatches: 0"

# 4. Spot-check audit trail
tail -50 logs/audit_trail.jsonl | jq '.event' | sort | uniq -c
# Expected distribution:
#   30 TRADE_APPROVED
#   10 TRADE_REJECTED
#    5 POSITION_OPENED
#    5 POSITION_CLOSED

# 5. Check disk space
df -h /home/thunes/THUNES/logs
# Expected: <50% usage
```

**Weekly Analysis** (2h, Sunday):

```python
# Run performance analysis
from src.monitoring.performance_tracker import PerformanceTracker

tracker = PerformanceTracker()

print("=== Week 2 Performance ===")
print(f"7-Day Sharpe: {tracker.calculate_sharpe_ratio(window_days=7):.2f}")
print(f"Total Return: {tracker.calculate_total_return(window_days=7):.2f}%")
print(f"Max Drawdown: {tracker.calculate_max_drawdown():.2f}%")
print(f"Win Rate: {tracker.calculate_win_rate(window_days=7):.1f}%")

# Compare vs Phase 13 paper trading
print("\n=== Paper vs Live Comparison ===")
print(f"Slippage Delta: {tracker.calculate_slippage_delta():.2f}%")
# Expected: <0.5% difference (slippage + fees)
```

**Success Criteria (Week 2)**:
- ✅ Zero position desyncs (100% reconciliation success)
- ✅ Sharpe >0.8 (live trading)
- ✅ Slippage delta <0.5% (vs paper trading)
- ✅ Circuit breaker trips <3/week
- ✅ Zero scheduler crashes

**Decision Gate**: If all criteria met → increase capital to €20 for Week 3

---

### Week 3-4: Scaled Live Trading (€20 capital)

**Capital Increase Procedure**:

```bash
# 1. Deposit additional €10 to Binance
# Total capital: €20 (€10 from Week 2 + €10 new)

# 2. Update config
# Edit .env or secrets manager
DEFAULT_QUOTE_AMOUNT=20.0  # Increase from 10.0

# 3. Restart scheduler
systemctl restart thunes-scheduler

# 4. Verify updated config
tail -10 logs/paper_trader.log | grep "quote_amount"
# Expected: quote_amount=20.0
```

**Weekly Profit Withdrawal** (Week 3+):

```bash
# If Week 2 profitable (PnL >€5), withdraw profit
# Manual withdrawal via Binance web UI (API withdrawal disabled for security)

# 1. Calculate profit
python -c "
from src.monitoring.performance_tracker import PerformanceTracker
tracker = PerformanceTracker()
profit = tracker.calculate_total_return(window_days=7) / 100 * 10  # 10 EUR capital
print(f'Week 2 Profit: €{profit:.2f}')
"

# 2. If profit >€5, withdraw to external wallet
# Example: €6 profit → withdraw €5, keep €1 as buffer

# 3. Document in logs
echo "$(date): Withdrew €5 profit (Week 2)" >> docs/withdrawal-log.txt
```

**Success Criteria (Week 3-4)**:
- ✅ 30 days uptime >99.9% (max 14.4 min downtime)
- ✅ Sharpe >1.0 (live trading)
- ✅ Zero position desyncs (continued)
- ✅ Profit withdrawal successful (if profitable)
- ✅ Capital preserved (no kill-switch activations)

---

## GO/NO-GO Decision for Phase 15

**Meeting**: End of Week 4, Friday 17:00 UTC

**Criteria**:

| Criterion | Threshold | Measured |
|-----------|-----------|----------|
| Uptime | >99.9% | systemctl show thunes-scheduler |
| Sharpe (30d) | >1.0 | PerformanceTracker |
| Position Desyncs | 0 | Reconciliation logs |
| Scheduler Crashes | 0 | systemctl status |
| Kill-Switch Activations | 0 | Audit trail grep |
| Profit Withdrawal | ≥1 successful | withdrawal-log.txt |

**Decision**:
- **GO**: Proceed to Phase 15 (RL Integration)
- **NO-GO**: Extend Phase 14 monitoring for 2 more weeks

---

## Summary Checklist

**Week 1**:
- [ ] Generate Binance live API keys (withdrawal-disabled)
- [ ] Configure secrets manager (AWS Secrets Manager or Vault)
- [ ] Deploy systemd service (thunes-scheduler.service)
- [ ] Configure log rotation (/etc/logrotate.d/thunes)
- [ ] Implement position reconciliation (hourly)
- [ ] Run chaos tests (scheduler crash, network partition, kill-switch, memory stress)

**Week 2**:
- [ ] Start live trading (€10 capital)
- [ ] Monitor daily (30 min/day)
- [ ] Weekly analysis (2h, Sunday)
- [ ] Verify success criteria (desyncs, Sharpe, slippage)

**Week 3-4**:
- [ ] Increase capital to €20 (if Week 2 successful)
- [ ] Continue monitoring
- [ ] Withdraw profit (if >€5 profit)
- [ ] Prepare Phase 15 infrastructure

**Week 4 GO/NO-GO**:
- [ ] Review 30-day metrics
- [ ] Document decision in `docs/production/PHASE_14_GO_NO_GO.md`
- [ ] If GO → proceed to Phase 15

---

**Document Version**: 1.0
**Last Updated**: 2025-10-05
**Author**: Claude Code (Automated Production Checklist)
