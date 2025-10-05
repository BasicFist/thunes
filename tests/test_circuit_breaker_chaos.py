"""
Circuit Breaker Chaos Tests

Tests thread-safety of CircuitBreaker state transitions under chaos conditions.
Sprint 1.4 - Critical path for Phase 13 rodage.

Test Categories:
1. Concurrent failure recording (10 threads × 50 calls)
2. State transition atomicity (CLOSED → OPEN)
3. Half-open state recovery
4. Concurrent reset operations
5. Multiple circuits concurrent operation
6. Listener state change notifications
"""

import pytest
import threading
import time
from unittest.mock import patch

from src.utils.circuit_breaker import (
    binance_api_breaker,
    circuit_monitor,
    CircuitBreakerMonitor,
    with_circuit_breaker,
)
from binance.exceptions import BinanceAPIException


class TestCircuitBreakerChaos:
    """Chaos testing for circuit breaker state transitions."""

    def setup_method(self):
        """Reset circuit breaker before each test."""
        binance_api_breaker.close()
        circuit_monitor.reset_all()

    def test_concurrent_failure_recording(self):
        """Test fail counter thread-safety (10 threads × 50 calls)."""
        binance_api_breaker.close()

        def api_call_failure(thread_id: int):
            for i in range(50):
                try:
                    @binance_api_breaker.call
                    def failing_call():
                        raise BinanceAPIException(
                            response=None,
                            status_code=503,
                            text="Service Unavailable"
                        )
                    failing_call()
                except Exception:
                    pass  # Expected
                time.sleep(0.001)

        threads = [threading.Thread(target=api_call_failure, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify circuit opened (after 5 consecutive failures)
        assert binance_api_breaker.current_state == "open"

        # Verify fail counter >= 5 (may be higher due to concurrent increments)
        assert binance_api_breaker.fail_counter >= 5

    def test_state_transition_atomicity(self):
        """Test CLOSED → OPEN transition is atomic (no partial states)."""
        binance_api_breaker.close()

        state_log = []
        lock = threading.Lock()

        def trigger_failure(thread_id: int):
            for i in range(10):
                try:
                    @binance_api_breaker.call
                    def fail():
                        raise BinanceAPIException(None, 503, "Fail")
                    fail()
                except Exception:
                    with lock:
                        state_log.append((thread_id, i, binance_api_breaker.current_state))
                    time.sleep(0.001)

        threads = [threading.Thread(target=trigger_failure, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify only valid states (no corrupted/partial states)
        valid_states = {"closed", "open", "half-open"}
        invalid_states = [s for _, _, s in state_log if s not in valid_states]

        assert len(invalid_states) == 0, f"Invalid states detected: {invalid_states}"

        # Verify state eventually transitioned to OPEN
        final_states = [s for _, _, s in state_log[-10:]]  # Last 10 observations
        assert "open" in final_states

    def test_reset_during_half_open(self):
        """Test manual reset() call during HALF_OPEN state is thread-safe."""
        binance_api_breaker.close()

        # Trip to OPEN
        for _ in range(6):
            try:
                @binance_api_breaker.call
                def fail():
                    raise BinanceAPIException(None, 503, "Fail")
                fail()
            except:
                pass

        assert binance_api_breaker.current_state == "open"

        # Manually force HALF_OPEN (simulate timeout elapsed)
        binance_api_breaker._state = "half-open"

        # Concurrent reset calls
        errors = []

        def reset_circuit(thread_id: int):
            try:
                for i in range(10):
                    circuit_monitor.reset_all()
                    time.sleep(0.01)
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=reset_circuit, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors during reset: {errors}"

        # Verify transitioned to CLOSED
        assert binance_api_breaker.current_state == "closed"
        assert binance_api_breaker.fail_counter == 0

    def test_concurrent_is_open_checks(self):
        """Test concurrent circuit_monitor.is_open() calls are thread-safe."""
        binance_api_breaker.close()

        # Trip circuit to OPEN
        for _ in range(6):
            try:
                @binance_api_breaker.call
                def fail():
                    raise BinanceAPIException(None, 503, "Fail")
                fail()
            except:
                pass

        assert binance_api_breaker.current_state == "open"

        is_open_results = []
        errors = []

        def check_is_open(thread_id: int):
            try:
                for i in range(50):
                    is_open = circuit_monitor.is_open("binance_api")
                    is_open_results.append((thread_id, i, is_open))
                    time.sleep(0.001)
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=check_is_open, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all reads succeeded (250 total)
        assert len(is_open_results) == 250

        # Verify all reads returned True (circuit is OPEN)
        assert all(result[2] for result in is_open_results)

    def test_concurrent_reset_all(self):
        """Test circuit_monitor.reset_all() thread-safe under concurrent calls."""
        # Trip multiple circuits (if multiple exist, else just binance_api)
        binance_api_breaker.close()

        for _ in range(6):
            try:
                @binance_api_breaker.call
                def fail():
                    raise BinanceAPIException(None, 503, "Fail")
                fail()
            except:
                pass

        assert binance_api_breaker.current_state == "open"

        errors = []

        def reset_all_circuits(thread_id: int):
            try:
                for i in range(20):
                    circuit_monitor.reset_all()
                    time.sleep(0.01)
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=reset_all_circuits, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all circuits closed
        assert binance_api_breaker.current_state == "closed"
        assert binance_api_breaker.fail_counter == 0

    def test_half_open_success_recovery(self):
        """Test HALF_OPEN → CLOSED transition on successful call."""
        binance_api_breaker.close()

        # Trip to OPEN
        for _ in range(6):
            try:
                @binance_api_breaker.call
                def fail():
                    raise BinanceAPIException(None, 503, "Fail")
                fail()
            except:
                pass

        assert binance_api_breaker.current_state == "open"

        # Force HALF_OPEN
        binance_api_breaker._state = "half-open"

        # Successful call should transition to CLOSED
        @binance_api_breaker.call
        def success():
            return "OK"

        result = success()

        assert result == "OK"
        assert binance_api_breaker.current_state == "closed"
        assert binance_api_breaker.fail_counter == 0

    def test_half_open_failure_reopen(self):
        """Test HALF_OPEN → OPEN transition on failed call."""
        binance_api_breaker.close()

        # Trip to OPEN
        for _ in range(6):
            try:
                @binance_api_breaker.call
                def fail():
                    raise BinanceAPIException(None, 503, "Fail")
                fail()
            except:
                pass

        assert binance_api_breaker.current_state == "open"

        # Force HALF_OPEN
        binance_api_breaker._state = "half-open"

        # Failed call should re-open circuit
        try:
            @binance_api_breaker.call
            def fail_again():
                raise BinanceAPIException(None, 503, "Fail Again")
            fail_again()
        except:
            pass

        # Verify circuit re-opened
        assert binance_api_breaker.current_state == "open"

    def test_circuit_monitor_get_status_concurrent(self):
        """Test circuit_monitor.get_status() thread-safe for concurrent reads."""
        binance_api_breaker.close()

        # Trip circuit
        for _ in range(6):
            try:
                @binance_api_breaker.call
                def fail():
                    raise BinanceAPIException(None, 503, "Fail")
                fail()
            except:
                pass

        status_results = []
        errors = []

        def read_status(thread_id: int):
            try:
                for i in range(50):
                    status = circuit_monitor.get_status()
                    status_results.append((thread_id, i, status))
                    time.sleep(0.001)
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=read_status, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all reads succeeded (250 total)
        assert len(status_results) == 250

        # Verify all status dicts contain binance_api circuit
        for _, _, status in status_results:
            assert "binance_api" in status
            assert status["binance_api"]["state"] == "open"

    def test_listener_state_change_concurrent(self):
        """Test circuit breaker state change listeners thread-safe."""
        binance_api_breaker.close()

        state_changes = []
        lock = threading.Lock()

        def state_listener(circuit_breaker, old_state, new_state):
            with lock:
                state_changes.append((old_state, new_state, time.time()))

        # Add listener
        binance_api_breaker.add_listener(state_listener)

        def trigger_state_changes(thread_id: int):
            for i in range(5):
                try:
                    @binance_api_breaker.call
                    def fail():
                        raise BinanceAPIException(None, 503, "Fail")
                    fail()
                except:
                    pass
                time.sleep(0.01)

        threads = [threading.Thread(target=trigger_state_changes, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify state change notifications recorded
        assert len(state_changes) > 0

        # Verify at least one CLOSED → OPEN transition
        transitions = [(old, new) for old, new, _ in state_changes]
        assert ("closed", "open") in transitions

    def test_mixed_success_failure_concurrent(self):
        """Test circuit behavior with mixed success/failure under concurrent load."""
        binance_api_breaker.close()

        results = []
        errors = []
        lock = threading.Lock()

        def mixed_calls(thread_id: int):
            try:
                for i in range(20):
                    # Alternate success/failure
                    if i % 2 == 0:
                        # Success call
                        @binance_api_breaker.call
                        def success():
                            return "OK"
                        result = success()
                        with lock:
                            results.append((thread_id, i, "success", binance_api_breaker.current_state))
                    else:
                        # Failure call
                        try:
                            @binance_api_breaker.call
                            def fail():
                                raise BinanceAPIException(None, 503, "Fail")
                            fail()
                        except:
                            with lock:
                                results.append((thread_id, i, "failure", binance_api_breaker.current_state))

                    time.sleep(0.01)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=mixed_calls, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify both success and failure calls recorded
        successes = [r for r in results if r[2] == "success"]
        failures = [r for r in results if r[2] == "failure"]

        assert len(successes) > 0
        assert len(failures) > 0

    def test_circuit_breaker_decorator_concurrent(self):
        """Test @with_circuit_breaker decorator thread-safe."""
        binance_api_breaker.close()

        results = []
        errors = []
        lock = threading.Lock()

        @with_circuit_breaker()
        def api_call_with_decorator(should_fail: bool):
            if should_fail:
                raise BinanceAPIException(None, 503, "Decorated Fail")
            return "OK"

        def call_decorated_function(thread_id: int):
            try:
                for i in range(10):
                    # Alternate success/failure
                    should_fail = (i % 3 == 0)  # Fail every 3rd call

                    try:
                        result = api_call_with_decorator(should_fail)
                        with lock:
                            results.append((thread_id, i, "success", result))
                    except Exception:
                        with lock:
                            results.append((thread_id, i, "failure", None))

                    time.sleep(0.01)

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=call_decorated_function, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no unexpected exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify both success and failure calls recorded
        successes = [r for r in results if r[2] == "success"]
        failures = [r for r in results if r[2] == "failure"]

        assert len(successes) > 0
        assert len(failures) > 0


class TestCircuitBreakerConcurrencyStress:
    """Stress tests for circuit breaker concurrency (high load scenarios)."""

    def setup_method(self):
        """Reset circuit breaker before each test."""
        binance_api_breaker.close()
        circuit_monitor.reset_all()

    def test_high_volume_concurrent_failures(self):
        """Test 1000 failures from 10 threads in rapid succession."""
        binance_api_breaker.close()

        errors = []

        def rapid_failures(thread_id: int):
            try:
                for i in range(100):
                    try:
                        @binance_api_breaker.call
                        def fail():
                            raise BinanceAPIException(None, 503, "Rapid Fail")
                        fail()
                    except:
                        pass  # Expected

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=rapid_failures, args=(i,)) for i in range(10)]

        start_time = time.time()

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.time() - start_time

        # Verify no unexpected exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify circuit opened
        assert binance_api_breaker.current_state == "open"

        # Verify completed quickly (<2 seconds)
        assert elapsed < 2.0, f"High-volume test took {elapsed}s (expected <2s)"

    @pytest.mark.slow
    def test_sustained_concurrent_load(self):
        """Test 5 threads × 200 calls over 10 seconds."""
        binance_api_breaker.close()

        results = []
        errors = []
        lock = threading.Lock()

        def sustained_load(thread_id: int):
            try:
                for i in range(200):
                    # Mix of success (75%) and failure (25%)
                    should_fail = (i % 4 == 0)

                    try:
                        @binance_api_breaker.call
                        def api_call():
                            if should_fail:
                                raise BinanceAPIException(None, 503, "Sustained Fail")
                            return "OK"

                        result = api_call()

                        with lock:
                            results.append((thread_id, i, "success"))

                    except Exception:
                        with lock:
                            results.append((thread_id, i, "failure"))

                    time.sleep(0.05)  # 20 calls/sec per thread = 100 calls/sec total

            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=sustained_load, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no unexpected exceptions
        assert len(errors) == 0, f"Errors: {errors}"

        # Verify all 1000 calls processed
        assert len(results) == 1000

        # Verify mix of success and failure
        successes = [r for r in results if r[2] == "success"]
        failures = [r for r in results if r[2] == "failure"]

        assert len(successes) > 0
        assert len(failures) > 0

    def test_reset_under_continuous_load(self):
        """Test reset_all() while continuous failures are happening."""
        binance_api_breaker.close()

        stop_flag = threading.Event()
        errors = []

        def continuous_failures():
            while not stop_flag.is_set():
                try:
                    @binance_api_breaker.call
                    def fail():
                        raise BinanceAPIException(None, 503, "Continuous Fail")
                    fail()
                except:
                    pass
                time.sleep(0.01)

        def continuous_resets(thread_id: int):
            try:
                for i in range(20):
                    circuit_monitor.reset_all()
                    time.sleep(0.1)
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start continuous failure thread
        failure_thread = threading.Thread(target=continuous_failures)
        failure_thread.start()

        # Wait for circuit to open
        time.sleep(0.5)

        # Start reset threads
        reset_threads = [threading.Thread(target=continuous_resets, args=(i,)) for i in range(3)]

        for t in reset_threads:
            t.start()
        for t in reset_threads:
            t.join()

        # Stop failure thread
        stop_flag.set()
        failure_thread.join(timeout=2.0)

        # Verify no exceptions during concurrent reset
        assert len(errors) == 0, f"Errors during reset under load: {errors}"

        # Verify circuit eventually closed (after final reset)
        circuit_monitor.reset_all()
        assert binance_api_breaker.current_state == "closed"
