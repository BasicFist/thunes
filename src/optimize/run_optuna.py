"""Hyperparameter optimization using Optuna."""

import argparse
from typing import Any

import optuna
import pandas as pd
from optuna.trial import Trial

from src.backtest.strategy import SMAStrategy
from src.config import ARTIFACTS_DIR
from src.data.binance_client import BinanceDataClient
from src.utils.logger import setup_logger

logger = setup_logger(__name__, log_file="optimize.log")


class OptunaOptimizer:
    """Optimize strategy parameters using Optuna."""

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "1h",
        lookback_days: int = 90,
    ) -> None:
        """
        Initialize optimizer.

        Args:
            symbol: Trading pair symbol
            timeframe: Candlestick timeframe
            lookback_days: Days of historical data for optimization
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback_days = lookback_days

        # Fetch data once for all trials
        logger.info(f"Fetching data for {symbol} ({timeframe})")
        client = BinanceDataClient(testnet=True)
        self.df = client.get_historical_klines(
            symbol=symbol,
            interval=timeframe,
            start_str=f"{lookback_days} days ago UTC",
            limit=1000,
        )
        logger.info(f"Data loaded: {len(self.df)} candles")

    def objective(self, trial: Trial) -> float:
        """
        Optuna objective function to maximize.

        Args:
            trial: Optuna trial object

        Returns:
            Metric to optimize (Sharpe Ratio)
        """
        # Suggest hyperparameters
        fast_window = trial.suggest_int("fast_window", 5, 30)
        slow_window = trial.suggest_int("slow_window", 20, 100)

        # Ensure fast < slow
        if fast_window >= slow_window:
            return -999.0  # Invalid configuration

        # Run backtest
        strategy = SMAStrategy(fast_window=fast_window, slow_window=slow_window)
        portfolio = strategy.backtest(self.df, initial_capital=10000.0)

        # Get Sharpe Ratio (or Total Return if Sharpe not available)
        stats = portfolio.stats()
        sharpe = stats.get("Sharpe Ratio", 0.0)

        # If Sharpe is NaN, use Total Return as fallback
        if pd.isna(sharpe):
            total_return = stats.get("Total Return [%]", 0.0)
            logger.debug(
                f"Trial {trial.number}: fast={fast_window}, slow={slow_window}, "
                f"Return={total_return:.2f}% (Sharpe N/A)"
            )
            return total_return / 100.0  # Normalize

        logger.debug(
            f"Trial {trial.number}: fast={fast_window}, slow={slow_window}, "
            f"Sharpe={sharpe:.3f}"
        )
        return sharpe

    def optimize(self, n_trials: int = 25, timeout: int = 300) -> dict[str, Any]:
        """
        Run optimization study.

        Args:
            n_trials: Number of trials to run
            timeout: Maximum time in seconds (optional)

        Returns:
            Dictionary with best parameters and results
        """
        logger.info(f"Starting optimization with {n_trials} trials")

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=42),
            pruner=optuna.pruners.MedianPruner(),
        )

        study.optimize(
            self.objective,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True,
        )

        # Save study results
        df_trials = study.trials_dataframe()
        output_file = ARTIFACTS_DIR / "optuna" / "study.csv"
        df_trials.to_csv(output_file, index=False)
        logger.info(f"Study results saved to {output_file}")

        # Get best parameters
        best_params = study.best_params
        best_value = study.best_value

        logger.info(f"Best Sharpe Ratio: {best_value:.3f}")
        logger.info(f"Best parameters: {best_params}")

        return {
            "best_params": best_params,
            "best_value": best_value,
            "n_trials": len(study.trials),
        }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Optimize strategy parameters with Optuna")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair symbol")
    parser.add_argument("--timeframe", type=str, default="1h", help="Candlestick timeframe")
    parser.add_argument("--lookback", type=int, default=90, help="Days of historical data")
    parser.add_argument("--trials", type=int, default=25, help="Number of optimization trials")
    parser.add_argument("--timeout", type=int, default=300, help="Max optimization time (seconds)")

    args = parser.parse_args()

    optimizer = OptunaOptimizer(
        symbol=args.symbol,
        timeframe=args.timeframe,
        lookback_days=args.lookback,
    )

    results = optimizer.optimize(n_trials=args.trials, timeout=args.timeout)

    # Print results
    print("\n" + "=" * 50)
    print("Optimization Results")
    print("=" * 50)
    print(f"Best Sharpe Ratio: {results['best_value']:.3f}")
    print(f"Best Parameters:")
    for param, value in results["best_params"].items():
        print(f"  {param}: {value}")
    print(f"Total Trials: {results['n_trials']}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
