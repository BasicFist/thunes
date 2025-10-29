"""Risk manager integration smokes (opt-in)."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from src.config import settings
from src.models.position import PositionTracker
from src.risk.manager import RiskManager

pytestmark = [pytest.mark.slow, pytest.mark.integration_creds]

if os.getenv("RISK_MANAGER_TESTS_ENABLE") != "1":  # pragma: no cover - opt-in
    pytest.skip(
        "Set RISK_MANAGER_TESTS_ENABLE=1 to run risk manager integration smokes",
        allow_module_level=True,
    )


@pytest.mark.integration_creds
def test_risk_manager_enforces_limits(tmp_path) -> None:
    """Ensure per-trade limits and kill switch logic behave as expected."""
    tracker = PositionTracker(str(tmp_path / "positions.db"))
    manager = RiskManager(position_tracker=tracker, enable_telegram=False)

    allowed_quote = float(manager.max_loss_per_trade * Decimal("0.5"))
    is_valid, reason = manager.validate_trade(
        symbol=settings.default_symbol,
        quote_qty=allowed_quote,
        side="BUY",
        strategy_id="integration-smoke",
    )
    assert is_valid, f"expected trade to be allowed, got: {reason}"

    disallowed_quote = float(manager.max_loss_per_trade * Decimal("2"))
    is_valid, reason = manager.validate_trade(
        symbol=settings.default_symbol,
        quote_qty=disallowed_quote,
        side="BUY",
        strategy_id="integration-smoke",
    )
    assert not is_valid
    assert "max loss per trade" in reason.lower()

    manager.activate_kill_switch("integration smoke")
    try:
        is_valid, reason = manager.validate_trade(
            symbol=settings.default_symbol,
            quote_qty=allowed_quote,
            side="BUY",
            strategy_id="integration-smoke",
        )
        assert not is_valid
        assert "kill-switch" in reason.lower()
    finally:
        manager.deactivate_kill_switch("integration cleanup")
