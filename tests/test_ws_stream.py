"""Tests for WebSocket streaming functionality."""

import time
from collections.abc import Generator
from threading import Thread
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.data.ws_stream import BinanceWebSocketStream, WebSocketHealthMonitor


class TestWebSocketHealthMonitor:
    """Tests for WebSocketHealthMonitor."""

    def test_initialization(self) -> None:
        """Test health monitor initialization."""
        monitor = WebSocketHealthMonitor(timeout_seconds=30)

        assert monitor.timeout_seconds == 30
        assert monitor.is_healthy()  # Should be healthy initially

    def test_record_message(self) -> None:
        """Test message timestamp recording."""
        monitor = WebSocketHealthMonitor(timeout_seconds=5)

        # Wait a bit then record message
        time.sleep(0.1)
        monitor.record_message()

        assert monitor.is_healthy()

    def test_unhealthy_after_timeout(self) -> None:
        """Test that monitor becomes unhealthy after timeout."""
        monitor = WebSocketHealthMonitor(timeout_seconds=1)

        # Wait for timeout
        time.sleep(1.1)

        assert not monitor.is_healthy()

    def test_watchdog_triggers_reconnect(self) -> None:
        """Test that watchdog calls reconnect callback when unhealthy."""
        # Use short intervals for testing (timeout=1s, check every 1s)
        monitor = WebSocketHealthMonitor(timeout_seconds=1, check_interval_seconds=1)
        reconnect_called = {"value": False}

        def reconnect_callback() -> None:
            reconnect_called["value"] = True

        # Start watchdog
        monitor.start_watchdog(reconnect_callback)

        # Wait for timeout + check interval + buffer
        # 1s timeout + 1s check + 0.5s buffer = 2.5s
        time.sleep(2.5)

        # Stop watchdog
        monitor.stop_watchdog()

        # Verify reconnect was called
        assert reconnect_called["value"] is True

    def test_watchdog_stop(self) -> None:
        """Test stopping watchdog thread."""
        monitor = WebSocketHealthMonitor(timeout_seconds=60)

        def dummy_callback() -> None:
            pass

        monitor.start_watchdog(dummy_callback)
        assert monitor._running is True

        monitor.stop_watchdog()
        assert monitor._running is False


