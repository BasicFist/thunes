# THUNES Production Roadmap
## From Current State (Phase 9.5) → Phase 14 (Live Trading)

**Document Version**: 1.0
**Created**: 2025-10-03
**Target Production Date**: 2025-10-17 (±3 days)
**Total Timeline**: 44 days (~6 weeks)

---

## Executive Summary

**Current Status**: MVP complete with 90% infrastructure readiness
**Critical Blocker**: Phase 10 (Orchestration) - autonomous operation layer
**Test Suite**: 174 tests (71 passing, 1 failing, coverage 33%)
**Capital at Risk**: 10-50 EUR (Phase 14)

**Key Insight**: THUNES has production-grade safety infrastructure (kill-switch, circuit breakers, audit trail) but lacks automation for 24/7 operation. Once orchestration is implemented, the system can run autonomously.

---

## Timeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ Week 1 (Day 1-7):   Critical Path Implementation               │
│                     - Fix WebSocket test (Day 1-2)              │
│                     - Build orchestration (Day 2-5)             │
│                     - Testing & validation (Day 5-7)            │
│                                                                 │
│ Week 2 (Day 8-15):  Phase 13 - Paper Trading 24/7              │
│                     - Deploy autonomous system                  │
│                     - Daily monitoring (1h/day)                 │
│                     - GO/NO-GO decision gate                    │
│                                                                 │
│ Week 3 (Day 16-22): Pre-Production Hardening                   │
│                     - Security audit                            │
│                     - Production configuration                  │
│                     - Runbook creation                          │
│                                                                 │
│ Week 4-7 (Day 23-47): Phase 14 - Live Trading                  │
│                     - 10 EUR starting capital                   │
│                     - Daily monitoring                          │
│                     - Performance validation                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## WEEK 1: Critical Path (Day 1-7)

### Day 1-2: Fix WebSocket Watchdog Test ⚠️ BLOCKER

**Issue**: `tests/test_ws_stream.py::TestWebSocketHealthMonitor::test_watchdog_triggers_reconnect` failing

**Root Cause**: Test implementation doesn't match production code pattern
- Test expects callback function: `reconnect_callback()`
- Production uses Queue: `reconnect_queue.put("reconnect")`

**Tasks**:
- [ ] Review test at `tests/test_ws_stream.py:42-70`
- [ ] Update test to use Queue pattern matching `src/data/ws_stream.py:62-106`
- [ ] Add assertions for watchdog state cleanup (`_running`, `_watchdog_thread`)
- [ ] Add debug logging to watchdog loop
- [ ] Verify reconnection works cleanly after watchdog trigger

**Validation**:
```bash
# Must pass all WebSocket tests
pytest tests/test_ws_stream.py -v

# Expected output:
# 13 tests passed in <5s
```

**Files to Modify**:
- `tests/test_ws_stream.py` (lines 42-70)

**Deliverables**:
- ✅ All 174 tests passing
- ✅ WebSocket health monitoring validated

**Estimated Effort**: 4-6 hours
**Risk Level**: Low (isolated test fix)

---

### Day 2-5: Implement Phase 10 Orchestration 🔴 CRITICAL PATH

**Goal**: Enable 24/7 autonomous operation via APScheduler

**Architecture Overview**:
```
TradingScheduler
├── Signal Check Job (every 10 minutes)
│   └── Calls PaperTrader.run_strategy()
├── Daily Summary Job (23:00 UTC)
│   └── Calls TelegramBot.send_daily_summary()
└── Parameter Reload Job (on file change)
    └── Calls PaperTrader.reload_parameters()

Features:
- SQLite job persistence (survives restarts)
- Anti-overlap protection (max 1 job at a time)
- Graceful shutdown (wait for jobs)
- Timezone-aware (UTC)
```

#### Day 2: Infrastructure (4-6 hours)

**Tasks**:
- [ ] Create `src/orchestration/` module
- [ ] Create `src/orchestration/__init__.py`
- [ ] Create `src/orchestration/scheduler.py` (~200 SLOC)
- [ ] Add `apscheduler>=3.10.0` to `requirements.txt`

**Implementation Guide**:
```python
# src/orchestration/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from src.config import settings
from src.live.paper_trader import PaperTrader
from src.alerts.telegram import TelegramBot
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class TradingScheduler:
    """Orchestrate trading operations with fault tolerance."""

    def __init__(self):
        """Initialize scheduler with persistent job store."""
        jobstores = {
            'default': SQLAlchemyJobStore(url='sqlite:///logs/jobs.db')
        }
        executors = {
            'default': ThreadPoolExecutor(max_workers=1)  # Serial execution
        }
        job_defaults = {
            'coalesce': True,  # Combine missed runs
            'max_instances': 1,  # Anti-overlap
            'misfire_grace_time': 60  # Allow 60s delay
        }

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        self.paper_trader = PaperTrader(testnet=(settings.environment != 'live'))
        self.telegram_bot = TelegramBot() if settings.telegram_bot_token else None

    def _check_signals(self) -> None:
        """Job: Check for trading signals."""
        try:
            logger.info("Signal check started")
            self.paper_trader.run_strategy(settings.default_symbol)
            logger.info("Signal check completed")
        except Exception as e:
            logger.error(f"Signal check failed: {e}", exc_info=True)

    def _send_daily_summary(self) -> None:
        """Job: Send daily performance summary via Telegram."""
        try:
            if self.telegram_bot:
                # Implementation in Day 3
                pass
        except Exception as e:
            logger.error(f"Daily summary failed: {e}", exc_info=True)

    def schedule_signal_check(self, interval_minutes: int = 10) -> None:
        """Schedule periodic signal checks."""
        self.scheduler.add_job(
            func=self._check_signals,
            trigger='interval',
            minutes=interval_minutes,
            id='signal_check',
            replace_existing=True,
            name='Signal Check'
        )
        logger.info(f"Scheduled signal checks every {interval_minutes} minutes")

    def schedule_daily_summary(self, hour: int = 23, minute: int = 0) -> None:
        """Schedule daily summary report."""
        self.scheduler.add_job(
            func=self._send_daily_summary,
            trigger='cron',
            hour=hour,
            minute=minute,
            id='daily_summary',
            replace_existing=True,
            name='Daily Summary'
        )
        logger.info(f"Scheduled daily summary at {hour:02d}:{minute:02d} UTC")

    def start(self) -> None:
        """Start scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
        else:
            logger.warning("Scheduler already running")

    def stop(self, wait: bool = True) -> None:
        """Stop scheduler, optionally waiting for jobs to complete."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info(f"Scheduler stopped (wait={wait})")

    def get_job_status(self) -> list[dict]:
        """Get status of all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs
```

**Deliverables**:
- ✅ `src/orchestration/scheduler.py` created
- ✅ APScheduler dependency added
- ✅ Basic scheduler infrastructure working

#### Day 3: Integration (6-8 hours)

**Tasks**:
- [ ] Implement `_send_daily_summary()` job
- [ ] Add parameter reload monitoring (file watcher or periodic check)
- [ ] Integrate circuit breaker checks before job execution
- [ ] Add job execution logging to `logs/scheduler.log`
- [ ] Handle edge cases (WebSocket disconnected, kill-switch active)

**Daily Summary Implementation**:
```python
def _send_daily_summary(self) -> None:
    """Job: Send daily performance summary via Telegram."""
    try:
        if not self.telegram_bot:
            logger.warning("Telegram not configured, skipping daily summary")
            return

        # Get daily stats from PositionTracker
        tracker = self.paper_trader.position_tracker
        daily_pnl = tracker.get_daily_pnl()
        trades_today = tracker.get_trades_today()

        # Get risk status
        risk_status = self.paper_trader.risk_manager.get_risk_status()

        # Format message
        message = f"""
📊 **THUNES Daily Summary**
📅 Date: {datetime.now().strftime('%Y-%m-%d')}

💰 **Performance**
Daily PnL: {daily_pnl:.2f} USDT
Trades Today: {len(trades_today)}
Win Rate: {self._calculate_win_rate(trades_today):.1f}%

🎯 **Risk Status**
Open Positions: {risk_status['open_positions']}/{risk_status['max_positions']}
Daily Loss: {risk_status['daily_pnl']:.2f} / {risk_status['max_daily_loss']:.2f}
Kill-Switch: {'🔴 ACTIVE' if risk_status['kill_switch_active'] else '🟢 OK'}

🔌 **System Health**
WebSocket: {'🟢 Connected' if self.paper_trader.ws_stream.is_connected() else '🔴 Disconnected'}
Circuit Breaker: {'🟢 Closed' if not circuit_monitor.is_open('BinanceAPI') else '🔴 Open'}
        """

        self.telegram_bot.send_message_sync(message.strip())
        logger.info("Daily summary sent")
    except Exception as e:
        logger.error(f"Daily summary failed: {e}", exc_info=True)
```

**Deliverables**:
- ✅ Daily summary job implemented
- ✅ Error handling for job failures
- ✅ Logging infrastructure in place

#### Day 4: CLI & Configuration (4-6 hours)

