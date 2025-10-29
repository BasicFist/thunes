"""PaperTrader integration smoke test (opt-in)."""

from __future__ import annotations

import os

import pytest
from binance.exceptions import BinanceAPIException

from src.config import settings
from src.live.paper_trader import PaperTrader

pytestmark = [pytest.mark.slow, pytest.mark.integration_creds]

if os.getenv("BINANCE_PAPER_TESTS_ENABLE") != "1":  # pragma: no cover - opt-in
    pytest.skip(
        "Set BINANCE_PAPER_TESTS_ENABLE=1 to run PaperTrader integration smokes",
        allow_module_level=True,
    )


def _has_trading_creds() -> bool:
    """Return True if Binance testnet or live credentials are configured."""
    return bool(
        (settings.binance_testnet_api_key and settings.binance_testnet_api_secret)
        or (settings.binance_api_key and settings.binance_api_secret)
    )


@pytest.mark.integration_creds
def test_paper_trader_rest_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate REST interactions (balance + price fallback) against live API."""
    if not _has_trading_creds():
        pytest.skip("Binance credentials not configured")

    # Ensure any websocket helper invoked for fallback respects opt-in behaviour.
    monkeypatch.setenv("BINANCE_WS_ALLOW_ONLINE_TESTS", "1")

    trader = PaperTrader(
        testnet=bool(settings.binance_testnet_api_key),
        enable_risk_manager=False,
        enable_performance_tracking=False,
        enable_telegram=False,
    )

    try:
        balance = trader.get_account_balance()
    except BinanceAPIException as exc:  # pragma: no cover - live integration only
        if getattr(exc, "code", None) == -2014 or "API-key format invalid" in str(exc):
            pytest.skip(f"Binance rejected credentials: {exc}")
        raise

    assert balance >= 0

    try:
        mid_price = trader.get_latest_price_with_fallback()
    except BinanceAPIException as exc:  # pragma: no cover - live integration only
        pytest.skip(f"Price lookup failed due to credentials: {exc}")

    assert mid_price is not None and mid_price > 0


@pytest.mark.integration_creds
def test_paper_trader_strategy_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke run the strategy loop without executing orders."""
    if not _has_trading_creds():
        pytest.skip("Binance credentials not configured")

    monkeypatch.setenv("BINANCE_WS_ALLOW_ONLINE_TESTS", "1")

    trader = PaperTrader(
        testnet=bool(settings.binance_testnet_api_key),
        enable_risk_manager=False,
        enable_performance_tracking=False,
        enable_telegram=False,
    )

    trader.run_strategy(symbol=settings.default_symbol, timeframe="1h", quote_amount=5.0)
