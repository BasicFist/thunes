"""Base strategy interface for plugin registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import pandas as pd
import vectorbt as vbt


@dataclass(slots=True)
class StrategyMetadata:
    """Describes a strategy's identity and configuration surface."""

    name: str
    description: str
    parameters: dict[str, Any]
    version: str = "1.0"


class BaseStrategy(ABC):
    """Base class all trading strategies must implement."""

    metadata: StrategyMetadata

    def __init__(self, **kwargs: Any) -> None:
        """Store initialization parameters for reproducibility."""
        self._init_kwargs = kwargs

    @property
    def strategy_id(self) -> str:
        """Stable identifier for registry lookups."""
        return self.metadata.name.lower()

    @property
    def parameters(self) -> dict[str, Any]:
        """Return initialization parameters."""
        return self._init_kwargs

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Return (entries, exits) boolean series."""

    @abstractmethod
    def backtest(
        self,
        df: pd.DataFrame,
        initial_capital: float = 10000.0,
        fees: float = 0.001,
        slippage: float = 0.0005,
    ) -> vbt.Portfolio:
        """Run a backtest and return vectorbt portfolio."""

    def get_stats(self, portfolio: vbt.Portfolio) -> pd.Series:
        """Convenience wrapper for stats extraction."""
        return portfolio.stats()