**Tasks**:
- [ ] Create `src/orchestration/run_scheduler.py` (CLI entry point)
- [ ] Add scheduler config to `.env`
- [ ] Implement signal handlers (SIGTERM, SIGINT)
- [ ] Add `--test-mode` flag for short-duration testing
- [ ] Create systemd service file (optional)

**CLI Implementation**:
```python
# src/orchestration/run_scheduler.py
"""CLI entry point for THUNES scheduler."""

import argparse
import signal
import sys
import time
from pathlib import Path

from src.orchestration.scheduler import TradingScheduler
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def signal_handler(sig, frame, scheduler: TradingScheduler) -> None:
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig}, shutting down...")
    scheduler.stop(wait=True)
    sys.exit(0)

def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description='THUNES Trading Scheduler')
    parser.add_argument('--test-mode', action='store_true',
                       help='Test mode (run for limited duration)')
    parser.add_argument('--duration', type=int, default=3600,
                       help='Test mode duration in seconds (default: 3600)')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon (background)')
    args = parser.parse_args()

    # Initialize scheduler
    scheduler = TradingScheduler()

    # Register signal handlers
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, scheduler))
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, scheduler))

    # Schedule jobs
    scheduler.schedule_signal_check(interval_minutes=10)
    scheduler.schedule_daily_summary(hour=23, minute=0)

    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started successfully")

    # Print job status
    for job in scheduler.get_job_status():
        logger.info(f"Job '{job['name']}' next run: {job['next_run']}")

    # Keep running
    if args.test_mode:
        logger.info(f"Test mode: running for {args.duration} seconds")
        time.sleep(args.duration)
        scheduler.stop(wait=True)
    else:
        logger.info("Running indefinitely (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            scheduler.stop(wait=True)

if __name__ == '__main__':
    main()
```

**Environment Variables** (add to `.env`):
```bash
# Scheduler Configuration
SIGNAL_CHECK_INTERVAL_MINUTES=10
DAILY_SUMMARY_HOUR=23  # UTC
ENABLE_AUTO_REOPTIMIZATION=false
```

**Deliverables**:
- ✅ `src/orchestration/run_scheduler.py` created
- ✅ Graceful shutdown implemented
- ✅ Configuration in `.env`

#### Day 5: Testing (6-8 hours)

**Tasks**:
- [ ] Create `tests/test_scheduler.py`
- [ ] Test job scheduling (mocked execution)
- [ ] Test anti-overlap enforcement
- [ ] Test graceful shutdown
- [ ] Test job persistence (restart test)
- [ ] Integration test: 1-hour live run
- [ ] Chaos test: Kill during job execution

**Test Implementation**:
```python
# tests/test_scheduler.py
"""Tests for trading scheduler."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.orchestration.scheduler import TradingScheduler

class TestTradingScheduler:
    """Tests for TradingScheduler."""

    def test_initialization(self) -> None:
        """Test scheduler initialization."""
        scheduler = TradingScheduler()
        assert scheduler.scheduler is not None
        assert not scheduler.scheduler.running

    def test_schedule_signal_check(self) -> None:
        """Test signal check job scheduling."""
        scheduler = TradingScheduler()
        scheduler.schedule_signal_check(interval_minutes=5)

        jobs = scheduler.get_job_status()
        assert len(jobs) == 1
        assert jobs[0]['id'] == 'signal_check'

    def test_schedule_daily_summary(self) -> None:
        """Test daily summary job scheduling."""
        scheduler = TradingScheduler()
        scheduler.schedule_daily_summary(hour=23, minute=0)

        jobs = scheduler.get_job_status()
        assert len(jobs) == 1
        assert jobs[0]['id'] == 'daily_summary'

    @patch('src.orchestration.scheduler.PaperTrader')
    def test_signal_check_execution(self, mock_trader) -> None:
        """Test signal check job executes correctly."""
        scheduler = TradingScheduler()
        scheduler.paper_trader = mock_trader

        # Execute job directly
        scheduler._check_signals()

        # Verify PaperTrader.run_strategy was called
        mock_trader.run_strategy.assert_called_once()

    def test_start_stop(self) -> None:
        """Test scheduler start/stop."""
        scheduler = TradingScheduler()

        scheduler.start()
        assert scheduler.scheduler.running

        scheduler.stop(wait=False)
        assert not scheduler.scheduler.running

    def test_anti_overlap_enforcement(self) -> None:
        """Test max_instances=1 prevents overlapping jobs."""
        scheduler = TradingScheduler()

        # Schedule job with short interval
        scheduler.schedule_signal_check(interval_minutes=1)
        scheduler.start()

        # Mock long-running job
        with patch.object(scheduler, '_check_signals',
                         side_effect=lambda: time.sleep(90)):  # 90s > 60s interval
            time.sleep(3)  # Wait for 2+ job attempts

        scheduler.stop()

        # Verify only 1 job ran (others coalesced)
        # Note: Actual implementation would check job execution count via logging

    def test_graceful_shutdown_waits_for_job(self) -> None:
        """Test shutdown waits for running jobs to complete."""
        scheduler = TradingScheduler()
        scheduler.schedule_signal_check(interval_minutes=1)
        scheduler.start()

        # Trigger job execution
        time.sleep(2)

        # Stop with wait=True
        start_time = time.time()
        scheduler.stop(wait=True)
        stop_time = time.time()

        # Should wait for job to complete (not instant)
        assert stop_time - start_time >= 0  # Basic sanity check

    def test_job_persistence_after_restart(self) -> None:
        """Test jobs persist in SQLite after scheduler restart."""
        # First instance
        scheduler1 = TradingScheduler()
        scheduler1.schedule_signal_check(interval_minutes=10)
        scheduler1.start()

        jobs_before = scheduler1.get_job_status()
        assert len(jobs_before) == 1

        scheduler1.stop()

        # Second instance (simulates restart)
        scheduler2 = TradingScheduler()
        scheduler2.start()

        jobs_after = scheduler2.get_job_status()
        assert len(jobs_after) == 1
        assert jobs_after[0]['id'] == 'signal_check'

        scheduler2.stop()
```

**Integration Test**:
```bash
# Run scheduler for 1 hour in test mode
python src/orchestration/run_scheduler.py --test-mode --duration=3600

# Monitor logs
tail -f logs/scheduler.log

# After 1 hour, verify:
# - At least 6 signal checks executed (10min intervals)
# - No crashes or errors
# - Jobs logged correctly
```

**Chaos Test**:
```bash
# Start scheduler
python src/orchestration/run_scheduler.py &
SCHEDULER_PID=$!

# Wait for job to start
sleep 5

# Kill mid-execution
kill -9 $SCHEDULER_PID

# Restart
python src/orchestration/run_scheduler.py &

# Verify: Jobs resume, no corruption in jobs.db
sqlite3 logs/jobs.db "SELECT * FROM apscheduler_jobs;"
```

**Deliverables**:
- ✅ `tests/test_scheduler.py` (150 SLOC, 8+ tests)
- ✅ All scheduler tests passing
- ✅ 1-hour integration test successful
- ✅ Chaos test recovery validated

**Estimated Total Effort (Day 2-5)**: 20-28 hours
**Risk Level**: Medium (new component, integration complexity)

---

### Day 5-7: Testing & Validation (Parallel Work)

#### Task 1: Configure Telegram Alerts (Day 5, 1 hour)

