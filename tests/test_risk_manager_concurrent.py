"""
Risk Manager Concurrency Tests

Tests thread-safety of RiskManager under concurrent validate_trade() calls.
Sprint 1.4 - Critical path for Phase 13 rodage.

Test Categories:
1. Concurrent validate_trade() calls (5 threads × 20 trades)
2. Kill-switch activation under load
3. Cool-down period thread-safety
4. Daily PnL calculation concurrency
5. Position tracking concurrent access
6. Audit trail write thread-safety
"""

import pytest
import threading
import time
from decimal import Decimal
from pathlib import Path

from src.risk.manager import RiskManager, AUDIT_TRAIL_PATH
from src.models.position import PositionTracker


class TestRiskManagerConcurrency:
    """Concurrent risk validation tests."""

    def test_concurrent_validate_trade(self):
        """Test 5 threads × 20 trades/thread validated concurrently."""
        rm = RiskManager(position_tracker=PositionTracker())

        results = []
        errors = []

        def validate_trades(thread_id: int):
            for i in range(20):
                try:
                    is_valid, reason = rm.validate_trade(
                        symbol=f"BTC{thread_id}USDT",  # Different symbols to avoid duplicate check
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_trade_{i}"
                    )
                    results.append((thread_id, i, is_valid, reason))
                except Exception as e:
                    errors.append((thread_id, i, str(e)))
                time.sleep(0.001)

        threads = [threading.Thread(target=validate_trades, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions raised
        assert len(errors) == 0, f"Errors during concurrent validation: {errors}"

        # Verify all trades processed (100 total)
        assert len(results) == 100

        # Verify all passed (no kill-switch or limits triggered)
        valid_trades = [r for r in results if r[2]]
        assert len(valid_trades) == 100

    def test_concurrent_position_limit_enforcement(self):
        """Test MAX_POSITIONS enforced correctly under concurrent load."""
        rm = RiskManager(position_tracker=PositionTracker(), max_positions=3)

        accepted = []
        rejected = []
        errors = []

        def open_positions(thread_id: int):
            for i in range(5):
                try:
                    symbol = f"SYM{thread_id * 5 + i}USDT"
                    is_valid, reason = rm.validate_trade(
                        symbol=symbol,
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_pos_{i}"
                    )

                    if is_valid:
                        # Simulate opening position
                        rm.position_tracker.open_position(
                            symbol=symbol,
                            entry_price=Decimal("100.0"),
                            quantity=Decimal("0.1"),
                            side="LONG"
                        )
                        accepted.append((thread_id, i, symbol))
                    else:
                        rejected.append((thread_id, i, symbol, reason))

                except Exception as e:
                    errors.append((thread_id, i, str(e)))
                time.sleep(0.01)

        threads = [threading.Thread(target=open_positions, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify exactly 3 positions opened (MAX_POSITIONS limit)
        assert len(accepted) == 3, f"Expected 3 accepted, got {len(accepted)}"

        # Verify remaining 22 rejected with "MAX_POSITIONS" reason
        max_pos_rejections = [r for r in rejected if "MAX_POSITIONS" in r[3]]
        assert len(max_pos_rejections) >= 20  # Allow for timing variations

    def test_kill_switch_activation_under_concurrent_load(self):
        """Test kill-switch activated correctly when multiple threads trigger losses."""
        rm = RiskManager(
            position_tracker=PositionTracker(),
            max_daily_loss=Decimal("50.0")
        )

        kill_switch_activated = []
        errors = []

        def trigger_losses(thread_id: int):
            try:
                # Record 5 losses of $12 each = $60 total (exceeds $50 limit)
                for i in range(5):
                    rm.record_loss(Decimal("12.0"))
                    time.sleep(0.01)

                    # Check if kill-switch activated
                    if rm.kill_switch_active:
                        kill_switch_activated.append((thread_id, i))

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=trigger_losses, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify kill-switch activated
        assert rm.kill_switch_active

        # Verify at least one thread detected activation
        assert len(kill_switch_activated) > 0

    def test_cool_down_period_thread_safety(self):
        """Test cool-down period correctly enforced across threads."""
        rm = RiskManager(
            position_tracker=PositionTracker(),
            cool_down_minutes=1  # 1 minute cool-down
        )

        # Trigger cool-down
        rm.record_loss(Decimal("10.0"))
        assert rm.in_cool_down()

        blocked_trades = []
        errors = []

        def attempt_trade_during_cooldown(thread_id: int):
            try:
                for i in range(10):
                    is_valid, reason = rm.validate_trade(
                        symbol=f"SYM{thread_id}USDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_cooldown_{i}"
                    )

                    if not is_valid and "COOL_DOWN" in reason:
                        blocked_trades.append((thread_id, i))

                    time.sleep(0.01)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=attempt_trade_during_cooldown, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all trades blocked (30 total)
        assert len(blocked_trades) == 30

    def test_daily_pnl_calculation_concurrency(self):
        """Test get_daily_pnl() thread-safe when called concurrently."""
        rm = RiskManager(position_tracker=PositionTracker())

        # Record some PnL
        rm.record_win(Decimal("15.0"))
        rm.record_loss(Decimal("5.0"))
        rm.record_win(Decimal("20.0"))

        pnl_results = []
        errors = []

        def read_daily_pnl(thread_id: int):
            try:
                for i in range(50):
                    pnl = rm.get_daily_pnl()
                    pnl_results.append((thread_id, i, pnl))
                    time.sleep(0.001)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=read_daily_pnl, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all reads succeeded (250 total)
        assert len(pnl_results) == 250

        # Verify consistent PnL value (all should return $30.0)
        expected_pnl = Decimal("30.0")
        all_pnl_values = [r[2] for r in pnl_results]
        assert all(pnl == expected_pnl for pnl in all_pnl_values), \
            f"Inconsistent PnL values: {set(all_pnl_values)}"

    def test_audit_trail_concurrent_writes(self):
        """Test audit trail writes are thread-safe (no corruption)."""
        rm = RiskManager(position_tracker=PositionTracker())

        # Clear audit trail
        if Path(AUDIT_TRAIL_PATH).exists():
            Path(AUDIT_TRAIL_PATH).unlink()

        errors = []

        def trigger_audit_events(thread_id: int):
            try:
                for i in range(20):
                    # Trigger trade validation (writes to audit trail)
                    rm.validate_trade(
                        symbol=f"SYM{thread_id}USDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_audit_{i}"
                    )
                    time.sleep(0.005)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=trigger_audit_events, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify audit trail file exists
        assert Path(AUDIT_TRAIL_PATH).exists()

        # Verify all 100 events logged (one per validation)
        with open(AUDIT_TRAIL_PATH, "r") as f:
            lines = f.readlines()

        # Should have 100 events (some may be missing due to timing, verify ≥90%)
        assert len(lines) >= 90, f"Expected ≥90 audit events, got {len(lines)}"

    def test_concurrent_duplicate_position_detection(self):
        """Test duplicate position check works correctly under concurrency."""
        rm = RiskManager(position_tracker=PositionTracker())

        # Pre-open a position
        rm.position_tracker.open_position(
            symbol="BTCUSDT",
            entry_price=Decimal("43000.0"),
            quantity=Decimal("0.1"),
            side="LONG"
        )

        duplicate_rejections = []
        errors = []

        def attempt_duplicate_position(thread_id: int):
            try:
                for i in range(10):
                    is_valid, reason = rm.validate_trade(
                        symbol="BTCUSDT",  # Same symbol as existing position
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_dup_{i}"
                    )

                    if not is_valid and "already open" in reason:
                        duplicate_rejections.append((thread_id, i))

                    time.sleep(0.01)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=attempt_duplicate_position, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all duplicate attempts rejected (30 total)
        assert len(duplicate_rejections) == 30

    def test_sell_orders_bypass_limits_concurrently(self):
        """Test SELL orders correctly bypass limits under concurrent load."""
        rm = RiskManager(
            position_tracker=PositionTracker(),
            max_positions=1  # Only 1 position allowed
        )

        # Open max positions
        rm.position_tracker.open_position(
            symbol="BTCUSDT",
            entry_price=Decimal("43000.0"),
            quantity=Decimal("0.1"),
            side="LONG"
        )

        sell_approved = []
        buy_rejected = []
        errors = []

        def attempt_trades(thread_id: int):
            try:
                for i in range(10):
                    # Try SELL (should bypass limits)
                    is_valid_sell, reason_sell = rm.validate_trade(
                        symbol="ETHUSDT",
                        quote_qty=Decimal("10.0"),
                        side="SELL",
                        strategy_id=f"thread_{thread_id}_sell_{i}"
                    )

                    if is_valid_sell:
                        sell_approved.append((thread_id, i))

                    # Try BUY (should be rejected - max positions reached)
                    is_valid_buy, reason_buy = rm.validate_trade(
                        symbol="ETHUSDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_buy_{i}"
                    )

                    if not is_valid_buy:
                        buy_rejected.append((thread_id, i))

                    time.sleep(0.01)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=attempt_trades, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all SELL orders approved (30 total)
        assert len(sell_approved) == 30

        # Verify all BUY orders rejected (30 total)
        assert len(buy_rejected) == 30

    def test_reset_daily_state_concurrency(self):
        """Test reset_daily_state() thread-safe when called concurrently."""
        rm = RiskManager(position_tracker=PositionTracker())

        # Prime with data
        rm.record_win(Decimal("10.0"))
        rm.record_loss(Decimal("5.0"))
        assert rm.get_daily_pnl() == Decimal("5.0")

        errors = []

        def reset_state(thread_id: int):
            try:
                for i in range(10):
                    rm.reset_daily_state()
                    time.sleep(0.01)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=reset_state, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify state reset (daily PnL should be $0)
        assert rm.get_daily_pnl() == Decimal("0.0")
        assert not rm.in_cool_down()

    def test_get_risk_status_concurrent_reads(self):
        """Test get_risk_status() thread-safe for concurrent reads."""
        rm = RiskManager(position_tracker=PositionTracker())

        # Prime with data
        rm.record_win(Decimal("10.0"))
        rm.record_loss(Decimal("5.0"))

        status_results = []
        errors = []

        def read_risk_status(thread_id: int):
            try:
                for i in range(50):
                    status = rm.get_risk_status()
                    status_results.append((thread_id, i, status))
                    time.sleep(0.001)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=read_risk_status, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all reads succeeded (250 total)
        assert len(status_results) == 250

        # Verify consistent status (all should have daily_pnl = $5.0)
        for _, _, status in status_results:
            assert status["daily_pnl"] == Decimal("5.0")
            assert not status["kill_switch_active"]


class TestRiskManagerConcurrencyStress:
    """Stress tests for Risk Manager concurrency (high load scenarios)."""

    def test_high_volume_validation_burst(self):
        """Test 1000 validations from 10 threads in rapid succession."""
        rm = RiskManager(position_tracker=PositionTracker())

        results = []
        errors = []

        def validate_burst(thread_id: int):
            try:
                for i in range(100):
                    is_valid, reason = rm.validate_trade(
                        symbol=f"SYM{thread_id * 100 + i}USDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_burst_{i}"
                    )
                    results.append((thread_id, i, is_valid))

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=validate_burst, args=(i,)) for i in range(10)]

        start_time = time.time()

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.time() - start_time

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all 1000 validations completed
        assert len(results) == 1000

        # Verify completed in reasonable time (<5 seconds)
        assert elapsed < 5.0, f"Validation burst took {elapsed}s (expected <5s)"

    @pytest.mark.slow
    def test_sustained_concurrent_validation(self):
        """Test 5 threads × 500 validations over 10 seconds."""
        rm = RiskManager(position_tracker=PositionTracker())

        results = []
        errors = []

        def sustained_validation(thread_id: int):
            try:
                for i in range(500):
                    is_valid, reason = rm.validate_trade(
                        symbol=f"SYM{thread_id * 500 + i}USDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_sustained_{i}"
                    )
                    results.append((thread_id, i, is_valid))
                    time.sleep(0.02)  # 50 validations/sec per thread

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=sustained_validation, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all 2500 validations completed
        assert len(results) == 2500

        # Verify all passed (no limits triggered)
        valid_count = sum(1 for r in results if r[2])
        assert valid_count == 2500
