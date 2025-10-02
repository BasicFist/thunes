"""Trading strategies for backtesting."""

import pandas as pd
import vectorbt as vbt

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class SMAStrategy:
    """Simple Moving Average crossover strategy."""

    def __init__(self, fast_window: int = 20, slow_window: int = 50) -> None:
        """
        Initialize SMA strategy.

        Args:
            fast_window: Fast SMA period (default: 20)
            slow_window: Slow SMA period (default: 50)
        """
        self.fast_window = fast_window
        self.slow_window = slow_window
        logger.info(f"SMA Strategy initialized: fast={fast_window}, slow={slow_window}")

    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """
        Generate entry and exit signals based on SMA crossover.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Tuple of (entry_signals, exit_signals) as boolean Series
        """
        close = df["close"]

        # Calculate SMAs
        fast_sma = vbt.MA.run(close, self.fast_window, short_name="fast")
        slow_sma = vbt.MA.run(close, self.slow_window, short_name="slow")

        # Entry: fast SMA crosses above slow SMA
        entries = fast_sma.ma_crossed_above(slow_sma)

        # Exit: fast SMA crosses below slow SMA
        exits = fast_sma.ma_crossed_below(slow_sma)

        logger.debug(f"Generated {entries.sum()} entry signals, {exits.sum()} exit signals")

        return entries, exits

    def backtest(
        self,
        df: pd.DataFrame,
        initial_capital: float = 10000.0,
        fees: float = 0.001,
        slippage: float = 0.0005,
    ) -> vbt.Portfolio:
        """
        Run backtest on historical data.

        Args:
            df: DataFrame with OHLCV data
            initial_capital: Starting capital in quote currency
            fees: Trading fees (0.001 = 0.1%)
            slippage: Estimated slippage per trade (0.0005 = 0.05%)

        Returns:
            VectorBT Portfolio object with backtest results
        """
        entries, exits = self.generate_signals(df)

        # Adjust price for slippage
        price = df["close"] * (1 + slippage)

        # Run portfolio simulation
        portfolio = vbt.Portfolio.from_signals(
            close=price,
            entries=entries,
            exits=exits,
            init_cash=initial_capital,
            fees=fees,
            freq="1h",  # Adjust based on timeframe
        )

        logger.info("Backtest completed")
        return portfolio

    def get_stats(self, portfolio: vbt.Portfolio) -> pd.Series:
        """
        Extract key statistics from portfolio.

        Args:
            portfolio: VectorBT Portfolio object

        Returns:
            Series with performance metrics
        """
        stats = portfolio.stats()
        logger.info(f"Total Return: {stats['Total Return [%]']:.2f}%")
        logger.info(f"Sharpe Ratio: {stats.get('Sharpe Ratio', 0.0):.2f}")
        logger.info(f"Max Drawdown: {stats['Max Drawdown [%]']:.2f}%")
        logger.info(f"Win Rate: {stats.get('Win Rate [%]', 0.0):.2f}%")

        return stats
