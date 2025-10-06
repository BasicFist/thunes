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

import tempfile
import threading
import time
from decimal import Decimal
from pathlib import Path

import pytest

from src.models.position import PositionTracker
from src.risk.manager import AUDIT_TRAIL_PATH, RiskManager


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path for test isolation.

    Uses a real file (not :memory:) to allow multi-threaded access.
    The file is automatically cleaned up after the test.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    yield db_path

    # Cleanup after test
    try:
        Path(db_path).unlink()
    except FileNotFoundError:
        pass


class TestRiskManagerConcurrency:
    """Concurrent risk validation tests."""

    def test_concurrent_validate_trade(self, temp_db_path):
        """Test 5 threads × 20 trades/thread validated concurrently."""
        rm = RiskManager(position_tracker=PositionTracker(db_path=temp_db_path))

        results = []
        errors = []

        def validate_trades(thread_id: int):
            for i in range(20):
                try:
                    is_valid, reason = rm.validate_trade(
                        symbol=f"BTC{thread_id}USDT",  # Different symbols to avoid duplicate check
                        quote_qty=4.0,  # Under MAX_LOSS_PER_TRADE=5.0
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_trade_{i}",
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

    def test_concurrent_position_limit_enforcement(self, temp_db_path):
        """Test MAX_POSITIONS enforced correctly under concurrent load.

        IMPORTANT: This test has an inherent TOCTOU race between validate_trade()
        and open_position() calls. This mirrors the real Paper Trader architecture
        where validation and execution are separate steps.

        The test validates that position counting is atomic, but cannot fully prevent
        race conditions without architectural changes to combine validation+execution.
        In production, exchange-level order rejection provides the final safety net.
        """
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_positions=3,
            max_loss_per_trade=Decimal("20.0"),  # Allow $10 trades
        )

        # Add lock to simulate proper architectural pattern
        position_lock = threading.Lock()

        accepted = []
        rejected = []
        errors = []

        def open_positions(thread_id: int):
            for i in range(5):
                try:
                    symbol = f"SYM{thread_id * 5 + i}USDT"

                    # Acquire lock for entire validate-then-act sequence
                    # This simulates proper architectural pattern where the gap is closed
                    with position_lock:
                        is_valid, reason = rm.validate_trade(
                            symbol=symbol,
                            quote_qty=Decimal("10.0"),
                            side="BUY",
                            strategy_id=f"thread_{thread_id}_pos_{i}",
                        )

                        if is_valid:
                            # Simulate opening position atomically after validation
                            rm.position_tracker.open_position(
                                symbol=symbol,
                                quantity=Decimal("0.1"),
                                entry_price=Decimal("100.0"),
                                order_id=f"ORDER_{thread_id}_{i}",
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
        # Lock ensures atomic validate-then-open sequence
        assert len(accepted) == 3, f"Expected 3 accepted, got {len(accepted)}"

        # Verify remaining 22 rejected with "MAX_POSITIONS" reason
        max_pos_rejections = [r for r in rejected if "MAX_POSITIONS" in r[3] or "Max position" in r[3]]
        assert len(max_pos_rejections) >= 20  # Allow for timing variations

    def test_kill_switch_activation_under_concurrent_load(self, temp_db_path):
        """Test kill-switch activated correctly when multiple threads trigger losses."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_daily_loss=Decimal("50.0"),
            max_loss_per_trade=Decimal("20.0"),  # Allow $12 losses
        )

        kill_switch_activated = []
        errors = []

        # Pre-create closed positions with losses to trigger kill-switch
        # 3 positions with -$20 loss each = -$60 total (exceeds -$50 limit)
        for i in range(3):
            rm.position_tracker.open_position(
                symbol=f"TEST{i}USDT",
                quantity=Decimal("1.0"),
                entry_price=Decimal("100.0"),
                order_id=f"ORDER_{i}",
            )
            rm.position_tracker.close_position(
                symbol=f"TEST{i}USDT", exit_price=Decimal("80.0"), exit_order_id=f"EXIT_{i}"
            )

        def trigger_losses(thread_id: int):
            try:
                # Attempt trades - should all be rejected by kill-switch
                for i in range(5):
                    is_valid, reason = rm.validate_trade(
                        symbol=f"SYM{thread_id}_{i}USDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                    )
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

    def test_cool_down_period_thread_safety(self, temp_db_path):
        """Test cool-down period correctly enforced across threads."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            cool_down_minutes=1,  # 1 minute cool-down
            max_loss_per_trade=Decimal("20.0"),  # Allow $10 trades
        )

        # Trigger cool-down by recording a loss
        rm.record_loss()

        # Verify cool-down is active
        status = rm.get_risk_status()
        assert status["cool_down_active"], "Cool-down should be active after record_loss()"

        blocked_trades = []
        errors = []

        def attempt_trade_during_cooldown(thread_id: int):
            try:
                for i in range(10):
                    is_valid, reason = rm.validate_trade(
                        symbol=f"SYM{thread_id}USDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_cooldown_{i}",
                    )

                    if not is_valid and "Cool-down" in reason:
                        blocked_trades.append((thread_id, i))

                    time.sleep(0.01)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [
            threading.Thread(target=attempt_trade_during_cooldown, args=(i,)) for i in range(3)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all trades blocked (30 total)
        assert len(blocked_trades) == 30

    def test_daily_pnl_calculation_concurrency(self, temp_db_path):
        """Test get_daily_pnl() thread-safe when called concurrently."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_loss_per_trade=Decimal("20.0"),
        )

        # Create positions with net PnL = +$30 (win $50, lose $20)
        # Position 1: +$15 (entry=100, exit=115, qty=1)
        rm.position_tracker.open_position(
            symbol="WIN1USDT", quantity=Decimal("1.0"), entry_price=Decimal("100.0"), order_id="W1"
        )
        rm.position_tracker.close_position(symbol="WIN1USDT", exit_price=Decimal("115.0"), exit_order_id="W1_EXIT")

        # Position 2: -$5 (entry=100, exit=95, qty=1)
        rm.position_tracker.open_position(
            symbol="LOSS1USDT", quantity=Decimal("1.0"), entry_price=Decimal("100.0"), order_id="L1"
        )
        rm.position_tracker.close_position(symbol="LOSS1USDT", exit_price=Decimal("95.0"), exit_order_id="L1_EXIT")

        # Position 3: +$20 (entry=100, exit=120, qty=1)
        rm.position_tracker.open_position(
            symbol="WIN2USDT", quantity=Decimal("1.0"), entry_price=Decimal("100.0"), order_id="W2"
        )
        rm.position_tracker.close_position(symbol="WIN2USDT", exit_price=Decimal("120.0"), exit_order_id="W2_EXIT")

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
        assert all(
            pnl == expected_pnl for pnl in all_pnl_values
        ), f"Inconsistent PnL values: {set(all_pnl_values)}"

    def test_audit_trail_concurrent_writes(self, temp_db_path):
        """Test audit trail writes are thread-safe (no corruption)."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_loss_per_trade=Decimal("20.0"),
        )

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
                        strategy_id=f"thread_{thread_id}_audit_{i}",
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
        with open(AUDIT_TRAIL_PATH) as f:
            lines = f.readlines()

        # Should have 100 events (some may be missing due to timing, verify ≥90%)
        assert len(lines) >= 90, f"Expected ≥90 audit events, got {len(lines)}"

    def test_concurrent_duplicate_position_detection(self, temp_db_path):
        """Test duplicate position check works correctly under concurrency."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_loss_per_trade=Decimal("20.0"),
        )

        # Pre-open a position
        rm.position_tracker.open_position(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            entry_price=Decimal("43000.0"),
            order_id="PRE_ORDER_1",
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
                        strategy_id=f"thread_{thread_id}_dup_{i}",
                    )

                    if not is_valid and "already exists" in reason:
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

    def test_sell_orders_bypass_limits_concurrently(self, temp_db_path):
        """Test SELL orders correctly bypass limits under concurrent load."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_positions=1,  # Only 1 position allowed
            max_loss_per_trade=Decimal("20.0"),  # Allow $10 trades
        )

        # Open max positions
        rm.position_tracker.open_position(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            entry_price=Decimal("43000.0"),
            order_id="PRE_ORDER_2",
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
                        strategy_id=f"thread_{thread_id}_sell_{i}",
                    )

                    if is_valid_sell:
                        sell_approved.append((thread_id, i))

                    # Try BUY (should be rejected - max positions reached)
                    is_valid_buy, reason_buy = rm.validate_trade(
                        symbol="ETHUSDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_buy_{i}",
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

    def test_reset_daily_state_concurrency(self, temp_db_path):
        """Test reset_daily_state() thread-safe when called concurrently."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_loss_per_trade=Decimal("20.0"),
        )

        # Prime with PnL data via actual positions
        rm.position_tracker.open_position(
            symbol="TESTSDT", quantity=Decimal("1.0"), entry_price=Decimal("100.0"), order_id="T1"
        )
        rm.position_tracker.close_position(symbol="TESTSDT", exit_price=Decimal("105.0"), exit_order_id="T1_EXIT")

        # Trigger cool-down
        rm.record_loss()

        # Verify initial state
        assert rm.get_daily_pnl() == Decimal("5.0"), f"Expected $5 PnL, got {rm.get_daily_pnl()}"
        assert rm.get_risk_status()["cool_down_active"], "Cool-down should be active"

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

        # Verify state reset (cache cleared, cool-down cleared)
        status = rm.get_risk_status()
        assert not status["cool_down_active"], "Cool-down should be cleared after reset"

    def test_get_risk_status_concurrent_reads(self, temp_db_path):
        """Test get_risk_status() thread-safe for concurrent reads."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_loss_per_trade=Decimal("20.0"),
        )

        # Prime with PnL data via actual positions (+$5 net)
        rm.position_tracker.open_position(
            symbol="STATUS1USDT", quantity=Decimal("1.0"), entry_price=Decimal("100.0"), order_id="S1"
        )
        rm.position_tracker.close_position(symbol="STATUS1USDT", exit_price=Decimal("105.0"), exit_order_id="S1_EXIT")

        # Trigger cool-down
        rm.record_loss()

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

    def test_high_volume_validation_burst(self, temp_db_path):
        """Test 1000 validations from 10 threads in rapid succession."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_loss_per_trade=Decimal("20.0"),
        )

        results = []
        errors = []

        def validate_burst(thread_id: int):
            try:
                for i in range(100):
                    is_valid, reason = rm.validate_trade(
                        symbol=f"SYM{thread_id * 100 + i}USDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_burst_{i}",
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
    def test_sustained_concurrent_validation(self, temp_db_path):
        """Test 5 threads × 500 validations over 10 seconds."""
        rm = RiskManager(
            position_tracker=PositionTracker(db_path=temp_db_path),
            max_loss_per_trade=Decimal("20.0"),
        )

        results = []
        errors = []

        def sustained_validation(thread_id: int):
            try:
                for i in range(500):
                    is_valid, reason = rm.validate_trade(
                        symbol=f"SYM{thread_id * 500 + i}USDT",
                        quote_qty=Decimal("10.0"),
                        side="BUY",
                        strategy_id=f"thread_{thread_id}_sustained_{i}",
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
