"""
Dynamic Position Sizing using Kelly Criterion and Volatility-Based Adjustments.

Optimizes capital allocation to maximize long-term growth while managing risk.
Implements fractional Kelly for real-world robustness.
"""

from decimal import Decimal
from typing import Optional

import numpy as np
import pandas as pd

from src.models.position import PositionTracker
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class PositionSizer:
    """
    Dynamic position sizing based on strategy performance and market conditions.

    Implements:
    - Kelly Criterion for optimal bet sizing
    - Volatility-based adjustments
    - Drawdown-based scaling
    - Strategy confidence weighting
    """

    def __init__(
        self,
        position_tracker: PositionTracker,
        kelly_fraction: float = 0.25,  # Conservative fractional Kelly
        min_trades_for_kelly: int = 30,  # Minimum sample size
        max_position_pct: float = 0.05,  # Max 5% of capital per position
        volatility_lookback: int = 20,  # Days for volatility calculation
    ):
        """
        Initialize position sizer.

        Args:
            position_tracker: Position tracker for historical performance
            kelly_fraction: Fraction of full Kelly to use (0.25 = quarter Kelly)
            min_trades_for_kelly: Minimum trades before using Kelly
            max_position_pct: Maximum position size as % of total capital
            volatility_lookback: Lookback period for volatility calculation
        """
        self.position_tracker = position_tracker
        self.kelly_fraction = kelly_fraction
        self.min_trades_for_kelly = min_trades_for_kelly
        self.max_position_pct = max_position_pct
        self.volatility_lookback = volatility_lookback

        logger.info(
            f"PositionSizer initialized: kelly_fraction={kelly_fraction}, "
            f"min_trades={min_trades_for_kelly}, max_pct={max_position_pct}"
        )

    def calculate_kelly_size(
        self,
        total_capital: float,
        strategy_id: str = "default",
    ) -> Optional[float]:
        """
        Calculate optimal position size using Kelly Criterion.

        Kelly formula: f* = (p*W - (1-p)) / W
        Where:
        - p = win rate
        - W = average win / average loss ratio
        - f* = fraction of capital to risk

        Args:
            total_capital: Total available capital
            strategy_id: Strategy identifier for performance tracking

        Returns:
            Optimal position size in quote currency (USDT), or None if insufficient data
        """
        # Get strategy performance history
        history = self.position_tracker.get_position_history(limit=100)

        # Filter by strategy if specified
        if strategy_id != "default":
            history = [p for p in history if p.strategy_id == strategy_id]

        if len(history) < self.min_trades_for_kelly:
            logger.warning(
                f"Insufficient trade history for Kelly ({len(history)}/{self.min_trades_for_kelly})"
            )
            return None

        # Calculate win rate and win/loss ratio
        wins = [p for p in history if p.pnl and p.pnl > 0]
        losses = [p for p in history if p.pnl and p.pnl < 0]

        if not wins or not losses:
            logger.warning("Need both wins and losses for Kelly calculation")
            return None

        win_rate = len(wins) / len(history)
        avg_win = abs(float(sum(p.pnl for p in wins) / len(wins)))
        avg_loss = abs(float(sum(p.pnl for p in losses) / len(losses)))
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # Kelly formula
        kelly_pct = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio

        # Apply fractional Kelly for robustness
        kelly_pct = kelly_pct * self.kelly_fraction

        # Clip to reasonable bounds
        kelly_pct = max(0.01, min(kelly_pct, self.max_position_pct))

        position_size = total_capital * kelly_pct

        logger.info(
            f"Kelly calculation: win_rate={win_rate:.2%}, W={win_loss_ratio:.2f}, "
            f"kelly={kelly_pct:.2%}, size={position_size:.2f} USDT"
        )

        return position_size

    def calculate_volatility_adjusted_size(
        self,
        base_size: float,
        symbol: str,
        price_history: pd.Series,
    ) -> float:
        """
        Adjust position size based on recent volatility.

        Higher volatility → smaller position size
        Lower volatility → larger position size (up to max)

        Args:
            base_size: Base position size before adjustment
            symbol: Trading symbol
            price_history: Recent price data (pandas Series)

        Returns:
            Volatility-adjusted position size
        """
        if len(price_history) < self.volatility_lookback:
            logger.warning(f"Insufficient price history for volatility adjustment ({len(price_history)})")
            return base_size

        # Calculate historical volatility (annualized)
        returns = price_history.pct_change().dropna()
        volatility = returns.std() * np.sqrt(365)  # Annualized (crypto trades 24/7)

        # Benchmark volatility (typical crypto: 50-100% annually)
        benchmark_vol = 0.75  # 75% annualized

        # Adjust size inversely to volatility
        vol_multiplier = benchmark_vol / volatility if volatility > 0 else 1.0

        # Clip to reasonable range (0.5x to 1.5x)
        vol_multiplier = max(0.5, min(vol_multiplier, 1.5))

        adjusted_size = base_size * vol_multiplier

        logger.info(
            f"Volatility adjustment for {symbol}: vol={volatility:.1%}, "
            f"multiplier={vol_multiplier:.2f}, size={adjusted_size:.2f} USDT"
        )

        return adjusted_size

    def calculate_drawdown_adjusted_size(
        self,
        base_size: float,
        current_drawdown_pct: float,
    ) -> float:
        """
        Reduce position size during drawdown periods.

        Implements risk reduction during losing streaks to prevent
        catastrophic losses (part of risk management best practices).

        Args:
            base_size: Base position size before adjustment
            current_drawdown_pct: Current drawdown as % (0-100)

        Returns:
            Drawdown-adjusted position size
        """
        if current_drawdown_pct <= 0:
            return base_size

        # Scale down aggressively during drawdown
        # 0% drawdown → 1.0x
        # 10% drawdown → 0.75x
        # 20% drawdown → 0.5x
        # 30%+ drawdown → 0.25x
        if current_drawdown_pct < 10:
            multiplier = 1.0
        elif current_drawdown_pct < 20:
            multiplier = 0.75
        elif current_drawdown_pct < 30:
            multiplier = 0.5
        else:
            multiplier = 0.25

        adjusted_size = base_size * multiplier

        logger.warning(
            f"Drawdown adjustment: drawdown={current_drawdown_pct:.1f}%, "
            f"multiplier={multiplier:.2f}, size={adjusted_size:.2f} USDT"
        )

        return adjusted_size

    def get_optimal_size(
        self,
        total_capital: float,
        symbol: str,
        price_history: Optional[pd.Series] = None,
        current_drawdown_pct: float = 0.0,
        strategy_id: str = "default",
        base_size: Optional[float] = None,
    ) -> float:
        """
        Calculate optimal position size with all adjustments.

        Combines:
        1. Kelly Criterion (if sufficient data)
        2. Volatility adjustment
        3. Drawdown adjustment

        Args:
            total_capital: Total available capital
            symbol: Trading symbol
            price_history: Recent price data for volatility calc
            current_drawdown_pct: Current drawdown percentage
            strategy_id: Strategy identifier
            base_size: Override base size (defaults to Kelly or fixed %)

        Returns:
            Optimal position size in quote currency
        """
        # 1. Determine base size
        if base_size is None:
            kelly_size = self.calculate_kelly_size(total_capital, strategy_id)
            if kelly_size is not None:
                base_size = kelly_size
            else:
                # Fallback: Conservative fixed % (2% of capital)
                base_size = total_capital * 0.02
                logger.info(f"Using fallback position size: {base_size:.2f} USDT (2% of capital)")

        # 2. Apply volatility adjustment
        if price_history is not None:
            base_size = self.calculate_volatility_adjusted_size(base_size, symbol, price_history)

        # 3. Apply drawdown adjustment
        if current_drawdown_pct > 0:
            base_size = self.calculate_drawdown_adjusted_size(base_size, current_drawdown_pct)

        # 4. Apply hard cap
        max_size = total_capital * self.max_position_pct
        final_size = min(base_size, max_size)

        if final_size < base_size:
            logger.warning(
                f"Position size capped: {base_size:.2f} → {final_size:.2f} USDT "
                f"(max {self.max_position_pct:.1%} of capital)"
            )

        logger.info(f"Final position size for {symbol}: {final_size:.2f} USDT")
        return final_size

    def get_strategy_stats(self, strategy_id: str = "default") -> dict:
        """
        Get strategy performance statistics.

        Args:
            strategy_id: Strategy identifier

        Returns:
            Dictionary with performance metrics
        """
        history = self.position_tracker.get_position_history(limit=100)

        if strategy_id != "default":
            history = [p for p in history if p.strategy_id == strategy_id]

        if not history:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "win_loss_ratio": 0.0,
                "kelly_pct": 0.0,
            }

        wins = [p for p in history if p.pnl and p.pnl > 0]
        losses = [p for p in history if p.pnl and p.pnl < 0]

        win_rate = len(wins) / len(history) if history else 0
        avg_win = abs(float(sum(p.pnl for p in wins) / len(wins))) if wins else 0
        avg_loss = abs(float(sum(p.pnl for p in losses) / len(losses))) if losses else 0
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # Kelly percentage
        kelly_pct = 0.0
        if win_loss_ratio > 0:
            kelly_pct = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
            kelly_pct = max(0, kelly_pct * self.kelly_fraction)

        return {
            "total_trades": len(history),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "win_loss_ratio": win_loss_ratio,
            "kelly_pct": kelly_pct,
            "wins": len(wins),
            "losses": len(losses),
        }
