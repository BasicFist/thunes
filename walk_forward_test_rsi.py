"""Walk-forward validation test for RSI strategy.

Test Protocol:
1. Optimize RSI parameters on Jul 1 - Aug 1, 2025 (training period)
2. Forward test on Aug 2 - Sep 1, 2025 (out-of-sample test)
3. Compare to SMA walk-forward results

This determines if RSI has better parameter stability than SMA.
"""

from datetime import datetime

import optuna
import pandas as pd

from src.backtest.rsi_strategy import RSIStrategy
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
    """Optimize RSI parameters on given data."""

    def objective(trial):
        rsi_period = trial.suggest_int("rsi_period", 10, 20)
        oversold = trial.suggest_float("oversold", 25.0, 35.0)
        overbought = trial.suggest_float("overbought", 65.0, 75.0)
        stop_loss = trial.suggest_float("stop_loss", 2.0, 5.0)

        # Ensure overbought > oversold
        if overbought <= oversold:
            return -999.0

        strategy = RSIStrategy(
            rsi_period=rsi_period,
            oversold_threshold=oversold,
            overbought_threshold=overbought,
            stop_loss_pct=stop_loss,
        )
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


def backtest_with_params(
    df: pd.DataFrame, rsi_period: int, oversold: float, overbought: float, stop_loss: float
) -> dict:
    """Backtest with specific RSI parameters."""
    strategy = RSIStrategy(
        rsi_period=rsi_period,
        oversold_threshold=oversold,
        overbought_threshold=overbought,
        stop_loss_pct=stop_loss,
    )
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
    """Run walk-forward validation test for RSI."""
    symbol = "BTCUSDT"
    timeframe = "1h"

    print("\n" + "=" * 80)
    print("RSI WALK-FORWARD VALIDATION TEST")
    print("=" * 80)

    # Step 1: Optimize on Jul 1 - Aug 1, 2025
    print("\n[1/4] Fetching training data (Jul 1 - Aug 1, 2025)...")
    train_df = fetch_data_for_period(symbol, "2025-07-01", "2025-08-01", timeframe)

    print("\n[2/4] Optimizing RSI parameters on training period (20 trials)...")
    train_results = optimize_on_period(train_df, n_trials=20)

    print("\n✓ Training Optimization Complete:")
    print("  Best Parameters:")
    print(f"    RSI Period: {train_results['best_params']['rsi_period']}")
    print(f"    Oversold: {train_results['best_params']['oversold']:.1f}")
    print(f"    Overbought: {train_results['best_params']['overbought']:.1f}")
    print(f"    Stop-Loss: {train_results['best_params']['stop_loss']:.1f}%")
    print(f"  Training Sharpe: {train_results['best_sharpe']:.3f}")

    # Step 2: Forward test on Aug 2 - Sep 1, 2025
    print("\n[3/4] Fetching test data (Aug 2 - Sep 1, 2025)...")
    test_df = fetch_data_for_period(symbol, "2025-08-02", "2025-09-01", timeframe)

    print("\n[4/4] Forward testing with optimized parameters...")
    test_results = backtest_with_params(
        test_df,
        rsi_period=train_results["best_params"]["rsi_period"],
        oversold=train_results["best_params"]["oversold"],
        overbought=train_results["best_params"]["overbought"],
        stop_loss=train_results["best_params"]["stop_loss"],
    )

    # Results summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    print("\nTraining Period (Jul 1 - Aug 1):")
    print("  Optimized Parameters:")
    print(f"    RSI Period: {train_results['best_params']['rsi_period']}")
    print(f"    Oversold: {train_results['best_params']['oversold']:.1f}")
    print(f"    Overbought: {train_results['best_params']['overbought']:.1f}")
    print(f"    Stop-Loss: {train_results['best_params']['stop_loss']:.1f}%")
    print(f"  Training Sharpe: {train_results['best_sharpe']:.3f}")

    print("\nForward Test (Aug 2 - Sep 1):")
    print(f"  Total Return: {test_results['total_return']:.2f}%")
    print(f"  Sharpe Ratio: {test_results['sharpe_ratio']:.3f}")
    print(f"  Win Rate: {test_results['win_rate']:.1f}%")
    print(f"  Max Drawdown: {test_results['max_drawdown']:.2f}%")
    print(f"  Total Trades: {test_results['total_trades']}")

    print("\n" + "=" * 80)
    print("DECISION TREE & COMPARISON")
    print("=" * 80)

    sharpe = test_results["sharpe_ratio"]

    # Compare to SMA walk-forward results
    print("\n📊 SMA Walk-Forward Results (Reference):")
    print("  Training Sharpe: 2.14")
    print("  Forward Test Sharpe: -4.59 (CATASTROPHIC FAILURE)")
    print("  Conclusion: Parameter instability\n")

    print("📊 RSI Walk-Forward Results:")
    print(f"  Training Sharpe: {train_results['best_sharpe']:.2f}")
    print(f"  Forward Test Sharpe: {sharpe:.2f}")

    if sharpe > 1.5:
        print(f"\n✓ SCENARIO A: Strong Performance (Sharpe {sharpe:.2f} > 1.5)")
        print("  → RSI has BETTER parameter stability than SMA")
        print("  → Recommended: Implement rolling 30-day re-optimization")
        print("  → Next Step: Optimize on Aug-Oct period and deploy to paper trading")
        decision = "A"
    elif sharpe > 1.0:
        print(f"\n⚠ SCENARIO A-: Acceptable Performance (Sharpe {sharpe:.2f} > 1.0)")
        print("  → RSI has BETTER parameter stability than SMA")
        print("  → Marginal but positive forward test")
        print("  → Recommended: Optimize and deploy with strict monitoring")
        print("  → Next Step: Run multi-symbol validation before proceeding")
        decision = "A-"
    elif sharpe > 0.0:
        print(f"\n⚠ SCENARIO C: Marginal Performance (0.0 < Sharpe {sharpe:.2f} < 1.0)")
        print("  → RSI shows SOME stability (better than SMA's -4.59)")
        print("  → Not strong enough for confident deployment")
        print("  → Recommended: Try Bollinger Bands OR deploy with very strict limits")
        decision = "C"
    else:
        print(f"\n✗ SCENARIO B: Poor Performance (Sharpe {sharpe:.2f} < 0.0)")
        print("  → RSI also suffers from parameter instability")
        print("  → Both trend-following AND mean reversion fail walk-forward")
        print("  → Recommended: Implement Bollinger Bands as last baseline attempt")
        print("  → If Bollinger fails: Consider ML approach or abandon current paradigm")
        decision = "B"

    print("=" * 80 + "\n")

    return {
        "train_params": train_results["best_params"],
        "train_sharpe": train_results["best_sharpe"],
        "test_results": test_results,
        "decision": decision,
    }


if __name__ == "__main__":
    results = main()
