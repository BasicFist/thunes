"""Main backtest runner script."""

import argparse

from src.backtest.rsi_strategy import RSIStrategy
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
    strategy_type: str = "rsi",
    # SMA parameters
    fast_window: int = 20,
    slow_window: int = 50,
    # RSI parameters
    rsi_period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
    stop_loss: float = 3.0,
) -> None:
    """
    Run backtest for specified symbol and parameters.

    Args:
        symbol: Trading pair symbol
        timeframe: Candlestick timeframe
        lookback_days: Number of days of historical data
        initial_capital: Starting capital
        strategy_type: Strategy to use ("sma" or "rsi")
        fast_window: Fast SMA window (SMA strategy)
        slow_window: Slow SMA window (SMA strategy)
        rsi_period: RSI calculation period (RSI strategy)
        oversold: RSI oversold threshold (RSI strategy)
        overbought: RSI overbought threshold (RSI strategy)
        stop_loss: Stop-loss percentage (RSI strategy)
    """
    logger.info(f"Starting backtest for {symbol} on {timeframe} timeframe")
    logger.info(f"Strategy: {strategy_type.upper()}")

    # Fetch data
    # Calculate required klines based on timeframe
    # For 90 days: 1h=2160, 4h=540, 1d=90
    timeframe_hours = {
        "1m": 1 / 60,
        "5m": 5 / 60,
        "15m": 15 / 60,
        "30m": 30 / 60,
        "1h": 1,
        "2h": 2,
        "4h": 4,
        "6h": 6,
        "12h": 12,
        "1d": 24,
        "1w": 24 * 7,
    }
    hours_per_candle = timeframe_hours.get(timeframe, 1)
    required_klines = int((lookback_days * 24) / hours_per_candle)

    # Use production Binance for historical data (public endpoint, no auth required)
    client = BinanceDataClient(testnet=False)
    df = client.get_historical_klines(
        symbol=symbol,
        interval=timeframe,
        start_str=f"{lookback_days} days ago UTC",
        limit=min(required_klines + 100, 1000),  # Binance max is 1000, add buffer
    )

    logger.info(f"Data fetched: {len(df)} candles from {df.index[0]} to {df.index[-1]}")

    # Select and run strategy
    if strategy_type.lower() == "sma":
        strategy = SMAStrategy(fast_window=fast_window, slow_window=slow_window)
        strategy_name = f"SMA_{fast_window}_{slow_window}"
    elif strategy_type.lower() == "rsi":
        strategy = RSIStrategy(
            rsi_period=rsi_period,
            oversold_threshold=oversold,
            overbought_threshold=overbought,
            stop_loss_pct=stop_loss,
        )
        strategy_name = f"RSI_{rsi_period}_{int(oversold)}_{int(overbought)}"
    else:
        raise ValueError(f"Unknown strategy type: {strategy_type}. Use 'sma' or 'rsi'.")

    portfolio = strategy.backtest(df, initial_capital=initial_capital)

    # Get statistics
    stats = strategy.get_stats(portfolio)

    # Save results with strategy name
    output_file = ARTIFACTS_DIR / "backtest" / f"stats_{symbol}_{timeframe}_{strategy_name}.csv"
    stats.to_csv(output_file)
    logger.info(f"Results saved to {output_file}")

    # Print key metrics
    print("\n" + "=" * 60)
    print(f"Backtest Results: {symbol} ({timeframe}) - {strategy_type.upper()}")
    print("=" * 60)
    print(f"Total Return: {stats['Total Return [%]']:.2f}%")
    print(f"Sharpe Ratio: {stats.get('Sharpe Ratio', 0.0):.2f}")
    print(f"Max Drawdown: {stats['Max Drawdown [%]']:.2f}%")
    print(f"Win Rate: {stats.get('Win Rate [%]', 0.0):.2f}%")
    print(f"Total Trades: {stats.get('Total Trades', 0)}")
    print("=" * 60 + "\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run backtest for crypto trading strategy")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol")
    parser.add_argument("--timeframe", type=str, default="1h", help="Candlestick timeframe")
    parser.add_argument("--lookback", type=int, default=40, help="Days of historical data")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital")
    parser.add_argument(
        "--strategy",
        type=str,
        default="rsi",
        choices=["sma", "rsi"],
        help="Strategy to use (default: rsi)",
    )

    # SMA parameters
    parser.add_argument("--fast", type=int, default=20, help="Fast SMA window (SMA strategy)")
    parser.add_argument("--slow", type=int, default=50, help="Slow SMA window (SMA strategy)")

    # RSI parameters
    parser.add_argument(
        "--rsi-period", type=int, default=14, help="RSI calculation period (RSI strategy)"
    )
    parser.add_argument(
        "--oversold", type=float, default=30.0, help="RSI oversold threshold (RSI strategy)"
    )
    parser.add_argument(
        "--overbought", type=float, default=70.0, help="RSI overbought threshold (RSI strategy)"
    )
    parser.add_argument(
        "--stop-loss", type=float, default=3.0, help="Stop-loss percentage (RSI strategy)"
    )

    args = parser.parse_args()

    run_backtest(
        symbol=args.symbol,
        timeframe=args.timeframe,
        lookback_days=args.lookback,
        initial_capital=args.capital,
        strategy_type=args.strategy,
        fast_window=args.fast,
        slow_window=args.slow,
        rsi_period=args.rsi_period,
        oversold=args.oversold,
        overbought=args.overbought,
        stop_loss=args.stop_loss,
    )


if __name__ == "__main__":
    main()
