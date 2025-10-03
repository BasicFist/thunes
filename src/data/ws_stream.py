"""WebSocket streaming for real-time Binance market data.

This module provides real-time price feeds via Binance WebSocket API with:
- Automatic reconnection with exponential backoff
- Ping/pong watchdog for connection health monitoring
- Graceful degradation to REST API fallback
- Thread-safe callback handling
"""

import time
from queue import Queue
from threading import Event, Lock, Thread
from typing import Any

from binance import ThreadedWebsocketManager
from binance.exceptions import BinanceAPIException

from src.config import settings
from src.utils.circuit_breaker import with_circuit_breaker
from src.utils.logger import setup_logger
from src.utils.rate_limiter import with_rate_limit

logger = setup_logger(__name__)


class WebSocketHealthMonitor:
    """Monitor WebSocket connection health via ping/pong mechanism.

    Detects stale connections by tracking last message timestamp.
    Triggers reconnection if no messages received within timeout period.
    """

    def __init__(self, timeout_seconds: int = 60, check_interval_seconds: int = 10) -> None:
        """Initialize health monitor.

        Args:
            timeout_seconds: Max seconds without messages before reconnect
            check_interval_seconds: How often watchdog checks health (default: 10s)
        """
        self.timeout_seconds = timeout_seconds
        self.check_interval_seconds = check_interval_seconds
        self.last_message_time: float = time.monotonic()
        self.lock = Lock()
        self._running = False
        self._watchdog_thread: Thread | None = None

    def record_message(self) -> None:
        """Record that a message was received."""
        with self.lock:
            self.last_message_time = time.monotonic()

    def is_healthy(self) -> bool:
        """Check if connection is healthy based on last message time.

        Returns:
            True if messages received within timeout window
        """
        with self.lock:
            elapsed = time.monotonic() - self.last_message_time
            return elapsed < self.timeout_seconds

    def start_watchdog(self, reconnect_queue: Queue[str]) -> None:
        """Start background watchdog thread.

        Args:
            reconnect_queue: Queue to signal reconnection requests (non-blocking)
        """
        if self._running:
            logger.warning("Watchdog already running")
            return

        self._running = True

        def watchdog_loop() -> None:
            try:
                while self._running:
                    time.sleep(self.check_interval_seconds)
                    if not self.is_healthy():
                        logger.error(
                            f"WebSocket unhealthy: no messages for {self.timeout_seconds}s"
                        )
                        # Non-blocking: signal control thread to handle reconnection
                        reconnect_queue.put("reconnect")
                        break
            finally:
                # CRITICAL: Reset state so subsequent start_watchdog() calls can succeed
                self._running = False
                self._watchdog_thread = None
                logger.debug("Watchdog thread exited, state cleared for reconnection")

        self._watchdog_thread = Thread(target=watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        logger.info(
            f"Started WebSocket watchdog (timeout={self.timeout_seconds}s, "
            f"check_interval={self.check_interval_seconds}s)"
        )

    def stop_watchdog(self) -> None:
        """Stop watchdog thread and reset state for clean restart."""
        self._running = False
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=2.0)
        # Reset thread reference so start_watchdog can create a new one
        self._watchdog_thread = None
        logger.info("Stopped WebSocket watchdog")


