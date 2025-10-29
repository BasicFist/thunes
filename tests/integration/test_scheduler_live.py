"""Scheduler and monitoring integration smokes (opt-in)."""

from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request

import pytest
from binance.exceptions import BinanceAPIException

from src.config import settings
from src.monitoring.prometheus_metrics import metrics_handler, update_ws_connection
from src.orchestration.run_scheduler import run_metrics_server
from src.orchestration.scheduler import TradingScheduler

pytestmark = [pytest.mark.slow, pytest.mark.integration_creds]

if not (
    os.getenv("SCHEDULER_TESTS_ENABLE") == "1" or os.getenv("MONITORING_TESTS_ENABLE") == "1"
):  # pragma: no cover - opt-in harness
    pytest.skip(
        "Set SCHEDULER_TESTS_ENABLE=1 or MONITORING_TESTS_ENABLE=1 to run scheduler/monitoring smokes",
        allow_module_level=True,
    )


def _ensure(flag: str, message: str) -> None:
    if os.getenv(flag) != "1":
        pytest.skip(message)


def _has_trading_creds() -> bool:
    return bool(
        (settings.binance_testnet_api_key and settings.binance_testnet_api_secret)
        or (settings.binance_api_key and settings.binance_api_secret)
    )


@pytest.mark.integration_creds
def test_scheduler_starts_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure TradingScheduler boots, schedules jobs, and shuts down."""
    _ensure("SCHEDULER_TESTS_ENABLE", "Set SCHEDULER_TESTS_ENABLE=1 to run scheduler smoke")
    if not _has_trading_creds():
        pytest.skip("Binance credentials not configured")

    monkeypatch.setenv("BINANCE_WS_ALLOW_ONLINE_TESTS", "1")

    try:
        scheduler = TradingScheduler(use_persistent_store=False)
    except BinanceAPIException as exc:  # pragma: no cover - live integration only
        pytest.skip(f"Scheduler could not initialize due to credentials: {exc}")

    scheduler.schedule_signal_check(interval_minutes=60)
    scheduler.schedule_daily_summary(hour=23, minute=0)
    scheduler.schedule_lab_metrics_update(interval_seconds=300)

    scheduler.start()
    try:
        time.sleep(1.0)
        jobs = scheduler.get_job_status()
        assert jobs, "Expected scheduled jobs to be present"
    finally:
        scheduler.stop(wait=False)


@pytest.mark.integration_creds
def test_prometheus_metrics_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that the metrics endpoint emits data over HTTP."""
    _ensure("MONITORING_TESTS_ENABLE", "Set MONITORING_TESTS_ENABLE=1 to run monitoring smoke")

    update_ws_connection(settings.default_symbol, True)
    payload = metrics_handler().decode()
    assert "thunes_ws_connected" in payload

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    thread = threading.Thread(target=run_metrics_server, args=(port,), daemon=True)
    thread.start()

    deadline = time.time() + 5.0
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=1.0) as resp:
                body = resp.read().decode()
            assert "thunes_ws_connected" in body
            break
        except Exception as exc:  # pragma: no cover - best effort loop
            last_error = exc
            time.sleep(0.2)
    else:
        pytest.fail(f"Failed to fetch metrics endpoint: {last_error}")
