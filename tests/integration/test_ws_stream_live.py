"""Live WebSocket integration smoke test.

This suite is intentionally skipped by default. Enable it by setting
`BINANCE_WS_TESTS_ENABLE=1` and providing Binance credentials via the usual
environment variables before running pytest. The test uses the same logic as
production, so it verifies that our offline guards can be bypassed safely when
we explicitly opt in to a real exchange connection.
"""

from __future__ import annotations

import os
import time

import pytest

from src.config import settings
from src.data.ws_stream import BinanceWebSocketStream

pytestmark = [pytest.mark.slow, pytest.mark.integration_creds]

if os.getenv("BINANCE_WS_TESTS_ENABLE") != "1":  # pragma: no cover - opt-in harness
    pytest.skip(
        "Set BINANCE_WS_TESTS_ENABLE=1 to run live WebSocket tests",
        allow_module_level=True,
    )


def _have_live_creds() -> bool:
    """Return True if either testnet or production credentials are configured."""
    has_testnet = bool(settings.binance_testnet_api_key and settings.binance_testnet_api_secret)
    has_live = bool(settings.binance_api_key and settings.binance_api_secret)
    return has_testnet or has_live


@pytest.mark.integration_creds
def test_websocket_stream_connects_with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the WebSocket stream reaches a live connected state."""
    if not _have_live_creds():
        pytest.skip("Binance credentials not configured")

    use_testnet = bool(settings.binance_testnet_api_key and settings.binance_testnet_api_secret)

    # Explicitly allow online mode even though pytest is running.
    monkeypatch.setenv("BINANCE_WS_ALLOW_ONLINE_TESTS", "1")

    stream = BinanceWebSocketStream(symbol="BTCUSDT", testnet=use_testnet)
    try:
        stream.start()
        deadline = time.time() + 15.0
        ticker: dict[str, str] | None = None

        while time.time() < deadline:
            if stream.is_connected() and not stream._offline_mode:
                ticker = stream.get_latest_ticker()
                if ticker:
                    break
            time.sleep(0.25)

        assert stream.is_connected(), "WebSocket did not report a healthy connection"
        assert not stream._offline_mode, "Offline mode remained active despite live credentials"

        assert ticker is not None, "No market data received before timeout"
        assert ticker.get("s") == "BTCUSDT"
    finally:
        stream.stop()
