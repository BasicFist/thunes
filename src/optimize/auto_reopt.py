"""Automatic weekly re-optimization of strategy parameters.

Implements adaptive parameter management to handle crypto's continuous drift.
Re-optimizes on trailing 30 days every 7 days to keep parameters fresh.
"""

import json
from datetime import datetime
from typing import Any

import optuna
import pandas as pd

from src.backtest.rsi_strategy import RSIStrategy
from src.config import ARTIFACTS_DIR
from src.data.binance_client import BinanceDataClient
from src.utils.logger import setup_logger

logger = setup_logger(__name__, log_file="auto_reopt.log")


class WeeklyReoptimizer:
    """
    Automatically re-optimize strategy parameters weekly.

    Addresses the parameter drift problem identified in walk-forward validation:
    - SMA: Training Sharpe 2.14 → Forward -4.59
    - RSI: Training Sharpe 4.15 → Forward -2.25
    - HMM: Training Sharpe 3.90 → Forward 0.00

    Solution: Re-optimize frequently to adapt to continuous market evolution.
    """

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "1h",
        lookback_days: int = 30,
        n_trials: int = 25,
    ):
        """
        Initialize weekly re-optimizer.

        Args:
            symbol: Trading pair
            timeframe: Candlestick interval
            lookback_days: Days of historical data for optimization (default: 30)
            n_trials: Optuna optimization trials (default: 25)
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback_days = lookback_days
        self.n_trials = n_trials

        # Parameters file location
        self.params_file = ARTIFACTS_DIR / "optimize" / "current_parameters.json"
        self.params_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"WeeklyReoptimizer initialized: {symbol} {timeframe}, "
            f"lookback={lookback_days}d, trials={n_trials}"
        )

    def should_reoptimize(self) -> bool:
        """
        Check if re-optimization is needed based on last run time.

        Returns:
            True if 7+ days since last optimization
        """
        if not self.params_file.exists():
            logger.info("No previous parameters found, re-optimization needed")
            return True

        with open(self.params_file) as f:
            data = json.load(f)

        last_optimized = datetime.fromisoformat(data.get("optimized_at", "2000-01-01"))
        days_since = (datetime.now() - last_optimized).days

        if days_since >= 7:
            logger.info(f"Re-optimization needed ({days_since} days since last run)")
            return True

        logger.info(f"Re-optimization not needed ({days_since} days since last run)")
        return False

    def fetch_recent_data(self) -> pd.DataFrame:
        """
        Fetch trailing N days of market data.

        Returns:
            DataFrame with OHLCV data
        """
        client = BinanceDataClient(testnet=False)

        # Calculate required klines
        timeframe_hours = {"1h": 1, "4h": 4, "1d": 24}
        hours_per_candle = timeframe_hours.get(self.timeframe, 1)
        required_klines = int((self.lookback_days * 24) / hours_per_candle)

        df = client.get_historical_klines(
            symbol=self.symbol,
            interval=self.timeframe,
            start_str=f"{self.lookback_days} days ago UTC",
            limit=min(required_klines + 100, 1000),
        )

        logger.info(f"Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")
        return df

    def optimize_rsi_parameters(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Run Optuna optimization for RSI strategy.

        Args:
            df: Historical OHLCV data

        Returns:
            Dict with best parameters and metrics
        """

        def objective(trial):
            rsi_period = trial.suggest_int("rsi_period", 10, 20)
            oversold = trial.suggest_float("oversold", 25.0, 35.0)
            overbought = trial.suggest_float("overbought", 65.0, 75.0)
            stop_loss = trial.suggest_float("stop_loss", 2.0, 5.0)

            if overbought <= oversold:
                return -999.0

            strategy = RSIStrategy(
                rsi_period=rsi_period,
                oversold_threshold=oversold,
                overbought_threshold=overbought,
                stop_loss_pct=stop_loss,
            )

            try:
                portfolio = strategy.backtest(df, initial_capital=10000.0)
                stats = portfolio.stats()
                sharpe = stats.get("Sharpe Ratio", 0.0)

                if pd.isna(sharpe):
                    total_return = stats.get("Total Return [%]", 0.0)
                    return total_return / 100.0

                return sharpe
            except Exception as e:
                logger.warning(f"Backtest failed in trial: {e}")
                return -999.0

        sampler = optuna.samplers.TPESampler(
            multivariate=True,
            group=True,
            n_startup_trials=10,
            seed=42,
        )

        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(objective, n_trials=self.n_trials, show_progress_bar=True)

        best_params = study.best_params
        best_sharpe = study.best_value

        logger.info(f"Optimization complete: Sharpe={best_sharpe:.3f}, params={best_params}")

        return {
            "parameters": best_params,
            "sharpe_ratio": best_sharpe,
            "n_trials": len(study.trials),
            "optimization_data_period": f"{df.index[0]} to {df.index[-1]}",
        }

    def save_parameters(self, results: dict[str, Any]) -> None:
        """
        Save optimized parameters to file.

        Args:
            results: Optimization results with parameters and metrics
        """
        output = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "strategy": "RSI",
            "parameters": results["parameters"],
            "metrics": {
                "sharpe_ratio": results["sharpe_ratio"],
                "n_trials": results["n_trials"],
            },
            "optimized_at": datetime.now().isoformat(),
            "optimization_data_period": results["optimization_data_period"],
            "lookback_days": self.lookback_days,
        }

        with open(self.params_file, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"Parameters saved to {self.params_file}")

    def load_current_parameters(self) -> dict[str, Any]:
        """
        Load current optimized parameters from file.

        Returns:
            Dict with current parameters, or industry defaults if not found
        """
        if not self.params_file.exists():
            logger.warning("No parameters file found, using industry defaults")
            return {
                "parameters": {
                    "rsi_period": 14,
                    "oversold": 30.0,
                    "overbought": 70.0,
                    "stop_loss": 3.0,
                },
                "sharpe_ratio": None,
                "optimized_at": None,
            }

        with open(self.params_file) as f:
            data = json.load(f)

        return {
            "parameters": data["parameters"],
            "sharpe_ratio": data.get("metrics", {}).get("sharpe_ratio"),
            "optimized_at": data.get("optimized_at"),
        }

    def run_weekly_optimization(self, force: bool = False) -> dict[str, Any]:
        """
        Run weekly re-optimization if needed.

        Args:
            force: Force re-optimization even if not 7 days yet

        Returns:
            Dict with optimization results
        """
        if not force and not self.should_reoptimize():
            logger.info("Skipping optimization (not needed yet)")
            return self.load_current_parameters()

        logger.info("Starting weekly re-optimization...")

        # Fetch recent data
        df = self.fetch_recent_data()

        # Optimize
        results = self.optimize_rsi_parameters(df)

        # Save
        self.save_parameters(results)

        logger.info("Weekly re-optimization complete")

        return results


def main():
    """CLI entry point for manual testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Weekly re-optimization of strategy parameters")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading pair")
    parser.add_argument("--timeframe", type=str, default="1h", help="Candlestick interval")
    parser.add_argument("--lookback", type=int, default=30, help="Days of historical data")
    parser.add_argument("--trials", type=int, default=25, help="Optuna trials")
    parser.add_argument("--force", action="store_true", help="Force re-optimization")

    args = parser.parse_args()

    reoptimizer = WeeklyReoptimizer(
        symbol=args.symbol,
        timeframe=args.timeframe,
        lookback_days=args.lookback,
        n_trials=args.trials,
    )

    results = reoptimizer.run_weekly_optimization(force=args.force)

    print("\n" + "=" * 60)
    print("WEEKLY RE-OPTIMIZATION RESULTS")
    print("=" * 60)
    print(f"Symbol: {args.symbol}")
    print(f"Parameters: {results['parameters']}")
    print(f"Sharpe Ratio: {results.get('sharpe_ratio', 'N/A')}")
    print(f"Optimized At: {results.get('optimized_at', 'N/A')}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
