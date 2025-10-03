"""Configuration management for THUNES trading system."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Binance API (Testnet)
    binance_testnet_api_key: str = Field(default="")
    binance_testnet_api_secret: str = Field(default="")
    binance_testnet_base_url: str = Field(default="https://testnet.binance.vision")

    # Binance API (Production)
    binance_api_key: str = Field(default="")
    binance_api_secret: str = Field(default="")

    # Telegram
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    # Environment
    tz: str = Field(default="Europe/Paris")
    environment: Literal["testnet", "paper", "live"] = Field(default="testnet")

    # Trading
    default_symbol: str = Field(default="BTCUSDT")
    default_timeframe: str = Field(default="1h")
    default_quote_amount: float = Field(default=10.0)

    # Risk Management
    max_loss_per_trade: float = Field(default=5.0)
    max_daily_loss: float = Field(default=20.0)
    max_positions: int = Field(default=3)
    cool_down_minutes: int = Field(default=60)

    # Monitoring
    prometheus_port: int = Field(default=9090)
    log_level: str = Field(default="INFO")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "live"

    @property
    def api_key(self) -> str:
        """Get appropriate API key based on environment."""
        if self.environment == "testnet":
            return self.binance_testnet_api_key
        return self.binance_api_key

    @property
    def api_secret(self) -> str:
        """Get appropriate API secret based on environment."""
        if self.environment == "testnet":
            return self.binance_testnet_api_secret
        return self.binance_api_secret

    @property
    def base_url(self) -> str:
        """Get appropriate base URL based on environment."""
        if self.environment == "testnet":
            return self.binance_testnet_base_url
        return "https://api.binance.com"


# Global settings instance
settings = Settings()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
LOGS_DIR = PROJECT_ROOT / "logs"


def ensure_directories() -> None:
    """Ensure required directories exist.

    IMPORTANT: Call this from entrypoints (backtest, paper, optimize) instead of
    at module import time to avoid failures in read-only or testing environments.

    Creates:
    - artifacts/
    - artifacts/backtest/
    - artifacts/optuna/
    - artifacts/monitoring/
    - logs/
    """
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    (ARTIFACTS_DIR / "backtest").mkdir(exist_ok=True)
    (ARTIFACTS_DIR / "optuna").mkdir(exist_ok=True)
    (ARTIFACTS_DIR / "monitoring").mkdir(exist_ok=True)
