"""RSI Mean Reversion Trading Strategy."""

import pandas as pd
import vectorbt as vbt

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class RSIStrategy:
    """
    RSI Mean Reversion Strategy.

    Entry: RSI crosses below oversold threshold (default: 30)
    Exit: RSI crosses above overbought threshold (default: 70) OR stop-loss triggered

    This strategy is designed for volatile, oscillating markets like crypto,
    where mean reversion often outperforms trend-following approaches.
    """

    def __init__(
        self,
        rsi_period: int = 14,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
        stop_loss_pct: float = 3.0,
    ) -> None:
        """
        Initialize RSI mean reversion strategy.

        Args:
            rsi_period: RSI calculation period (default: 14, industry standard)
            oversold_threshold: RSI level for oversold entry (default: 30)
            overbought_threshold: RSI level for overbought exit (default: 70)
            stop_loss_pct: Stop-loss percentage from entry price (default: 3%)
        """
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        self.stop_loss_pct = stop_loss_pct

        logger.info(
            f"RSI Strategy initialized: period={rsi_period}, "
            f"oversold={oversold_threshold}, overbought={overbought_threshold}, "
            f"stop_loss={stop_loss_pct}%"
        )

    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """
        Generate entry and exit signals based on RSI mean reversion.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Tuple of (entry_signals, exit_signals) as boolean Series

        Strategy Logic:
            - Entry: RSI crosses below oversold threshold (momentum exhaustion)
            - Exit: RSI crosses above overbought threshold OR stop-loss triggered
        """
        # Shift close prices to prevent look-ahead bias
        # Signal at bar i uses only data through bar i-1
        close = df["close"].shift(1)

        # Calculate RSI using vectorbt
        rsi_indicator = vbt.RSI.run(close, window=self.rsi_period, short_name="rsi")
        rsi = rsi_indicator.rsi

        # Entry: RSI crosses below oversold threshold
        # Use crossing logic to avoid staying in oversold too long
        entries = (rsi < self.oversold_threshold) & (rsi.shift(1) >= self.oversold_threshold)

        # Exit: RSI crosses above overbought threshold
        exits_overbought = (rsi > self.overbought_threshold) & (
            rsi.shift(1) <= self.overbought_threshold
        )

        # Exit: Stop-loss triggered (price drops stop_loss_pct% from entry)
        exits_stoploss = self._calculate_stop_loss(df, entries, self.stop_loss_pct)

        # Combine exit conditions
        exits = exits_overbought | exits_stoploss

        logger.debug(
            f"Generated {entries.sum()} entry signals, "
            f"{exits_overbought.sum()} overbought exits, "
            f"{exits_stoploss.sum()} stop-loss exits"
        )

        return entries, exits

    def _calculate_stop_loss(
        self, df: pd.DataFrame, entries: pd.Series, stop_loss_pct: float
    ) -> pd.Series:
        """
        Calculate stop-loss exit signals.

        Args:
            df: DataFrame with OHLCV data
            entries: Boolean series of entry signals
            stop_loss_pct: Stop-loss percentage threshold

        Returns:
            Boolean series indicating stop-loss exits

        Logic:
            - Track entry price for each position
            - Exit if current price drops stop_loss_pct% from entry
        """
        # Forward-fill entry prices to track position entry levels
        entry_prices = df["close"].where(entries).ffill()

        # Calculate price change from entry
        current_prices = df["close"]
        price_change_pct = ((current_prices - entry_prices) / entry_prices) * 100

        # Stop-loss triggered when price drops below threshold
        stop_loss_signals = price_change_pct < -stop_loss_pct

        # Only trigger stop-loss when in position (after an entry)
        in_position = entries.cumsum() > 0
        stop_loss_exits = stop_loss_signals & in_position

        return stop_loss_exits

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
