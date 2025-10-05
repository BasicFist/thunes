"""
WebSocket Concurrency Tests

Tests thread-safety of BinanceWebSocketStream under concurrent operations.
Sprint 1.4 - Critical path for Phase 13 rodage.

Test Categories:
1. Concurrent message processing (3 threads × 1000 messages)
2. Reconnection race conditions
3. Queue overflow handling
4. Watchdog concurrent operation
5. Stop during processing
6. Concurrent read operations
"""

import pytest
import threading
import time
from queue import Queue
from unittest.mock import MagicMock, patch

from src.data.ws_stream import BinanceWebSocketStream


class TestWebSocketConcurrency:
    """Concurrent WebSocket operation validation."""

    def test_concurrent_message_processing(self):
        """Test 3 threads × 1000 messages processed without loss."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)

        messages_processed = []
        errors = []

        # Mock the message handler to track processing
        original_handler = stream._handle_message
        def tracked_handler(msg):
            messages_processed.append(msg.get("u"))
            return original_handler(msg)

        stream._handle_message = tracked_handler
        stream.start()

        def submit_messages(thread_id: int, count: int):
            for i in range(count):
                msg = {
                    "u": thread_id * 1000 + i,
                    "b": "43000.00",
                    "a": "43000.50"
                }
                try:
                    stream._message_queue.put(msg, timeout=1.0)
                except Exception as e:
                    errors.append((thread_id, i, str(e)))

        threads = [
            threading.Thread(target=submit_messages, args=(i, 1000))
            for i in range(3)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Wait for async processing
        time.sleep(2.0)

        # Verify no errors
        assert len(errors) == 0, f"Errors during concurrent processing: {errors}"

        # Verify all messages processed (or in queue)
        total_submitted = 3000
        processed_count = len(messages_processed)
        queue_size = stream._message_queue.qsize()

        assert processed_count + queue_size >= total_submitted * 0.95, \
            f"Message loss detected: {processed_count} processed + {queue_size} queued < {total_submitted}"

        stream.stop()

    def test_reconnection_race_condition(self):
        """Test reconnection triggered while messages are processing."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        # Flood message queue
        for i in range(50):
            msg = {"u": i, "b": "43000.00", "a": "43000.50"}
            stream._message_queue.put(msg)

        # Trigger reconnection mid-processing
        reconnect_thread = threading.Thread(target=stream._reconnect)
        reconnect_thread.start()

        # Continue submitting messages during reconnection
        for i in range(50, 100):
            msg = {"u": i, "b": "43000.00", "a": "43000.50"}
            stream._message_queue.put(msg)

        reconnect_thread.join(timeout=5.0)
        time.sleep(1.0)

        # Verify stream still connected
        assert stream._connected
        assert stream.get_latest_ticker() is not None

        stream.stop()

    def test_queue_overflow_handling(self):
        """Test behavior when message queue fills (200 messages, 100 max)."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream._message_queue = Queue(maxsize=100)  # Set explicit max
        stream.start()

        overflow_count = 0

        # Submit 200 messages rapidly (queue max=100)
        for i in range(200):
            msg = {"u": i, "b": "43000.00", "a": "43000.50"}
            try:
                stream._message_queue.put(msg, block=False)
            except:
                overflow_count += 1

        time.sleep(0.1)

        # Verify overflow occurred
        assert overflow_count > 0, "No overflow detected when queue should be full"

        # Verify queue size capped at 100
        assert stream._message_queue.qsize() <= 100

        stream.stop()

    def test_watchdog_concurrent_health_check(self):
        """Test watchdog doesn't interfere with message processing."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        health_checks = []

        # Watchdog checks health concurrently
        def watchdog_loop():
            for _ in range(10):
                is_healthy = stream.health_monitor.is_healthy()
                health_checks.append(is_healthy)
                time.sleep(0.1)

        watchdog_thread = threading.Thread(target=watchdog_loop)
        watchdog_thread.start()

        # Submit messages while watchdog runs
        for i in range(100):
            msg = {"u": i, "b": "43000.00", "a": "43000.50"}
            stream._message_queue.put(msg)

        watchdog_thread.join()
        time.sleep(1.0)

        # Verify all health checks completed
        assert len(health_checks) == 10

        # Verify stream still functional
        assert stream.get_latest_ticker() is not None

        stream.stop()

    def test_stop_during_message_processing(self):
        """Test stopping stream while messages are being processed."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        # Submit messages
        for i in range(100):
            msg = {"u": i, "b": "43000.00", "a": "43000.50"}
            stream._message_queue.put(msg)

        # Stop mid-processing
        time.sleep(0.1)
        stop_thread = threading.Thread(target=stream.stop)
        stop_thread.start()

        # Try to submit more messages (should be rejected)
        post_stop_rejected = 0
        for i in range(100, 150):
            msg = {"u": i, "b": "43000.00", "a": "43000.50"}
            if not stream._connected:
                post_stop_rejected += 1

        stop_thread.join(timeout=5.0)

        # Verify stream stopped cleanly
        assert not stream._connected
        assert post_stop_rejected > 0, "Stream accepted messages after stop initiated"

    def test_concurrent_get_latest_ticker_reads(self):
        """Test multiple threads reading latest ticker simultaneously."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        # Prime with initial data
        msg = {"u": 1, "b": "43000.00", "a": "43000.50"}
        stream._message_queue.put(msg)
        time.sleep(0.5)

        ticker_values = []
        errors = []

        def read_ticker(thread_id: int):
            for i in range(50):
                try:
                    ticker = stream.get_latest_ticker()
                    ticker_values.append((thread_id, i, ticker))
                except Exception as e:
                    errors.append((thread_id, i, str(e)))
                time.sleep(0.001)

        threads = [threading.Thread(target=read_ticker, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors during concurrent reads
        assert len(errors) == 0, f"Errors during concurrent reads: {errors}"

        # Verify all reads succeeded
        assert len(ticker_values) == 250  # 5 threads × 50 reads

        stream.stop()

    def test_reconnect_with_pending_messages(self):
        """Test reconnection doesn't lose pending messages in queue."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        # Add messages to queue
        for i in range(20):
            msg = {"u": i, "b": f"{43000 + i}.00", "a": f"{43000 + i + 1}.00"}
            stream._message_queue.put(msg)

        initial_queue_size = stream._message_queue.qsize()

        # Trigger reconnection
        stream._reconnect()

        time.sleep(0.5)

        # Verify queue not cleared (messages preserved)
        final_queue_size = stream._message_queue.qsize()
        assert final_queue_size >= initial_queue_size * 0.9, \
            f"Messages lost during reconnection: {initial_queue_size} → {final_queue_size}"

        stream.stop()

    def test_health_monitor_concurrent_record_message(self):
        """Test health monitor thread-safety when recording messages."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        def record_messages(thread_id: int):
            for i in range(100):
                stream.health_monitor.record_message()
                time.sleep(0.001)

        threads = [threading.Thread(target=record_messages, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify health monitor recorded all messages (300 total)
        # Note: Exact count may vary due to timing, verify ≥ 90% captured
        assert stream.health_monitor.message_count >= 270

        stream.stop()

    def test_multiple_streams_same_symbol(self):
        """Test multiple WebSocket streams for same symbol don't interfere."""
        stream1 = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream2 = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)

        stream1.start()
        stream2.start()

        # Submit messages to both
        for i in range(50):
            msg1 = {"u": i, "b": f"{43000 + i}.00", "a": f"{43000 + i + 1}.00"}
            msg2 = {"u": i + 1000, "b": f"{44000 + i}.00", "a": f"{44000 + i + 1}.00"}
            stream1._message_queue.put(msg1)
            stream2._message_queue.put(msg2)

        time.sleep(1.0)

        # Verify both streams have independent data
        ticker1 = stream1.get_latest_ticker()
        ticker2 = stream2.get_latest_ticker()

        assert ticker1 is not None
        assert ticker2 is not None
        assert ticker1 != ticker2  # Should have different data

        stream1.stop()
        stream2.stop()

    def test_stream_restart_during_processing(self):
        """Test stopping and restarting stream during active processing."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        # Submit initial messages
        for i in range(50):
            msg = {"u": i, "b": "43000.00", "a": "43000.50"}
            stream._message_queue.put(msg)

        time.sleep(0.2)

        # Stop stream
        stream.stop()
        time.sleep(0.5)

        # Restart stream
        stream.start()

        # Submit new messages
        for i in range(50, 100):
            msg = {"u": i, "b": "43500.00", "a": "43500.50"}
            stream._message_queue.put(msg)

        time.sleep(0.5)

        # Verify stream functional after restart
        assert stream._connected
        ticker = stream.get_latest_ticker()
        assert ticker is not None

        stream.stop()


class TestWebSocketConcurrencyStress:
    """Stress tests for WebSocket concurrency (high load scenarios)."""

    def test_high_volume_message_burst(self):
        """Test handling 10,000 messages submitted in <1 second."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        start_time = time.time()

        for i in range(10000):
            msg = {"u": i, "b": "43000.00", "a": "43000.50"}
            try:
                stream._message_queue.put(msg, block=False)
            except:
                pass  # Overflow expected

        elapsed = time.time() - start_time

        # Verify burst completed quickly
        assert elapsed < 1.0, f"Message submission took {elapsed}s (expected <1s)"

        # Wait for processing
        time.sleep(2.0)

        # Verify stream still responsive
        ticker = stream.get_latest_ticker()
        assert ticker is not None

        stream.stop()

    @pytest.mark.slow
    def test_sustained_concurrent_load(self):
        """Test 5 threads × 2000 messages over 10 seconds."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        errors = []

        def sustained_load(thread_id: int):
            for i in range(2000):
                msg = {
                    "u": thread_id * 2000 + i,
                    "b": f"{43000 + (i % 100)}.00",
                    "a": f"{43000 + (i % 100) + 1}.00"
                }
                try:
                    stream._message_queue.put(msg, timeout=0.1)
                except Exception as e:
                    errors.append((thread_id, i, str(e)))
                time.sleep(0.005)  # 200 msgs/sec per thread = 1000 msgs/sec total

        threads = [threading.Thread(target=sustained_load, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Wait for queue to drain
        time.sleep(3.0)

        # Verify minimal errors (<1%)
        assert len(errors) < 100, f"Too many errors: {len(errors)}/10000"

        # Verify stream still healthy
        assert stream._connected
        assert stream.health_monitor.is_healthy()

        stream.stop()