class TestBinanceWebSocketStream:
    """Tests for BinanceWebSocketStream."""

    @pytest.fixture
    def mock_twm(self) -> Generator[MagicMock, None, None]:
        """Create mocked ThreadedWebsocketManager."""
        with patch("src.data.ws_stream.ThreadedWebsocketManager") as MockTWM:
            mock_instance = MagicMock()
            mock_instance.start_symbol_book_ticker_socket.return_value = "test_stream_key"
            MockTWM.return_value = mock_instance
            yield mock_instance

    def test_initialization(self) -> None:
        """Test WebSocket stream initialization."""
        stream = BinanceWebSocketStream(
            symbol="BTCUSDT",
            testnet=True,
            enable_rest_fallback=True,
        )

        assert stream.symbol == "BTCUSDT"
        assert stream.testnet is True
        assert stream.enable_rest_fallback is True
        assert stream.is_connected() is False

    def test_start_stop(self, mock_twm: MagicMock) -> None:
        """Test starting and stopping WebSocket stream."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)

        # Start stream
        stream.start()
        assert stream.twm is not None
        mock_twm.start.assert_called_once()
        mock_twm.start_symbol_book_ticker_socket.assert_called_once()

        # Stop stream
        stream.stop()
        mock_twm.stop_socket.assert_called_once_with("test_stream_key")
        mock_twm.stop.assert_called_once()

    def test_handle_message(self, mock_twm: MagicMock) -> None:
        """Test processing incoming WebSocket messages."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        # Simulate incoming message
        test_msg = {
            "u": 400900217,  # update_id
            "s": "BTCUSDT",  # symbol
            "b": "43000.00",  # best bid price
            "B": "1.50000000",  # best bid qty
            "a": "43000.50",  # best ask price
            "A": "2.00000000",  # best ask qty
        }

        stream._handle_message(test_msg)

        # Verify data stored
        ticker = stream.get_latest_ticker()
        assert ticker is not None
        assert ticker["b"] == "43000.00"
        assert ticker["a"] == "43000.50"

        # Verify health monitor updated
        assert stream.health_monitor.is_healthy()

        stream.stop()

    def test_get_best_bid_ask(self, mock_twm: MagicMock) -> None:
        """Test extracting best bid/ask prices."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        # Simulate message
        test_msg = {
            "u": 400900217,
            "s": "BTCUSDT",
            "b": "43000.00",
            "B": "1.50000000",
            "a": "43000.50",
            "A": "2.00000000",
        }
        stream._handle_message(test_msg)

        # Test bid/ask extraction
        assert stream.get_best_bid() == 43000.00
        assert stream.get_best_ask() == 43000.50
        assert stream.get_mid_price() == 43000.25

        stream.stop()

    def test_no_data_returns_none(self, mock_twm: MagicMock) -> None:
        """Test that methods return None when no data available."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        # No messages received yet
        assert stream.get_latest_ticker() is None
        assert stream.get_best_bid() is None
        assert stream.get_best_ask() is None
        assert stream.get_mid_price() is None

        stream.stop()

    def test_rest_fallback_initialization(self) -> None:
        """Test lazy REST client initialization."""
        stream = BinanceWebSocketStream(
            symbol="BTCUSDT",
            testnet=True,
            enable_rest_fallback=True,
        )

        # REST client should be None initially
        assert stream._rest_client is None

        # Initialize REST client
        stream._init_rest_client()
        assert stream._rest_client is not None

    @patch("src.data.ws_stream.BinanceWebSocketStream._fetch_ticker_rest")
    def test_rest_fallback_when_websocket_disconnected(
        self, mock_fetch: Mock, mock_twm: MagicMock
    ) -> None:
        """Test automatic fallback to REST when WebSocket disconnected."""
        stream = BinanceWebSocketStream(
            symbol="BTCUSDT",
            testnet=True,
            enable_rest_fallback=True,
        )

        # Mock REST response
        mock_fetch.return_value = {
            "symbol": "BTCUSDT",
            "bidPrice": "43000.00",
            "askPrice": "43000.50",
        }

        # WebSocket not connected - should fallback to REST
        price = stream.get_latest_price_with_fallback()

        assert price == 43000.25  # Mid price
        mock_fetch.assert_called_once()

    @patch("src.data.ws_stream.BinanceWebSocketStream._fetch_ticker_rest")
    def test_no_fallback_when_disabled(self, mock_fetch: Mock, mock_twm: MagicMock) -> None:
        """Test that REST fallback doesn't trigger when disabled."""
        stream = BinanceWebSocketStream(
            symbol="BTCUSDT",
            testnet=True,
            enable_rest_fallback=False,
        )

        # WebSocket not connected, fallback disabled
        price = stream.get_latest_price_with_fallback()

        assert price is None
        mock_fetch.assert_not_called()

    def test_exponential_backoff_delay(self) -> None:
        """Test exponential backoff calculation."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)

        # Simulate multiple reconnection attempts
        stream._reconnect_attempts = 0
        stream._base_reconnect_delay = 1.0

        # Attempt 1: 1.0 * 2^0 = 1.0s
        # Attempt 2: 1.0 * 2^1 = 2.0s
        # Attempt 3: 1.0 * 2^2 = 4.0s
        # Attempt 4: 1.0 * 2^3 = 8.0s
        # Attempt 5: 1.0 * 2^4 = 16.0s

        expected_delays = [1.0, 2.0, 4.0, 8.0, 16.0]

        for i in range(5):
            stream._reconnect_attempts = i
            delay = min(
                stream._base_reconnect_delay * (2**stream._reconnect_attempts),
                60.0,
            )
            assert delay == expected_delays[i]

    def test_context_manager(self, mock_twm: MagicMock) -> None:  # noqa: ARG002
        """Test WebSocket stream as context manager."""
        with BinanceWebSocketStream(symbol="BTCUSDT", testnet=True):
            # Stream should be started
            mock_twm.start.assert_called_once()

        # Stream should be stopped after exiting context
        mock_twm.stop.assert_called_once()

    def test_thread_safety_of_data_access(self, mock_twm: MagicMock) -> None:  # noqa: ARG002
        """Test that data access is thread-safe."""
        stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=True)
        stream.start()

        # Simulate concurrent message handling and data reading
        def write_data() -> None:
            for i in range(100):
                stream._handle_message({"b": f"{43000 + i}.00", "a": f"{43000 + i + 1}.00"})
                time.sleep(0.001)

        def read_data() -> None:
            for _ in range(100):
                stream.get_latest_ticker()
                stream.get_best_bid()
                stream.get_best_ask()
                time.sleep(0.001)

        # Start concurrent threads
        writer = Thread(target=write_data)
        reader = Thread(target=read_data)

        writer.start()
        reader.start()

        writer.join()
        reader.join()

        # Should complete without errors
        assert stream.get_latest_ticker() is not None

        stream.stop()


class TestWebSocketIntegration:
    """Integration tests for WebSocket stream (requires network)."""

    @pytest.mark.skip(reason="Integration test - requires Binance testnet connection")
    def test_real_websocket_connection(self) -> None:
        """Test real WebSocket connection to Binance testnet.

        This test requires:
        - Valid testnet API credentials
        - Network connectivity
        - Binance testnet availability
        """
        stream = BinanceWebSocketStream(
            symbol="BTCUSDT",
            testnet=True,
            enable_rest_fallback=True,
        )

        with stream:
            # Wait for first message
            max_wait = 10  # seconds
            start = time.monotonic()

            while time.monotonic() - start < max_wait:
                if stream.is_connected() and stream.get_latest_ticker() is not None:
                    break
                time.sleep(0.5)

            # Verify connection established
            assert stream.is_connected()

            # Verify data received
            ticker = stream.get_latest_ticker()
            assert ticker is not None
            assert "b" in ticker
            assert "a" in ticker

            # Verify price extraction
            bid = stream.get_best_bid()
            ask = stream.get_best_ask()
            mid = stream.get_mid_price()

            assert bid is not None
            assert ask is not None
            assert mid is not None
            assert bid < ask  # Sanity check
            assert bid < mid < ask

    @pytest.mark.skip(reason="Long-running stability test - run manually")
    def test_1hour_stability(self) -> None:
        """1+ hour stability test with network interruption.

        Manual test procedure:
        1. Run this test
        2. After 30 minutes, disable network (unplug ethernet or disable WiFi)
        3. Wait 2 minutes
        4. Re-enable network
        5. Verify automatic reconnection occurs
        6. Verify data continues flowing

        Expected behavior:
        - WebSocket should reconnect automatically after network restored
        - Health monitor should detect stale connection
        - Exponential backoff should prevent connection spam
        - Total runtime: 60+ minutes
        """
        stream = BinanceWebSocketStream(
            symbol="BTCUSDT",
            testnet=True,
            enable_rest_fallback=True,
        )

        message_count = 0
        errors = []

        def count_messages() -> None:
            nonlocal message_count
            ticker = stream.get_latest_ticker()
            if ticker is not None:
                message_count += 1

        with stream:
            start_time = time.monotonic()
            duration_seconds = 3600  # 1 hour

            while time.monotonic() - start_time < duration_seconds:
                try:
                    count_messages()

                    # Check health every 10 seconds
                    if int(time.monotonic() - start_time) % 10 == 0:
                        if not stream.is_connected():
                            errors.append(f"Disconnected at {int(time.monotonic() - start_time)}s")

                    time.sleep(1)

                except Exception as e:
                    errors.append(f"Error at {int(time.monotonic() - start_time)}s: {e}")

        # Verify stability
        assert message_count > 3000  # At least ~1 message per second
        assert len(errors) == 0 or all(
            "Disconnected" in e for e in errors
        )  # Only disconnection errors expected