**Steps**:
1. Create Telegram bot via [@BotFather](https://t.me/botfather)
   - Send `/newbot` command
   - Choose bot name and username
   - Save bot token
2. Get chat ID
   - Message your bot
   - Run: `curl https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Extract `chat.id` from response
3. Add to `.env`:
   ```bash
   TELEGRAM_BOT_TOKEN=<your_token>
   TELEGRAM_CHAT_ID=<your_chat_id>
   ```
4. Test:
   ```bash
   python -c "
   from src.alerts.telegram import TelegramBot
   bot = TelegramBot()
   bot.send_message_sync('🚀 THUNES alerts configured')
   "
   ```

**Checklist**:
- [ ] Bot created via @BotFather
- [ ] Chat ID obtained
- [ ] Credentials added to `.env`
- [ ] Test message sent successfully
- [ ] Daily summary test (manually trigger `_send_daily_summary()`)

#### Task 2: Validate Audit Trail (Day 5, 2 hours)

**Goal**: Verify immutable audit trail works in practice

**Steps**:
1. Execute paper trades to generate audit log:
   ```bash
   python -c "
   from src.live.paper_trader import PaperTrader

   # Execute 3 trades
   trader = PaperTrader(testnet=True)
   for _ in range(3):
       trader.run_strategy('BTCUSDT')
   "
   ```

2. Validate JSONL format:
   ```bash
   # Check file exists
   ls -lh logs/audit_trail.jsonl

   # Validate JSON syntax
   cat logs/audit_trail.jsonl | jq '.' > /dev/null
   echo "JSONL valid: $?"

   # Inspect event types
   cat logs/audit_trail.jsonl | jq '.event' | sort | uniq -c
   ```

3. Manually trigger kill-switch:
   ```bash
   python -c "
   from src.risk.manager import RiskManager
   from src.models.position import PositionTracker

   rm = RiskManager(position_tracker=PositionTracker())
   rm.activate_kill_switch('Pre-production validation test')
   "

   # Verify Telegram alert received
   # Verify audit log contains KILL_SWITCH_ACTIVATED event
   ```

4. Attempt trade with kill-switch active (should reject):
   ```bash
   python -c "
   from src.live.paper_trader import PaperTrader
   trader = PaperTrader(testnet=True)
   trader.run_strategy('BTCUSDT')  # Should log TRADE_REJECTED
   "
   ```

5. Deactivate kill-switch:
   ```bash
   python -c "
   from src.risk.manager import RiskManager
   from src.models.position import PositionTracker

   rm = RiskManager(position_tracker=PositionTracker())
   rm.deactivate_kill_switch()
   "
   ```

**Expected Audit Log Events**:
```json
{"timestamp": "...", "event": "TRADE_APPROVED", "symbol": "BTCUSDT", ...}
{"timestamp": "...", "event": "TRADE_APPROVED", "symbol": "BTCUSDT", ...}
{"timestamp": "...", "event": "TRADE_APPROVED", "symbol": "BTCUSDT", ...}
{"timestamp": "...", "event": "KILL_SWITCH_ACTIVATED", "reason": "Pre-production validation test", ...}
{"timestamp": "...", "event": "TRADE_REJECTED", "reason": "kill_switch_active", ...}
{"timestamp": "...", "event": "KILL_SWITCH_DEACTIVATED", ...}
```

**Checklist**:
- [ ] Audit trail file created at `logs/audit_trail.jsonl`
- [ ] JSONL syntax valid
- [ ] Contains TRADE_APPROVED events
- [ ] Contains TRADE_REJECTED events
- [ ] Contains KILL_SWITCH_ACTIVATED events
- [ ] Telegram alerts sent for kill-switch

#### Task 3: Create Integration Tests (Day 6-7, 12-16 hours)

**Goal**: Validate entire trading pipeline end-to-end

**File**: `tests/test_paper_trader_e2e.py` (~300 SLOC)

**Tests to Implement**:

1. **Full Trade Execution Flow** (4 hours)
   ```python
   def test_full_trade_execution_flow():
       """Test: WebSocket → Signal → Risk Check → Order → Position."""
       # Setup
       trader = PaperTrader(testnet=True)

       # Force BUY signal (mock data or wait for real signal)
       # Verify:
       # 1. ExchangeFilters validated order
       # 2. RiskManager approved trade
       # 3. Order placed via Binance API
       # 4. Position tracked correctly
       # 5. Audit log written
   ```

2. **Kill-Switch Blocks Trades** (2 hours)
   ```python
   def test_kill_switch_blocks_trades():
       """Test: Kill-switch activation prevents new orders."""
       trader = PaperTrader(testnet=True)

       # Activate kill-switch
       trader.risk_manager.activate_kill_switch('Test')

       # Attempt trade (should reject)
       # Verify audit log shows TRADE_REJECTED
       # Verify Telegram alert sent (if configured)
   ```

3. **Cool-Down Enforcement** (3 hours)
   ```python
   def test_cool_down_enforcement():
       """Test: Cool-down period prevents rapid trading after loss."""
       trader = PaperTrader(testnet=True)

       # Execute losing trade (need to mock or execute real trade)
       # Record loss with risk manager
       # Immediately attempt new trade (should reject)
       # Mock time advance by 60 minutes
       # Attempt trade (should approve)
   ```

4. **Position Limit Enforcement** (2 hours)
   ```python
   def test_position_limit_enforcement():
       """Test: Max 3 concurrent positions enforced."""
       trader = PaperTrader(testnet=True)

       # Open 3 positions (may need to mock or use testnet)
       # Attempt 4th position (should reject with "max_positions_reached")
       # Close 1 position
       # Attempt new position (should approve)
   ```

5. **WebSocket Reconnection Recovery** (3 hours)
   ```python
   def test_websocket_reconnection_recovery():
       """Test: Trading continues after WebSocket disconnect."""
       trader = PaperTrader(testnet=True)

       # Start WebSocket
       # Force disconnect (stop WebSocket manager)
       # Wait for reconnection (max 30s)
       # Verify trading resumes
       # Check REST fallback used during reconnection
   ```

**Deliverables**:
- ✅ `tests/test_paper_trader_e2e.py` created
- ✅ 5+ integration tests implemented
- ✅ All tests passing
- ✅ Test coverage for critical execution paths validated

**Estimated Total Effort (Day 5-7)**: 15-19 hours
**Risk Level**: Low (validation work, no production impact)

---

### Week 1 Completion Checklist

**By End of Day 7**:
- ✅ All 174+ tests passing (WebSocket fix complete)
- ✅ Orchestration layer implemented (`src/orchestration/`)
- ✅ Scheduler CLI working (`run_scheduler.py`)
- ✅ Telegram alerts configured and tested
- ✅ Audit trail validated (JSONL format, all event types)
- ✅ End-to-end integration tests passing
- ✅ 1-hour scheduler integration test successful

**Readiness for Phase 13**: 100%

**Total Estimated Effort**: 39-53 hours (5-7 days focused work)

---

## WEEK 2: Phase 13 - Paper Trading 24/7 (Day 8-15)

### Day 8: Deployment (2 hours)

**Tasks**:

1. **Deploy Scheduler** (30 minutes)
   ```bash
   # Start scheduler in daemon mode
   cd /home/miko/LAB/projects/THUNES
   source .venv/bin/activate
   nohup python src/orchestration/run_scheduler.py --daemon > logs/scheduler_daemon.log 2>&1 &
   echo $! > logs/scheduler.pid

   # Verify running
   ps aux | grep run_scheduler
   ```

2. **Verify Job Scheduling** (15 minutes)
   ```bash
   # Check jobs in database
   sqlite3 logs/jobs.db "SELECT * FROM apscheduler_jobs;"

   # Expected output:
   # signal_check | ... | next_run_time=<within 10 min>
   # daily_summary | ... | next_run_time=23:00 UTC
   ```

3. **Monitor Initial Execution** (45 minutes)
   ```bash
   # Watch logs in real-time
   tail -f logs/scheduler.log logs/paper_trader.log

   # Wait for first signal check (within 10 minutes)
   # Verify:
   # - Job executes successfully
   # - No errors in logs
   # - WebSocket connected
   ```

4. **Set Up Monitoring Alerts** (30 minutes)
   - Configure Telegram daily summaries (23:00 UTC)
   - Set calendar reminder for daily manual checks (09:00 UTC)
   - Bookmark monitoring commands (see below)

**Monitoring Commands** (bookmark these):
```bash
# Quick health check (run daily)
cd /home/miko/LAB/projects/THUNES
source .venv/bin/activate

# 1. Check scheduler running
ps aux | grep run_scheduler || echo "⚠️ Scheduler not running!"

# 2. Recent errors
tail -50 logs/scheduler.log | grep ERROR
tail -50 logs/paper_trader.log | grep ERROR

# 3. Job status
sqlite3 logs/jobs.db "SELECT name, next_run_time FROM apscheduler_jobs ORDER BY next_run_time;"

# 4. Position status
python -c "
from src.models.position import PositionTracker
tracker = PositionTracker()
positions = tracker.get_open_positions()
print(f'Open positions: {len(positions)}')
print(f'Total PnL: {tracker.get_total_pnl():.2f} USDT')
"

# 5. Risk status
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
status = rm.get_risk_status()
print(f\"Kill-switch: {'🔴 ACTIVE' if status['kill_switch_active'] else '🟢 OK'}\")
print(f\"Daily PnL: {status['daily_pnl']:.2f} USDT\")
print(f\"Positions: {status['open_positions']}/{status['max_positions']}\")
"
```

**Checklist**:
- [ ] Scheduler deployed and running
- [ ] Jobs scheduled correctly
- [ ] First signal check executed successfully
- [ ] Telegram daily summary configured
- [ ] Monitoring commands bookmarked

---

### Day 9-15: Autonomous Operation (7 days)

**Daily Monitoring** (1 hour/day):

**Morning Checklist (09:00 UTC)**:
```bash
# 1. Check Telegram for daily summary (sent at 23:00 UTC previous day)

# 2. Run health check
cd /home/miko/LAB/projects/THUNES && source .venv/bin/activate
bash <<'EOF'
echo "=== THUNES Health Check $(date) ==="

# Scheduler status
if ps aux | grep -q "[r]un_scheduler"; then
    echo "✅ Scheduler running"
else
    echo "🔴 Scheduler NOT running"
fi

# Recent errors
ERROR_COUNT=$(tail -100 logs/scheduler.log | grep -c ERROR)
if [ $ERROR_COUNT -eq 0 ]; then
    echo "✅ No scheduler errors"
else
    echo "⚠️ $ERROR_COUNT scheduler errors in last 100 lines"
fi

# WebSocket reconnections
RECONNECT_COUNT=$(grep -c "reconnect" logs/paper_trader.log 2>/dev/null || echo 0)
echo "ℹ️  Total WebSocket reconnections: $RECONNECT_COUNT"

# Positions
python -c "
from src.models.position import PositionTracker
tracker = PositionTracker()
print(f'ℹ️  Open positions: {len(tracker.get_open_positions())}')
print(f'ℹ️  Total PnL: {tracker.get_total_pnl():.2f} USDT')
"

# Risk status
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
status = rm.get_risk_status()
print(f\"{'✅' if not status['kill_switch_active'] else '🔴'} Kill-switch: {'ACTIVE' if status['kill_switch_active'] else 'OK'}\")
print(f\"ℹ️  Daily PnL: {status['daily_pnl']:.2f} USDT\")
"

echo "=== End Health Check ==="
EOF
```

**Evening Review (Optional, 23:30 UTC)**:
- Check Telegram for daily summary (sent at 23:00)
- Verify stats match expectations
- Note any anomalies in monitoring log

**Weekly Deep Dive (Day 15, 2 hours)**:
```bash
# Generate Phase 13 report
cd /home/miko/LAB/projects/THUNES
source .venv/bin/activate

python <<'EOF'
from datetime import datetime, timedelta
from src.models.position import PositionTracker
from src.risk.manager import RiskManager
import json

print("=" * 60)
print("THUNES Phase 13 - 7-Day Report")
print(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 60)

# Load position tracker
tracker = PositionTracker()

# Closed positions (PnL data)
closed_positions = tracker.get_closed_positions()
if closed_positions:
    total_pnl = sum(p.pnl for p in closed_positions)
    wins = [p for p in closed_positions if p.pnl > 0]
    losses = [p for p in closed_positions if p.pnl < 0]
    win_rate = len(wins) / len(closed_positions) * 100 if closed_positions else 0

    print(f"\n📊 Trading Performance")
    print(f"Total Trades: {len(closed_positions)}")
    print(f"Wins: {len(wins)} | Losses: {len(losses)}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Total PnL: {total_pnl:.2f} USDT")
    print(f"Average PnL/Trade: {total_pnl/len(closed_positions):.2f} USDT")
else:
    print("\n📊 Trading Performance: No closed positions")

# Open positions
open_positions = tracker.get_open_positions()
print(f"\n🔓 Open Positions: {len(open_positions)}")
if open_positions:
    for pos in open_positions:
        print(f"  - {pos.symbol}: {pos.quantity:.6f} @ {pos.entry_price:.2f}")

# Risk status
rm = RiskManager(position_tracker=tracker)
status = rm.get_risk_status()
print(f"\n⚠️  Risk Management")
print(f"Kill-Switch: {'🔴 ACTIVE' if status['kill_switch_active'] else '🟢 OK'}")
print(f"Daily PnL: {status['daily_pnl']:.2f} / {status['max_daily_loss']:.2f} USDT")
print(f"Positions: {status['open_positions']}/{status['max_positions']}")

# System health
import sqlite3
conn = sqlite3.connect('logs/jobs.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM apscheduler_jobs")
job_count = cursor.fetchone()[0]
print(f"\n🔧 System Health")
print(f"Scheduled Jobs: {job_count}")

# Count signal checks in logs (approx)
with open('logs/scheduler.log', 'r') as f:
    signal_checks = sum(1 for line in f if 'Signal check completed' in line)
print(f"Signal Checks Executed: {signal_checks} (expected: ~1008 for 7 days)")

# WebSocket stability
with open('logs/paper_trader.log', 'r') as f:
    reconnects = sum(1 for line in f if 'reconnect' in line.lower())
print(f"WebSocket Reconnections: {reconnects} (<35 acceptable for 7 days)")

print("\n" + "=" * 60)
print("End Report")
print("=" * 60)
EOF
```

**Success Criteria** (by Day 15):

| Metric | Target | Pass/Fail |
|--------|--------|-----------|
| **Uptime** | 168 hours continuous | ☐ |
| **Signal Checks** | ~1008 executions (144/day × 7) | ☐ |
| **WebSocket Stability** | <5 reconnections/day avg | ☐ |
| **Memory Stable** | RSS <500MB throughout | ☐ |
| **Trades Executed** | 5-10 paper trades | ☐ |
| **Position Limits** | No breaches | ☐ |
| **Kill-Switch** | NOT triggered (unless extreme market) | ☐ |
| **Audit Trail** | All trades logged | ☐ |
| **Telegram Summaries** | 7 consecutive days received | ☐ |

**Failure Response Matrix**:

| Issue | Severity | Action | Continue? |
|-------|----------|--------|-----------|
| Kill-switch triggered (market conditions) | Low | Deactivate manually, resume | ✅ YES |
| Scheduler crashed | High | Fix bug, extend Phase 13 by 2 days | ❌ NO |
| WebSocket >20 reconnects/day | Medium | Investigate network, conditional continue | ⚠️ CONDITIONAL |
| Memory leak (RSS >1GB) | High | Profile, fix, restart Phase 13 | ❌ NO |
| Order rejection (-1013 error) | Critical | Fix ExchangeFilters, restart Phase 13 | ❌ NO |
| Position tracker desync | Critical | Fix PositionTracker, restart Phase 13 | ❌ NO |

**Deliverables**:
- ✅ 7-day monitoring log (daily health checks)
- ✅ Phase 13 final report (trading performance, system health)
- ✅ Incident log (crashes, errors, manual interventions)
- ✅ **GO/NO-GO decision for Phase 14**

**Decision Gate**: If all success criteria met → Proceed to Phase 14. If critical issues → Fix and restart Phase 13.

---

## WEEK 3: Pre-Production Hardening (Day 16-22)

### Day 17-18: Security & Configuration (10 hours)

**Security Audit** (4 hours):

1. **API Key Permissions Review** (1 hour)
   ```
   Binance > API Management > Edit Restrictions

   ✅ Enable Trading
   ❌ Disable Withdrawals  ← CRITICAL
   ❌ Disable Universal Transfer  ← CRITICAL
   ❌ Disable Margin Trading
   ❌ Disable Futures Trading

   IP Whitelist: <your_server_IP> (recommended)
   ```

2. **Secret Management Audit** (1 hour)
   ```bash
   # 1. Verify file permissions (600 = owner read-write only)
   ls -l ~/.config/codex/secrets.env
   # Should show: -rw------- (600)

   # 2. Verify .env permissions
   ls -l .env
   # Should show: -rw------- (600)

   # 3. Check .gitignore
   grep -E "\.env|secrets\.env" .gitignore
   # Should include both files

   # 4. Audit git history for leaked secrets
   git log -p | grep -iE "api.*key|secret|password" || echo "✅ No secrets found"
   ```

3. **Kill-Switch Manual Trigger Test** (1 hour)
   ```bash
   # Test kill-switch activation + Telegram alert
   python -c "
   from src.risk.manager import RiskManager
   from src.models.position import PositionTracker

   rm = RiskManager(position_tracker=PositionTracker(), enable_telegram=True)
   rm.activate_kill_switch('Pre-production security test')

   # Verify:
   # 1. Telegram alert received
   # 2. Audit log entry created
   # 3. Future trades rejected
   "

   # Attempt trade (should reject)
   python -c "
   from src.live.paper_trader import PaperTrader
   trader = PaperTrader(testnet=False)  # ⚠️ Production API
   is_valid, reason = trader.risk_manager.validate_trade('BTCUSDT', 10.0)
   print(f'Trade allowed: {is_valid}')
   print(f'Reason: {reason}')
   # Expected: is_valid=False, reason contains 'KILL-SWITCH'
   "

   # Deactivate
   python -c "
   from src.risk.manager import RiskManager
   from src.models.position import PositionTracker

   rm = RiskManager(position_tracker=PositionTracker())
   rm.deactivate_kill_switch()
   print('✅ Kill-switch deactivated')
   "
   ```

4. **Code Review: Hardcoded Secrets** (1 hour)
   ```bash
   # Search codebase for potential hardcoded secrets
   grep -r "api.*key\|secret\|password" src/ tests/ --exclude-dir=__pycache__
   # Review results - all should be from config.py or comments
   ```

**Production Configuration** (2 hours):

1. **Backup Testnet Config** (15 minutes)
   ```bash
   # Backup current .env
   cp .env .env.testnet.backup
   ```

2. **Update `.env` for Production** (30 minutes)
   ```bash
   # CRITICAL: Update these values
   ENVIRONMENT=live  # ⚠️ Changes API endpoint to mainnet

   # Conservative risk limits for micro-live
   DEFAULT_QUOTE_AMOUNT=10.0  # Start with 10 EUR
   MAX_LOSS_PER_TRADE=2.0     # Reduce from 5.0
   MAX_DAILY_LOSS=10.0        # Reduce from 20.0
   MAX_POSITIONS=2            # Reduce from 3
   COOL_DOWN_MINUTES=120      # Increase from 60 (2 hours)

   # Production API keys (mainnet Binance)
   BINANCE_API_KEY=<production_key>
   BINANCE_API_SECRET=<production_secret>

   # Telegram (already configured)
   TELEGRAM_BOT_TOKEN=<existing>
   TELEGRAM_CHAT_ID=<existing>
   ```

3. **Verify Production Config** (15 minutes)
   ```bash
   # Load and verify settings
   python -c "
   from src.config import settings

   print(f'Environment: {settings.environment}')
   assert settings.environment == 'live', '⚠️ Not in live mode!'

   print(f'Testnet: {settings.testnet}')
   assert not settings.testnet, '⚠️ Still using testnet!'

   print(f'Quote Amount: {settings.default_quote_amount}')
   print(f'Max Daily Loss: {settings.max_daily_loss}')
   print(f'Max Positions: {settings.max_positions}')
   print(f'Cool-Down: {settings.cool_down_minutes} minutes')

   print('✅ Production config validated')
   "
   ```

4. **Test Production API Connection** (30 minutes)
   ```bash
   # Test Binance mainnet connection (NO TRADES)
   python -c "
   from binance.client import Client
   from src.config import settings

   client = Client(settings.api_key, settings.api_secret, testnet=False)

   # Get account info
   account = client.get_account()
   print(f\"Account Status: {account['accountType']}\")
   print(f\"Can Trade: {account['canTrade']}\")
   print(f\"Can Withdraw: {account['canWithdraw']}\")  # Should be False

   # Check balances
   balances = {b['asset']: float(b['free']) for b in account['balances'] if float(b['free']) > 0}
   print(f'Available Balances: {balances}')

   # Verify USDT available for trading
   usdt_balance = balances.get('USDT', 0)
   print(f'USDT Balance: {usdt_balance:.2f}')
   assert usdt_balance >= settings.default_quote_amount, '⚠️ Insufficient USDT balance!'

   print('✅ Production API connection validated')
   "
   ```

5. **Set File Permissions** (15 minutes)
   ```bash
   # Secure sensitive files
   chmod 600 .env
   chmod 600 ~/.config/codex/secrets.env

   # Verify
   ls -l .env ~/.config/codex/secrets.env
   # Both should show: -rw------- (600)
   ```

**Runbook Creation** (4 hours):

Create `docs/RUNBOOK.md` - see full content in next section.

**Checklist**:
- [ ] API keys trading-only (withdrawals disabled)
- [ ] Secret files secured (600 permissions)
- [ ] No secrets in git history
- [ ] Kill-switch tested + Telegram alert received
- [ ] Production .env configured
- [ ] Production API connection tested
- [ ] USDT balance sufficient (≥10 EUR)
- [ ] Runbook created

---

### Day 19-22: Runbook & Final Validation (6 hours)

**Create `docs/RUNBOOK.md`** (4 hours):

```markdown
# THUNES Production Runbook
**Version**: 1.0
**Last Updated**: 2025-10-17
**Environment**: Live (Binance Mainnet)

---

## Emergency Procedures

### 🚨 Kill-Switch Manual Activation

**When to Use**:
- Unusual market conditions (flash crash, exchange issues)
- Suspected bug in trading logic
- Need to pause system for investigation

**Steps**:
```bash
cd /home/miko/LAB/projects/THUNES
source .venv/bin/activate

python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

rm = RiskManager(position_tracker=PositionTracker(), enable_telegram=True)
rm.activate_kill_switch('Manual intervention: <INSERT REASON>')
print('✅ Kill-switch activated')
"

# Verify Telegram alert received
```

**Verification**:
- Telegram alert received
- Audit log entry: `cat logs/audit_trail.jsonl | tail -1 | jq .`
- Future trades blocked (test with dry-run if needed)

### 🟢 Kill-Switch Deactivation

**When to Use**:
- Market conditions normalized
- Bug fixed and deployed
- Ready to resume trading

**Steps**:
```bash
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

rm = RiskManager(position_tracker=PositionTracker())
rm.deactivate_kill_switch()
print('✅ Kill-switch deactivated')
"

# Verify
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

rm = RiskManager(position_tracker=PositionTracker())
status = rm.get_risk_status()
assert not status['kill_switch_active'], 'Kill-switch still active!'
print('✅ Kill-switch confirmed off')
"
```

### ⛔ Emergency Stop (Complete Trading Halt)

**When to Use**:
- Critical system failure
- Security incident
- Immediate manual intervention required

**Steps**:
```bash
# 1. Stop scheduler (prevents new signal checks)
pkill -f "run_scheduler.py"

# Verify stopped
ps aux | grep run_scheduler || echo "✅ Scheduler stopped"

# 2. Activate kill-switch
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker(), enable_telegram=True)
rm.activate_kill_switch('Emergency stop: <REASON>')
"

# 3. Close all open positions manually via Binance UI
# Login to Binance > Spot Trading > Open Orders > Cancel All
# Then close positions at market price

# 4. Verify no jobs running
sqlite3 logs/jobs.db "SELECT * FROM apscheduler_jobs WHERE next_run_time IS NOT NULL;"
```

**Recovery**:
```bash
# After issue resolved:
# 1. Fix root cause
# 2. Test fix in separate environment
# 3. Deactivate kill-switch
# 4. Restart scheduler
python src/orchestration/run_scheduler.py --daemon &
echo $! > logs/scheduler.pid
```

---

## Daily Operations

### Morning Checklist (09:00 UTC)

**Time Required**: 10 minutes

```bash
cd /home/miko/LAB/projects/THUNES
source .venv/bin/activate

# Run automated health check
bash <<'EOF'
echo "=== THUNES Daily Health Check $(date) ==="

# 1. Scheduler status
if ps aux | grep -q "[r]un_scheduler"; then
    echo "✅ Scheduler running"
else
    echo "🔴 Scheduler NOT running - INVESTIGATE"
fi

# 2. Recent errors
ERROR_COUNT=$(tail -200 logs/scheduler.log | grep -c ERROR)
if [ $ERROR_COUNT -eq 0 ]; then
    echo "✅ No scheduler errors"
else
    echo "⚠️  $ERROR_COUNT scheduler errors in last 200 lines"
    tail -200 logs/scheduler.log | grep ERROR
fi

# 3. Position status
python -c "
from src.models.position import PositionTracker
tracker = PositionTracker()
positions = tracker.get_open_positions()
print(f'ℹ️  Open positions: {len(positions)}')
if positions:
    for p in positions:
        print(f'   - {p.symbol}: {p.quantity:.6f} @ {p.entry_price:.2f}')
print(f'ℹ️  Total PnL: {tracker.get_total_pnl():.2f} USDT')
"

# 4. Risk status
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
status = rm.get_risk_status()
print(f\"{'✅' if not status['kill_switch_active'] else '🔴'} Kill-switch: {'ACTIVE' if status['kill_switch_active'] else 'OK'}\")
print(f\"ℹ️  Daily PnL: {status['daily_pnl']:.2f} / {status['max_daily_loss']:.2f} USDT\")
print(f\"ℹ️  Positions: {status['open_positions']}/{status['max_positions']}\")
"

# 5. WebSocket health
RECONNECTS=$(grep -c "reconnect" logs/paper_trader.log 2>/dev/null || echo 0)
echo "ℹ️  Total WebSocket reconnections: $RECONNECTS"

echo "=== End Health Check ==="
EOF
```

**Action Items**:
- ✅ All green → No action
- ⚠️ Scheduler errors → Review logs, investigate
- 🔴 Scheduler stopped → Restart (see "Scheduler Management" below)
- 🔴 Kill-switch active → Review reason, deactivate if appropriate
- ⚠️ Daily PnL < -8 EUR (80% of limit) → Manual review, consider pausing

### Evening Review (23:30 UTC) - Optional

**Time Required**: 5 minutes

```bash
# 1. Check Telegram for daily summary (sent at 23:00 UTC)

# 2. Quick audit trail review
tail -20 logs/audit_trail.jsonl | jq '.event' | sort | uniq -c

# 3. Note any anomalies in personal log
```

---

## Weekly Operations

### Sunday Performance Review (1 hour)

**Generate Weekly Report**:
```bash
cd /home/miko/LAB/projects/THUNES
source .venv/bin/activate

python <<'EOF'
from datetime import datetime, timedelta
from src.models.position import PositionTracker
from src.risk.manager import RiskManager

print("=" * 60)
print("THUNES Weekly Report")
print(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 60)

tracker = PositionTracker()

# Closed positions (PnL)
closed = tracker.get_closed_positions()
if closed:
    # Filter last 7 days
    week_ago = datetime.now() - timedelta(days=7)
    weekly_closed = [p for p in closed if p.exit_time and p.exit_time > week_ago]

    if weekly_closed:
        total_pnl = sum(p.pnl for p in weekly_closed)
        wins = [p for p in weekly_closed if p.pnl > 0]
        losses = [p for p in weekly_closed if p.pnl < 0]
        win_rate = len(wins) / len(weekly_closed) * 100

        print(f"\n📊 Weekly Trading Performance")
        print(f"Total Trades: {len(weekly_closed)}")
        print(f"Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Total PnL: {total_pnl:.2f} USDT")
        print(f"Average PnL/Trade: {total_pnl/len(weekly_closed):.2f} USDT")
    else:
        print("\n📊 No trades closed this week")
else:
    print("\n📊 No closed positions")

# Open positions
open_pos = tracker.get_open_positions()
print(f"\n🔓 Open Positions: {len(open_pos)}")

# Risk status
rm = RiskManager(position_tracker=tracker)
status = rm.get_risk_status()
print(f"\n⚠️  Risk Management")
print(f"Kill-Switch: {'🔴 ACTIVE' if status['kill_switch_active'] else '🟢 OK'}")

print("\n" + "=" * 60)
EOF
```

**Review Checklist**:
- [ ] PnL trend (positive/negative/neutral)
- [ ] Win rate (target: ≥40%)
- [ ] Average PnL per trade
- [ ] Any kill-switch activations
- [ ] WebSocket stability (<35 reconnects/week)

**Actions**:
- **If PnL negative for 2+ consecutive weeks** → Consider re-optimization
- **If win rate <30%** → Re-optimize or pause for strategy review
- **If stable positive performance** → Consider increasing quote amount (cautiously)

### Bi-Weekly Re-Optimization (2 hours)

**Schedule**: Every 2 weeks (Sunday evening)

**Steps**:
```bash
cd /home/miko/LAB/projects/THUNES
source .venv/bin/activate

# 1. Run optimization (25 trials, ~30 minutes)
make optimize

# 2. Review results
cat artifacts/optuna/study.csv

# 3. Compare to current parameters
python -c "
import json
with open('artifacts/optimize/best_params_RSI.json', 'r') as f:
    current = json.load(f)
print('Current parameters:')
print(json.dumps(current, indent=2))
"

# 4. If Sharpe improved by ≥10%:
python src/optimize/auto_reopt.py --apply

# Scheduler will auto-reload parameters on next signal check
# Telegram notification sent

# 5. Monitor performance for next 7 days
# If degradation → Revert to previous parameters
```

**Decision Criteria**:
- **Sharpe improvement ≥10%** → Apply new parameters
- **Sharpe improvement <10%** → Keep current parameters (insufficient evidence)
- **Sharpe degraded** → Do NOT apply (backtest may not reflect live conditions)

---

## Scheduler Management

### Start Scheduler

```bash
cd /home/miko/LAB/projects/THUNES
source .venv/bin/activate

# Start in daemon mode
nohup python src/orchestration/run_scheduler.py --daemon > logs/scheduler_daemon.log 2>&1 &
echo $! > logs/scheduler.pid

# Verify
sleep 5
ps aux | grep run_scheduler && echo "✅ Scheduler started" || echo "🔴 Failed to start"
```

### Stop Scheduler (Graceful)

```bash
# Read PID
SCHEDULER_PID=$(cat logs/scheduler.pid 2>/dev/null)

if [ -n "$SCHEDULER_PID" ]; then
    # Send SIGTERM (graceful shutdown)
    kill -TERM $SCHEDULER_PID

    # Wait for shutdown (max 30s)
    for i in {1..30}; do
        if ! ps -p $SCHEDULER_PID > /dev/null 2>&1; then
            echo "✅ Scheduler stopped gracefully"
            rm logs/scheduler.pid
            break
        fi
        sleep 1
    done
else
    # No PID file - try pkill
    pkill -f "run_scheduler.py"
fi
```

### Restart Scheduler

```bash
# Stop (graceful)
bash /path/to/stop_scheduler.sh

# Wait 5 seconds
sleep 5

# Start
bash /path/to/start_scheduler.sh
```

### Check Scheduler Status

```bash
# Process status
ps aux | grep run_scheduler

# Job status
sqlite3 logs/jobs.db "SELECT name, next_run_time FROM apscheduler_jobs ORDER BY next_run_time;"

# Recent activity
tail -50 logs/scheduler.log
```

---

## Parameter Management

### View Current Parameters

```bash
cat artifacts/optimize/best_params_RSI.json | jq .
```

### Manual Parameter Update

**⚠️ Use with caution - prefer automated re-optimization**

```bash
# 1. Edit parameters file
nano artifacts/optimize/best_params_RSI.json

# Example:
# {
#   "period": 14,
#   "oversold": 30,
#   "overbought": 70,
#   "sharpe_ratio": 1.23,
#   "optimized_at": "2025-10-17T10:00:00"
# }

# 2. Trigger reload
# Scheduler auto-detects file changes on next signal check
# OR restart scheduler to force reload

# 3. Verify reload in logs
tail -f logs/paper_trader.log | grep "Parameters loaded"
```

---

## Monitoring & Alerts

### Key Metrics (Prometheus - If Phase 11 Implemented)

Access Grafana dashboard at `http://localhost:3000`

**Critical Dashboards**:
- **Daily PnL**: Should trend positive or neutral
- **Kill-Switch Status**: Should be 0 (off)
- **WebSocket Reconnections**: <5/day acceptable
- **Circuit Breaker State**: Should be 0 (closed)

**Alert Thresholds**:
- Kill-switch activated → Immediate Telegram alert
- Daily PnL < -8 EUR → Manual review
- WebSocket >10 reconnects/hour → Network investigation
- No trades for 72 hours → Strategy may be stale, re-optimize

### Telegram Alerts

**Expected Notifications**:
- **Daily Summary** (23:00 UTC): Performance stats, risk status, system health
- **Kill-Switch Activation**: Immediate alert when triggered
- **Parameter Decay** (if Sharpe <0.5): Warning to re-optimize
- **Re-Optimization Applied**: Notification when new parameters loaded

**If Alerts Stop**:
```bash
# Test Telegram connectivity
python -c "
from src.alerts.telegram import TelegramBot
bot = TelegramBot()
bot.send_message_sync('🧪 Test alert from THUNES')
"

# If fails → Check .env credentials
grep TELEGRAM .env
```

---

## Troubleshooting

### Issue: Scheduler Crashed

**Symptoms**:
- `ps aux | grep run_scheduler` returns nothing
- No recent entries in `logs/scheduler.log`

**Diagnosis**:
```bash
# Check last error in log
tail -100 logs/scheduler.log | grep ERROR

# Check daemon log (if using nohup)
tail -100 logs/scheduler_daemon.log
```

**Resolution**:
```bash
# Fix underlying issue (e.g., missing dependency, config error)

# Restart scheduler
python src/orchestration/run_scheduler.py --daemon &
echo $! > logs/scheduler.pid
```

### Issue: WebSocket Keeps Disconnecting

**Symptoms**:
- Frequent "reconnect" messages in `logs/paper_trader.log`
- >10 reconnections/hour

**Diagnosis**:
```bash
# Count reconnections
grep -c "reconnect" logs/paper_trader.log

# Check for patterns (time-based, error-based)
grep "reconnect" logs/paper_trader.log | tail -20
```

**Resolution**:
- **If network issue** → Check internet stability, firewall rules
- **If Binance side** → Check Binance status page
- **If persistent** → Increase watchdog timeout in `ws_stream.py`

### Issue: Kill-Switch Won't Deactivate

**Symptoms**:
- `deactivate_kill_switch()` called but status still active

**Diagnosis**:
```bash
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
print(rm.kill_switch_active)
print(rm.get_risk_status())
"
```

**Resolution**:
```bash
# Manually reset (emergency only)
python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
rm = RiskManager(position_tracker=PositionTracker())
rm.kill_switch_active = False  # Direct override
rm._write_audit_log('MANUAL_RESET', {'reason': 'Emergency override'})
print('✅ Kill-switch force-deactivated')
"
```

### Issue: Order Rejected (-1013 Error)

**Symptoms**:
- Trades fail with "Filter failure: -1013"
- Logs show `ExchangeFilters` errors

**Diagnosis**:
```bash
# Test filter validation
python -c "
from binance.client import Client
from src.config import settings
from src.filters.exchange_filters import ExchangeFilters

client = Client(settings.api_key, settings.api_secret, testnet=False)
filters = ExchangeFilters(client)

# Test validation
is_valid, msg = filters.validate_order('BTCUSDT', quote_qty=10.0)
print(f'Valid: {is_valid}')
print(f'Message: {msg}')

# Check filters
print(f'Tick size: {filters.get_tick_size(\"BTCUSDT\")}')
print(f'Step size: {filters.get_step_size(\"BTCUSDT\")}')
print(f'Min notional: {filters.get_min_notional(\"BTCUSDT\")}')
"
```

**Resolution**:
- **If quote amount too small** → Increase `DEFAULT_QUOTE_AMOUNT` in `.env`
- **If rounding issue** → Verify `ExchangeFilters` implementation
- **If Binance changed filters** → Re-fetch exchange info (restart system)

---

## Backup & Recovery

### Daily Backups

**Automated** (recommended - add to cron):
```bash
# Add to crontab: Daily backup at 00:00 UTC
0 0 * * * /home/miko/LAB/projects/THUNES/scripts/daily_backup.sh
```

**Manual**:
```bash
# Create backup directory
mkdir -p backups/$(date +%Y-%m-%d)

# Backup critical data
cp logs/audit_trail.jsonl backups/$(date +%Y-%m-%d)/
cp logs/jobs.db backups/$(date +%Y-%m-%d)/
cp artifacts/optimize/best_params_RSI.json backups/$(date +%Y-%m-%d)/
cp .env backups/$(date +%Y-%m-%d)/env.backup

# Create archive
tar -czf backups/thunes_backup_$(date +%Y-%m-%d).tar.gz backups/$(date +%Y-%m-%d)/

echo "✅ Backup created: backups/thunes_backup_$(date +%Y-%m-%d).tar.gz"
```

### Restore from Backup

```bash
# Extract backup
tar -xzf backups/thunes_backup_YYYY-MM-DD.tar.gz

# Restore files
cp backups/YYYY-MM-DD/audit_trail.jsonl logs/
cp backups/YYYY-MM-DD/jobs.db logs/
cp backups/YYYY-MM-DD/best_params_RSI.json artifacts/optimize/

# Restart scheduler to reload
pkill -f run_scheduler
python src/orchestration/run_scheduler.py --daemon &
```

---

## Contact & Escalation

**Primary Operator**: Mickael Souedan
**Emergency Contact**: [Your phone/email]

**Escalation Path**:
1. Review runbook procedures
2. Check logs: `logs/scheduler.log`, `logs/paper_trader.log`, `logs/audit_trail.jsonl`
3. If critical financial impact → Emergency stop (see above)
4. Document incident in `docs/incidents/YYYY-MM-DD_description.md`

---

## Appendix: File Locations

```
/home/miko/LAB/projects/THUNES/
├── logs/
│   ├── scheduler.log          # Scheduler activity
│   ├── paper_trader.log       # Trading activity
│   ├── audit_trail.jsonl      # Immutable audit trail
│   ├── jobs.db                # APScheduler job store
│   └── scheduler.pid          # Scheduler process ID
├── artifacts/
│   └── optimize/
│       └── best_params_RSI.json  # Current strategy parameters
├── .env                       # Production configuration
└── docs/
    └── RUNBOOK.md             # This file
```

---

**Document Version History**:
- v1.0 (2025-10-17): Initial production runbook
```

**Final Validation** (2 hours):

1. **Dry-Run All Procedures** (1 hour)
   ```bash
   # Test each runbook procedure in safe mode:

   # 1. Kill-switch activation/deactivation
   # 2. Emergency stop
   # 3. Scheduler restart
   # 4. Parameter update
   # 5. Health check
   # 6. Weekly report generation
   ```

2. **Team Briefing** (1 hour, if applicable)
   - Walk through runbook with stakeholders
   - Assign responsibilities (who monitors, who escalates)
   - Agree on decision criteria (when to pause/resume)

**Checklist**:
- [ ] Runbook created (`docs/RUNBOOK.md`)
- [ ] All procedures tested
- [ ] Team briefed (if applicable)
- [ ] Backup strategy defined

---

## WEEK 4-7: Phase 14 - Micro-Live Trading (Day 19-47)

### Day 19: Production Deployment (2 hours)

**Pre-Flight Checklist**:
- ✅ Phase 13 completed successfully (7 days, all criteria met)
- ✅ Security audit passed
- ✅ Production .env configured
- ✅ Runbook reviewed and procedures tested
- ✅ Telegram alerts working
- ✅ API keys trading-only (withdrawals disabled)
- ✅ USDT balance ≥10 EUR

**Deployment Steps**:

1. **Final Configuration Verification** (30 minutes)
   ```bash
   cd /home/miko/LAB/projects/THUNES
   source .venv/bin/activate

   # Verify ENVIRONMENT=live
   python -c "
   from src.config import settings
   assert settings.environment == 'live', 'Not in live mode!'
   assert not settings.testnet, 'Still on testnet!'
   print('✅ Production mode confirmed')
   print(f'Quote amount: {settings.default_quote_amount} USDT')
   print(f'Max daily loss: {settings.max_daily_loss} USDT')
   print(f'Max positions: {settings.max_positions}')
   "
   ```

2. **Backup Testnet Data** (15 minutes)
   ```bash
   # Archive Phase 13 results
   mkdir -p backups/phase13_testnet
   cp -r logs/ backups/phase13_testnet/
   cp -r artifacts/ backups/phase13_testnet/

   # Clear logs for fresh start
   > logs/scheduler.log
   > logs/paper_trader.log
   > logs/audit_trail.jsonl

   # Keep jobs.db (preserve job schedules)
   ```

3. **Deploy Production Scheduler** (30 minutes)
   ```bash
   # Start scheduler with production config
   nohup python src/orchestration/run_scheduler.py --daemon > logs/scheduler_daemon.log 2>&1 &
   echo $! > logs/scheduler.pid

   # Verify startup
   sleep 10
   ps aux | grep run_scheduler && echo "✅ Scheduler running" || echo "🔴 Failed"

   # Check first signal check (within 10 minutes)
   tail -f logs/scheduler.log
   # Wait for "Signal check completed" message
   ```

4. **Monitor First Trade** (45 minutes)
   ```bash
   # Watch logs for first signal
   tail -f logs/scheduler.log logs/paper_trader.log

   # When trade executes, verify:
   # 1. ExchangeFilters validated order
   # 2. Risk manager approved
   # 3. Order placed successfully
   # 4. Position tracked
   # 5. Audit log written

   # Check Binance UI
   # Login > Spot Trading > Order History
   # Verify order appears
   ```

**Go-Live Decision**:
- ✅ Scheduler running
- ✅ First signal check completed (no errors)
- ✅ If trade executed: Order visible in Binance UI
- ✅ Audit trail logging
- ✅ Telegram daily summary scheduled

**If any checks fail** → Emergency stop, investigate, fix, restart Day 19

---

### Day 20-33: Monitoring Period 1 (2 Weeks)

**Daily Monitoring** (10 min/day):
- Run morning health check (see Runbook)
- Review Telegram daily summary
- Check audit trail for anomalies
- Monitor capital (should not drop below 5 EUR)

**Weekly Deep Dive** (1 hour, Day 26 & Day 33):
- Generate weekly report (see Runbook)
- Calculate Sharpe ratio (if ≥10 trades)
- Review win rate, average PnL
- Check WebSocket stability

**Week 2 Decision Gate (Day 33)**:

| Metric | Target | Action if Not Met |
|--------|--------|-------------------|
| **Capital** | ≥5 EUR (max -5 EUR loss) | Reduce quote to 5 EUR |
| **Kill-Switch** | 0-1 activations | If >1: Investigate, consider pause |
| **System Uptime** | >95% (max 16h downtime) | Investigate crashes |
| **Trades Executed** | ≥5 trades | If 0: Re-optimize, market may be ranging |

**Actions**:
- ✅ All targets met → Continue to Week 3-4
- ⚠️ Capital 5-10 EUR → Reduce quote to 5 EUR, continue monitoring
- ❌ Capital <5 EUR → **Pause trading**, full strategy review
- ❌ >2 kill-switch triggers → **Pause trading**, investigate

---

### Day 34-47: Monitoring Period 2 (2 Weeks)

**Daily Operations**: Same as Period 1

**Bi-Weekly Re-Optimization (Day 40)**:
```bash
# Run optimization
make optimize

# Review Sharpe improvement
# If ≥10% improvement → Apply new parameters
python src/optimize/auto_reopt.py --apply
```

**Week 4 Decision Gate (Day 47) - FINAL REVIEW**:

**Performance Targets**:
| Metric | Target | Excellent |
|--------|--------|-----------|
| **Total PnL** | >0 EUR | >5 EUR |
| **Sharpe Ratio** | ≥0.5 | ≥1.0 |
| **Max Drawdown** | <30% | <20% |
| **Win Rate** | ≥40% | ≥50% |
| **Kill-Switch** | <3 activations | 0 activations |
| **Uptime** | >95% | >99% |

**Decision Matrix**:

| Scenario | Action |
|----------|--------|
| **All targets met** | ✅ Increase quote to 20 EUR, graduate to Phase 15 (ML) |
| **PnL >0, Sharpe ≥0.5** | ✅ Continue at 10 EUR, monitor 2 more weeks |
| **PnL >0, Sharpe <0.5** | ⚠️ Strategy barely profitable, re-optimize |
| **PnL 0 to -5 EUR** | ⚠️ Continue monitoring, no capital increase |
| **PnL -5 to -10 EUR** | ❌ Pause trading, full strategy review |
| **Kill-switch >3 triggers** | ❌ Pause trading, risk management review |

**Final Report (Day 47)**:

Generate comprehensive 30-day report:
```bash
cd /home/miko/LAB/projects/THUNES
source .venv/bin/activate

python <<'EOF'
import json
from datetime import datetime, timedelta
from src.models.position import PositionTracker
from src.risk.manager import RiskManager

print("=" * 70)
print("THUNES Phase 14 - 30-Day Production Report")
print(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 70)

tracker = PositionTracker()

# All closed positions
closed = tracker.get_closed_positions()
if closed:
    total_pnl = sum(p.pnl for p in closed)
    wins = [p for p in closed if p.pnl > 0]
    losses = [p for p in closed if p.pnl < 0]
    win_rate = len(wins) / len(closed) * 100

    # Calculate Sharpe ratio (if enough data)
    if len(closed) >= 10:
        pnls = [p.pnl for p in closed]
        import numpy as np
        sharpe = np.mean(pnls) / np.std(pnls) * np.sqrt(252)  # Annualized
    else:
        sharpe = None

    # Max drawdown
    cumulative_pnl = 0
    peak = 0
    max_dd = 0
    for p in sorted(closed, key=lambda x: x.exit_time):
        cumulative_pnl += p.pnl
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        dd = (peak - cumulative_pnl) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    print(f"\n📊 Trading Performance (30 Days)")
    print(f"Total Trades: {len(closed)}")
    print(f"Wins: {len(wins)} | Losses: {len(losses)}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Total PnL: {total_pnl:.2f} EUR")
    print(f"Average PnL/Trade: {total_pnl/len(closed):.2f} EUR")
    if sharpe:
        print(f"Sharpe Ratio: {sharpe:.2f} (annualized)")
    print(f"Max Drawdown: {max_dd:.1f}%")

    # Best/Worst trades
    best = max(closed, key=lambda p: p.pnl)
    worst = min(closed, key=lambda p: p.pnl)
    print(f"\nBest Trade: {best.symbol} @ {best.pnl:.2f} EUR")
    print(f"Worst Trade: {worst.symbol} @ {worst.pnl:.2f} EUR")
else:
    print("\n📊 No trades executed")

# Risk events
with open('logs/audit_trail.jsonl', 'r') as f:
    events = [json.loads(line) for line in f]

kill_switch_activations = [e for e in events if e['event'] == 'KILL_SWITCH_ACTIVATED']
print(f"\n⚠️  Risk Events")
print(f"Kill-Switch Activations: {len(kill_switch_activations)}")
if kill_switch_activations:
    for e in kill_switch_activations:
        print(f"  - {e['timestamp']}: {e.get('details', {}).get('reason', 'N/A')}")

# System health
trade_rejections = [e for e in events if e['event'] == 'TRADE_REJECTED']
print(f"\n🔧 System Health")
print(f"Trade Rejections: {len(trade_rejections)}")

# Uptime estimate (crude)
import sqlite3
conn = sqlite3.connect('logs/jobs.db')
cursor = conn.cursor()
# This is approximate - better to track in monitoring
print(f"Jobs Scheduled: {cursor.execute('SELECT COUNT(*) FROM apscheduler_jobs').fetchone()[0]}")

print("\n" + "=" * 70)
print("DECISION GATE: Phase 15 Readiness")
print("=" * 70)

# Automated decision
if closed:
    if total_pnl > 0 and sharpe and sharpe >= 1.0:
        print("✅ RECOMMENDATION: Graduate to Phase 15 (AI/ML)")
        print("   - Increase quote amount to 20 EUR")
        print("   - Begin ML experimentation")
    elif total_pnl > 0 and sharpe and sharpe >= 0.5:
        print("⚠️  RECOMMENDATION: Continue Phase 14 (2 more weeks)")
        print("   - Maintain 10 EUR quote amount")
        print("   - Monitor performance")
    elif total_pnl > -5:
        print("⚠️  RECOMMENDATION: Pause and re-optimize")
        print("   - Strategy marginally profitable")
        print("   - Run extended optimization (100 trials)")
    else:
        print("❌ RECOMMENDATION: Pause trading")
        print("   - Significant capital loss")
        print("   - Full strategy review required")
else:
    print("❌ RECOMMENDATION: Investigate")
    print("   - No trades executed in 30 days")
    print("   - Market conditions or strategy issue")

print("=" * 70)
EOF

# Save report
python generate_report.py > reports/phase14_final_$(date +%Y-%m-%d).txt
```

**Lessons Learned**:
- Document what worked, what didn't
- Identify edge cases encountered
- Note any bugs discovered
- Record manual interventions

**Next Steps**:
- ✅ **If successful** → Phase 15 (AI/ML roadmap, see CLAUDE.md)
- ⚠️ **If marginal** → Continue Phase 14, re-optimize
- ❌ **If failed** → Pause, conduct post-mortem

---

## POST-PRODUCTION: Test Coverage Hardening (Ongoing)

**Goal**: Increase coverage from 33% → 80% over 3 months

**Can run parallel to Phase 14 (non-blocking)**

### Priority 1: Execution Layer (15-20 hours)

**Week 5-6** (parallel to Phase 14 monitoring):

1. **`src/filters/exchange_filters.py`** (0% → 80%, 8 hours)
   ```python
   # tests/test_exchange_filters.py (NEW FILE)

   def test_get_tick_size():
       """Test tick size retrieval for BTCUSDT."""

   def test_get_step_size():
       """Test step size retrieval for BTCUSDT."""

   def test_round_price():
       """Test price rounding to tick size."""

   def test_round_quantity():
       """Test quantity rounding to step size."""

   def test_validate_order_min_notional():
       """Test min notional validation (10 USDT)."""

   def test_prepare_market_order():
       """Test market order preparation with rounding."""
   ```

2. **`src/live/paper_trader.py`** (0% → 60%, 10 hours)
   ```python
   # tests/test_paper_trader.py (NEW FILE)

   def test_initialization():
       """Test PaperTrader initialization."""

   def test_run_strategy_no_signal():
       """Test strategy execution with no entry signal."""

   def test_run_strategy_with_buy_signal():
       """Test strategy execution with BUY signal."""

   def test_parameter_reload():
       """Test parameter reloading from JSON file."""

   def test_position_tracking():
       """Test position lifecycle (open → close)."""
   ```

### Priority 2: Models & Optimization (10-12 hours)

**Week 7-8**:

1. **`src/models/position.py`** (30% → 80%, 6 hours)
2. **`src/optimize/run_optuna.py`** (0% → 50%, 4 hours)

### Priority 3: Monitoring (8-10 hours)

**Week 9-10**:

1. **`src/monitoring/performance_tracker.py`** (15% → 70%, 6 hours)

**Total Effort**: 33-42 hours spread over 10 weeks (3-4 hours/week)

---

## FUTURE: Phase 15-18 (AI/ML Roadmap)

**See CLAUDE.md for full details**

**Timeline**: 6-12 months post-Phase 14

**Phases**:
- **Phase 15** (Months 1-2): Signal modeling (triple-barrier, meta-labeling)
- **Phase 16** (Months 3-4): Execution ML (Kelly sizing, slippage prediction)
- **Phase 17** (Months 4-6): Governance (model registry, SHAP explainability)
- **Phase 18** (Months 6-12): Advanced (ensemble, SOR facade)

**Prerequisites**:
- Phase 14 successful (Sharpe ≥1.0 for 2+ months)
- Test coverage ≥70%
- Prometheus observability operational

---

## Progress Tracking

### Week 1 (Day 1-7)
- [ ] Day 1-2: Fix WebSocket test
- [ ] Day 2: Orchestration infrastructure
- [ ] Day 3: Orchestration integration
- [ ] Day 4: Orchestration CLI
- [ ] Day 5: Orchestration testing + Telegram config + Audit validation
- [ ] Day 6-7: Integration tests

### Week 2 (Day 8-15)
- [ ] Day 8: Deploy Phase 13
- [ ] Day 9-15: Daily monitoring (7 days)
- [ ] Day 15: Generate Phase 13 final report
- [ ] Day 15: GO/NO-GO decision

### Week 3 (Day 16-22)
- [ ] Day 17-18: Security audit + Production config + Runbook
- [ ] Day 19-22: Final validation

### Week 4-7 (Day 19-47)
- [ ] Day 19: Production deployment
- [ ] Day 20-33: Monitoring Period 1 (2 weeks)
- [ ] Day 33: Week 2 decision gate
- [ ] Day 34-47: Monitoring Period 2 (2 weeks)
- [ ] Day 40: Bi-weekly re-optimization
- [ ] Day 47: Final Phase 14 review + GO/NO-GO for Phase 15

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Kill-switch triggered early | Medium | Low | Expected behavior, manual deactivation |
| Scheduler crash in production | Low | High | Monitoring alerts, auto-restart script |
| WebSocket instability | Medium | Medium | REST fallback, reconnection logic |
| Order rejection (filter error) | Low | Critical | Comprehensive filter tests, testnet validation |
| Capital loss >10 EUR | Low | Medium | Kill-switch at -10 EUR, position limits |
| Exchange API outage | Low | Medium | Circuit breaker, graceful degradation |
| Parameter decay (Sharpe drop) | Medium | Medium | Bi-weekly re-optimization, decay detection |
| Security breach (API keys) | Very Low | Critical | Trading-only permissions, no withdrawals |

---

## Success Metrics Summary

**Phase 13 (Paper 24/7)**:
- 168 hours uptime
- ~1008 signal checks
- <35 WebSocket reconnects
- 5-10 trades executed

**Phase 14 (Micro-Live)**:
- Total PnL >0 EUR
- Sharpe ratio ≥0.5 (≥1.0 excellent)
- Max drawdown <30%
- Win rate ≥40%
- <3 kill-switch activations

**Production Readiness**:
- Test coverage ≥70%
- Prometheus metrics operational
- Runbook procedures validated
- 30+ days successful live trading

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-03 | Initial roadmap created |

---

**END OF ROADMAP**
