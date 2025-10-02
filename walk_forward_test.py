"""Walk-forward validation test.

Test Protocol:
1. Optimize hyperparameters on Jul 1 - Aug 1, 2025 (training period)
2. Forward test on Aug 2 - Sep 1, 2025 (out-of-sample test)
3. Compare to original optimization (Aug 23 - Oct 2)

This determines if rolling re-optimization can solve regime overfitting.
"""

from datetime import datetime

import optuna
import pandas as pd

from src.backtest.strategy import SMAStrategy
from src.data.binance_client import BinanceDataClient
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def fetch_data_for_period(symbol: str, start_date: str, end_date: str, timeframe: str = "1h"):
    """Fetch data for specific date range."""
    client = BinanceDataClient(testnet=False)

    # Calculate number of candles needed
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end_dt - start_dt).days

    timeframe_hours = {"1h": 1, "4h": 4, "1d": 24}
    hours_per_candle = timeframe_hours.get(timeframe, 1)
    required_klines = int((days * 24) / hours_per_candle)

    df = client.get_historical_klines(
        symbol=symbol,
        interval=timeframe,
        start_str=start_date,
        end_str=end_date,
        limit=min(required_klines + 100, 1000),
    )

    logger.info(f"Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    return df


def optimize_on_period(df: pd.DataFrame, n_trials: int = 20) -> dict:
    """Optimize SMA parameters on given data."""

    def objective(trial):
        fast_window = trial.suggest_int("fast_window", 5, 30)
        slow_window = trial.suggest_int("slow_window", 20, 100)

        if fast_window >= slow_window:
            return -999.0

        strategy = SMAStrategy(fast_window=fast_window, slow_window=slow_window)
        portfolio = strategy.backtest(df, initial_capital=10000.0)
        stats = portfolio.stats()
        sharpe = stats.get("Sharpe Ratio", 0.0)

        if pd.isna(sharpe):
            total_return = stats.get("Total Return [%]", 0.0)
            return total_return / 100.0

        return sharpe

    sampler = optuna.samplers.TPESampler(
        multivariate=True,
        group=True,
        n_startup_trials=10,
        seed=42,
    )

    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    return {
        "best_params": study.best_params,
        "best_sharpe": study.best_value,
    }


def backtest_with_params(df: pd.DataFrame, fast_window: int, slow_window: int) -> dict:
    """Backtest with specific parameters."""
    strategy = SMAStrategy(fast_window=fast_window, slow_window=slow_window)
    portfolio = strategy.backtest(df, initial_capital=10000.0)
    stats = portfolio.stats()

    return {
        "total_return": stats.get("Total Return [%]", 0.0),
        "sharpe_ratio": stats.get("Sharpe Ratio", 0.0),
        "win_rate": stats.get("Win Rate [%]", 0.0),
        "max_drawdown": stats.get("Max Drawdown [%]", 0.0),
        "total_trades": stats.get("Total Trades", 0),
    }


def main():
    """Run walk-forward validation test."""
    symbol = "BTCUSDT"
    timeframe = "1h"

    print("\n" + "=" * 80)
    print("WALK-FORWARD VALIDATION TEST")
    print("=" * 80)

    # Step 1: Optimize on Jul 1 - Aug 1, 2025
    print("\n[1/4] Fetching training data (Jul 1 - Aug 1, 2025)...")
    train_df = fetch_data_for_period(symbol, "2025-07-01", "2025-08-01", timeframe)

    print("\n[2/4] Optimizing on training period (20 trials)...")
    train_results = optimize_on_period(train_df, n_trials=20)

    print("\n✓ Training Optimization Complete:")
    print(
        f"  Best Parameters: fast={train_results['best_params']['fast_window']}, "
        f"slow={train_results['best_params']['slow_window']}"
    )
    print(f"  Training Sharpe: {train_results['best_sharpe']:.3f}")

    # Step 2: Forward test on Aug 2 - Sep 1, 2025
    print("\n[3/4] Fetching test data (Aug 2 - Sep 1, 2025)...")
    test_df = fetch_data_for_period(symbol, "2025-08-02", "2025-09-01", timeframe)

    print("\n[4/4] Forward testing with optimized parameters...")
    test_results = backtest_with_params(
        test_df,
        fast_window=train_results["best_params"]["fast_window"],
        slow_window=train_results["best_params"]["slow_window"],
    )

    # Step 3: Compare to original optimization (for reference)
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    print("\nTraining Period (Jul 1 - Aug 1):")
    print(
        f"  Optimized Parameters: fast={train_results['best_params']['fast_window']}, "
        f"slow={train_results['best_params']['slow_window']}"
    )
    print(f"  Training Sharpe: {train_results['best_sharpe']:.3f}")

    print("\nForward Test (Aug 2 - Sep 1):")
    print(f"  Total Return: {test_results['total_return']:.2f}%")
    print(f"  Sharpe Ratio: {test_results['sharpe_ratio']:.3f}")
    print(f"  Win Rate: {test_results['win_rate']:.1f}%")
    print(f"  Max Drawdown: {test_results['max_drawdown']:.2f}%")
    print(f"  Total Trades: {test_results['total_trades']}")

    print("\n" + "=" * 80)
    print("DECISION TREE")
    print("=" * 80)

    sharpe = test_results["sharpe_ratio"]

    if sharpe > 1.5:
        print(f"\n✓ SCENARIO A: Strong Performance (Sharpe {sharpe:.2f} > 1.5)")
        print("  → Walk-forward optimization WORKS")
        print("  → Recommended: Implement rolling 30-day re-optimization")
        print("  → Next Step: Create src/optimize/walk_forward.py (2-3 hours)")
        decision = "A"
    elif sharpe < 0.5:
        print(f"\n✗ SCENARIO B: Poor Performance (Sharpe {sharpe:.2f} < 0.5)")
        print("  → SMA strategy may be fundamentally flawed")
        print("  → Recommended: Try alternative strategies (RSI, Bollinger Bands)")
        print("  → Next Step: Implement and test alternative strategy (4-6 hours)")
        decision = "B"
    else:
        print(f"\n⚠ SCENARIO C: Mixed Performance (0.5 ≤ Sharpe {sharpe:.2f} ≤ 1.5)")
        print("  → Results are inconclusive")
        print("  → Recommended: Deploy to paper trading with strict monitoring")
        print("  → Next Step: Implement Phase 2.1 Telegram alerts first")
        decision = "C"

    print("=" * 80 + "\n")

    return {
        "train_params": train_results["best_params"],
        "train_sharpe": train_results["best_sharpe"],
        "test_results": test_results,
        "decision": decision,
    }


if __name__ == "__main__":
    results = main()
