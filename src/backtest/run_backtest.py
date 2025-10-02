"""Main backtest runner script."""

import argparse
from pathlib import Path

import pandas as pd

from src.backtest.strategy import SMAStrategy
from src.config import ARTIFACTS_DIR
from src.data.binance_client import BinanceDataClient
from src.utils.logger import setup_logger

logger = setup_logger(__name__, log_file="backtest.log")


def run_backtest(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    lookback_days: int = 90,
    initial_capital: float = 10000.0,
    fast_window: int = 20,
    slow_window: int = 50,
) -> None:
    """
    Run backtest for specified symbol and parameters.

    Args:
        symbol: Trading pair symbol
        timeframe: Candlestick timeframe
        lookback_days: Number of days of historical data
        initial_capital: Starting capital
        fast_window: Fast SMA window
        slow_window: Slow SMA window
    """
    logger.info(f"Starting backtest for {symbol} on {timeframe} timeframe")
    logger.info(f"Parameters: fast={fast_window}, slow={slow_window}")

    # Fetch data
    client = BinanceDataClient(testnet=True)
    df = client.get_historical_klines(
        symbol=symbol,
        interval=timeframe,
        start_str=f"{lookback_days} days ago UTC",
        limit=1000,
    )

    logger.info(f"Data fetched: {len(df)} candles from {df.index[0]} to {df.index[-1]}")

    # Run strategy
    strategy = SMAStrategy(fast_window=fast_window, slow_window=slow_window)
    portfolio = strategy.backtest(df, initial_capital=initial_capital)

    # Get statistics
    stats = strategy.get_stats(portfolio)

    # Save results
    output_file = ARTIFACTS_DIR / "backtest" / f"stats_{symbol}_{timeframe}.csv"
    stats.to_csv(output_file)
    logger.info(f"Results saved to {output_file}")

    # Print key metrics
    print("\n" + "=" * 50)
    print(f"Backtest Results: {symbol} ({timeframe})")
    print("=" * 50)
    print(f"Total Return: {stats['Total Return [%]']:.2f}%")
    print(f"Sharpe Ratio: {stats.get('Sharpe Ratio', 0.0):.2f}")
    print(f"Max Drawdown: {stats['Max Drawdown [%]']:.2f}%")
    print(f"Win Rate: {stats.get('Win Rate [%]', 0.0):.2f}%")
    print(f"Total Trades: {stats.get('Total Trades', 0)}")
    print("=" * 50 + "\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run backtest for crypto trading strategy")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol")
    parser.add_argument("--timeframe", type=str, default="1h", help="Candlestick timeframe")
    parser.add_argument("--lookback", type=int, default=90, help="Days of historical data")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital")
    parser.add_argument("--fast", type=int, default=20, help="Fast SMA window")
    parser.add_argument("--slow", type=int, default=50, help="Slow SMA window")

    args = parser.parse_args()

    run_backtest(
        symbol=args.symbol,
        timeframe=args.timeframe,
        lookback_days=args.lookback,
        initial_capital=args.capital,
        fast_window=args.fast,
        slow_window=args.slow,
    )


if __name__ == "__main__":
    main()
