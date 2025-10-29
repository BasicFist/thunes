"""Strategy plugin infrastructure."""

from .base import BaseStrategy, StrategyMetadata  # noqa: F401
from .registry import register_strategy, strategy_registry  # noqa: F401