class BinanceWebSocketStream:
    """Real-time Binance WebSocket stream with resilience features.

    Features:
    - bookTicker stream (best bid/ask prices with quantities)
    - Automatic reconnection with exponential backoff
    - Connection health monitoring via watchdog
    - Graceful degradation to REST API when WebSocket fails
    - Thread-safe operation
    """

    def __init__(
        self,
        symbol: str,
        testnet: bool = True,
        enable_rest_fallback: bool = True,
    ) -> None:
        """Initialize WebSocket stream.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            testnet: Use testnet API (True) or production (False)
            enable_rest_fallback: Enable automatic REST fallback on failure
        """
        self.symbol = symbol.upper()
        self.testnet = testnet
        self.enable_rest_fallback = enable_rest_fallback

        # WebSocket manager (python-binance ThreadedWebsocketManager)
        self.twm: ThreadedWebsocketManager | None = None
        self._stream_key: str | None = None

        # Connection state
        self._connected = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._base_reconnect_delay = 1.0  # seconds
        self._stop_event = Event()

        # Control thread for reconnection (prevents callback thread blocking)
        self._reconnect_queue: Queue[str] = Queue()
        self._control_thread: Thread | None = None

        # Health monitoring
        self.health_monitor = WebSocketHealthMonitor(timeout_seconds=60)

        # Latest market data (thread-safe access)
        self._latest_data: dict[str, Any] = {}
        self._data_lock = Lock()

        # REST fallback (lazy initialization)
        self._rest_client: Any = None

        logger.info(
            f"Initialized WebSocket stream for {symbol} "
            f"(testnet={testnet}, fallback={enable_rest_fallback})"
        )

    def _init_websocket_manager(self) -> None:
        """Initialize ThreadedWebsocketManager with credentials."""
        api_key = settings.binance_testnet_api_key if self.testnet else settings.binance_api_key
        api_secret = (
            settings.binance_testnet_api_secret if self.testnet else settings.binance_api_secret
        )

        self.twm = ThreadedWebsocketManager(
            api_key=api_key,
            api_secret=api_secret,
            testnet=self.testnet,
        )
        self.twm.start()
        logger.info("Started ThreadedWebsocketManager")

    def _handle_message(self, msg: dict[str, Any]) -> None:
        """Process incoming WebSocket message.

        Args:
            msg: WebSocket message dictionary
        """
        # Record message for health monitoring
        self.health_monitor.record_message()

        # Update latest data (thread-safe)
        with self._data_lock:
            self._latest_data = msg

        # Log first message for debugging
        if not self._connected:
            logger.info(f"First WebSocket message received: {msg}")
            self._connected = True
            self._reconnect_attempts = 0  # Reset on successful connection

    def _handle_error(self, msg: dict[str, Any]) -> None:
        """Handle WebSocket error messages.

        Args:
            msg: Error message dictionary
        """
        logger.error(f"WebSocket error: {msg}")

        # Trigger reconnection for critical errors
        if msg.get("m") == "error":
            self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self._max_reconnect_attempts}) reached")
            if self.enable_rest_fallback:
                logger.warning("Falling back to REST API")
                # Caller should check is_connected() and use get_latest_price()
            return

        # Calculate exponential backoff delay
        delay = min(
            self._base_reconnect_delay * (2**self._reconnect_attempts),
            60.0,  # Cap at 60 seconds
        )
        self._reconnect_attempts += 1

        logger.info(
            f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts}/"
            f"{self._max_reconnect_attempts})"
        )
        time.sleep(delay)

        # Stop existing stream
        self.stop()

        # Restart stream
        self.start()

    def _control_loop(self) -> None:
        """Control thread that handles reconnection requests from watchdog.

        This prevents the watchdog from blocking on itself when calling stop().
        """
        while not self._stop_event.is_set():
            try:
                # Block until watchdog signals reconnection (with timeout)
                signal = self._reconnect_queue.get(timeout=1.0)
                if signal == "reconnect":
                    logger.info("Control thread received reconnect signal")
                    self._attempt_reconnect()
            except Exception:
                # Timeout or queue closed - continue monitoring
                continue

    def start(self) -> None:
        """Start WebSocket stream for bookTicker data.

        Subscribes to real-time best bid/ask price updates.
        """
        if self._stop_event.is_set():
            self._stop_event.clear()

        # Start control thread for reconnection handling
        if self._control_thread is None or not self._control_thread.is_alive():
            self._control_thread = Thread(target=self._control_loop, daemon=True)
            self._control_thread.start()
            logger.info("Started WebSocket control thread")

        # Initialize manager if needed
        if self.twm is None:
            self._init_websocket_manager()

        # Start bookTicker stream
        try:
            assert self.twm is not None
            self._stream_key = self.twm.start_symbol_book_ticker_socket(
                callback=self._handle_message,
                symbol=self.symbol,
            )
            logger.info(f"Started bookTicker stream for {self.symbol}")

            # Start health monitoring (signals via queue instead of callback)
            self.health_monitor.start_watchdog(reconnect_queue=self._reconnect_queue)

        except Exception as e:
            logger.error(f"Failed to start WebSocket stream: {e}")
            raise

    def stop(self) -> None:
        """Stop WebSocket stream and cleanup resources."""
        self._stop_event.set()

        # Stop health monitoring
        self.health_monitor.stop_watchdog()

        # Stop WebSocket stream
        if self.twm is not None:
            try:
                if self._stream_key:
                    self.twm.stop_socket(self._stream_key)
                self.twm.stop()
                logger.info("Stopped WebSocket stream")
            except Exception as e:
                logger.error(f"Error stopping WebSocket: {e}")

        self.twm = None
        self._stream_key = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if WebSocket is connected and healthy.

        Returns:
            True if connected and receiving messages
        """
        return self._connected and self.health_monitor.is_healthy()

    def get_latest_ticker(self) -> dict[str, Any] | None:
        """Get latest bookTicker data from WebSocket.

        Returns:
            Latest ticker dict with keys: 'u', 'b', 'B', 'a', 'A'
            (update_id, best_bid, bid_qty, best_ask, ask_qty)
            None if no data received yet
        """
        with self._data_lock:
            return self._latest_data.copy() if self._latest_data else None

    def get_best_bid(self) -> float | None:
        """Get current best bid price.

        Returns:
            Best bid price or None if unavailable
        """
        ticker = self.get_latest_ticker()
        if ticker and "b" in ticker:
            return float(ticker["b"])
        return None

    def get_best_ask(self) -> float | None:
        """Get current best ask price.

        Returns:
            Best ask price or None if unavailable
        """
        ticker = self.get_latest_ticker()
        if ticker and "a" in ticker:
            return float(ticker["a"])
        return None

    def get_mid_price(self) -> float | None:
        """Calculate mid price from best bid/ask.

        Returns:
            Mid price ((bid + ask) / 2) or None if unavailable
        """
        bid = self.get_best_bid()
        ask = self.get_best_ask()

        if bid is not None and ask is not None:
            return (bid + ask) / 2.0
        return None

    # REST API fallback methods

    def _init_rest_client(self) -> None:
        """Lazy initialization of REST client for fallback."""
        if self._rest_client is not None:
            return

        from binance.client import Client

        if self.testnet:
            self._rest_client = Client(
                api_key=settings.binance_testnet_api_key,
                api_secret=settings.binance_testnet_api_secret,
                testnet=True,
            )
        else:
            self._rest_client = Client(
                api_key=settings.binance_api_key or "",
                api_secret=settings.binance_api_secret or "",
            )

        logger.info("Initialized REST client for fallback")

    @with_circuit_breaker()
    @with_rate_limit(weight=2, is_order=False)
    def _fetch_ticker_rest(self) -> dict[str, Any]:
        """Fetch bookTicker via REST API (fallback).

        Returns:
            Ticker data from REST API

        Raises:
            BinanceAPIException: If API call fails
        """
        if self._rest_client is None:
            self._init_rest_client()

        assert self._rest_client is not None
        ticker: dict[str, Any] = self._rest_client.get_orderbook_ticker(symbol=self.symbol)
        logger.debug(f"Fetched ticker via REST: {ticker}")
        return ticker

    def get_latest_price_with_fallback(self) -> float | None:
        """Get latest mid price with automatic REST fallback.

        First tries WebSocket, falls back to REST API if WebSocket unavailable.

        Returns:
            Mid price or None if both methods fail
        """
        # Try WebSocket first
        if self.is_connected():
            mid_price = self.get_mid_price()
            if mid_price is not None:
                return mid_price
            logger.warning("WebSocket connected but no price data")

        # Fallback to REST API
        if not self.enable_rest_fallback:
            logger.warning("REST fallback disabled, no price available")
            return None

        try:
            ticker = self._fetch_ticker_rest()
            bid = float(ticker["bidPrice"])
            ask = float(ticker["askPrice"])
            mid_price = (bid + ask) / 2.0
            logger.info(f"Using REST fallback price: {mid_price}")
            return mid_price
        except BinanceAPIException as e:
            logger.error(f"REST fallback failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in REST fallback: {e}")
            return None

    def __enter__(self) -> "BinanceWebSocketStream":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop()
