"""Tests for configuration module."""

from src.config import settings, ARTIFACTS_DIR, LOGS_DIR, PROJECT_ROOT


def test_settings_loaded() -> None:
    """Test that settings are loaded correctly."""
    assert settings is not None
    assert settings.default_symbol == "BTCUSDT"
    assert settings.default_timeframe == "1h"
    assert settings.environment in ["testnet", "paper", "live"]


def test_paths_exist() -> None:
    """Test that required directories exist."""
    assert PROJECT_ROOT.exists()
    assert ARTIFACTS_DIR.exists()
    assert LOGS_DIR.exists()
    assert (ARTIFACTS_DIR / "backtest").exists()
    assert (ARTIFACTS_DIR / "optuna").exists()


def test_is_production_flag() -> None:
    """Test production environment detection."""
    if settings.environment == "live":
        assert settings.is_production is True
    else:
        assert settings.is_production is False
