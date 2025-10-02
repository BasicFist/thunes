"""Walk-forward validation with HMM regime detection.

Test Protocol:
1. Train HMM on Jul 1 - Aug 1, 2025 to detect market regimes
2. Optimize RSI parameters separately for each regime
3. Forward test on Aug 2 - Sep 1, 2025:
   - Detect which regime(s) August belongs to
   - Use regime-specific parameters

This tests whether regime-adaptive parameters solve parameter instability.
"""

from datetime import datetime

import numpy as np
import optuna
import pandas as pd

from src.backtest.rsi_strategy import RSIStrategy
from src.data.binance_client import BinanceDataClient
from src.models.regime import MarketRegimeDetector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def fetch_data_for_period(symbol: str, start_date: str, end_date: str, timeframe: str = "1h"):
    """Fetch data for specific date range."""
    client = BinanceDataClient(testnet=False)

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


def optimize_for_regime(
    df: pd.DataFrame, regime_mask: pd.Series, regime_id: int, n_trials: int = 15
) -> dict:
    """Optimize RSI parameters for specific regime."""
    # Filter data for this regime
    regime_df = df[regime_mask]

    if len(regime_df) < 50:
        logger.warning(
            f"Regime {regime_id} has only {len(regime_df)} samples, skipping optimization"
        )
        return None

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
            portfolio = strategy.backtest(regime_df, initial_capital=10000.0)
            stats = portfolio.stats()
            sharpe = stats.get("Sharpe Ratio", 0.0)

            if pd.isna(sharpe):
                total_return = stats.get("Total Return [%]", 0.0)
                return total_return / 100.0

            return sharpe
        except Exception as e:
            logger.warning(f"Backtest failed for regime {regime_id}: {e}")
            return -999.0

    sampler = optuna.samplers.TPESampler(multivariate=True, group=True, n_startup_trials=5, seed=42)

    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    return {
        "best_params": study.best_params,
        "best_sharpe": study.best_value,
        "n_samples": len(regime_df),
    }


def backtest_with_regime_switching(
    df: pd.DataFrame,
    regimes: np.ndarray,
    regime_params: dict,
) -> dict:
    """
    Backtest with regime-aware parameter switching.

    Args:
        df: OHLCV data
        regimes: Regime labels for each row
        regime_params: Dict mapping regime_id → RSI parameters

    Returns:
        Combined backtest results
    """
    total_return = 0.0
    total_trades = 0
    winning_trades = 0
    all_returns = []

    # Align regimes with dataframe (regimes may be shorter due to NaN dropping)
    min_len = min(len(df), len(regimes))
    df_aligned = df.iloc[:min_len].copy()
    regimes_aligned = regimes[:min_len]

    # Split by regime and backtest each segment
    for regime_id, params_dict in regime_params.items():
        if params_dict is None:
            continue

        regime_mask = regimes_aligned == regime_id
        regime_df = df_aligned[regime_mask]

        if len(regime_df) < 10:
            continue

        params = params_dict["best_params"]
        strategy = RSIStrategy(
            rsi_period=params["rsi_period"],
            oversold_threshold=params["oversold"],
            overbought_threshold=params["overbought"],
            stop_loss_pct=params["stop_loss"],
        )

        try:
            portfolio = strategy.backtest(regime_df, initial_capital=10000.0)
            stats = portfolio.stats()

            total_return += stats.get("Total Return [%]", 0.0)
            total_trades += stats.get("Total Trades", 0)

            win_rate = stats.get("Win Rate [%]", 0.0)
            trades_in_regime = stats.get("Total Trades", 0)
            winning_trades += int((win_rate / 100.0) * trades_in_regime)

            # Collect individual trade returns for Sharpe calculation
            trade_returns = portfolio.trades.records_readable["Return [%]"]
            all_returns.extend(trade_returns.values)

        except Exception as e:
            logger.warning(f"Backtest failed for regime {regime_id} segment: {e}")
            continue

    # Calculate aggregate statistics
    if len(all_returns) > 0:
        returns_series = pd.Series(all_returns)
        sharpe = (returns_series.mean() / returns_series.std()) if returns_series.std() > 0 else 0.0
    else:
        sharpe = 0.0

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

    return {
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "total_trades": total_trades,
        "win_rate": win_rate,
    }


def main():
    """Run HMM-based walk-forward validation."""
    symbol = "BTCUSDT"
    timeframe = "1h"

    print("\n" + "=" * 80)
    print("HMM REGIME-ADAPTIVE WALK-FORWARD VALIDATION")
    print("=" * 80)

    # Step 1: Fetch training data
    print("\n[1/6] Fetching training data (Jul 1 - Aug 1, 2025)...")
    train_df = fetch_data_for_period(symbol, "2025-07-01", "2025-08-01", timeframe)

    # Step 2: Train HMM on training data
    print("\n[2/6] Training HMM to detect market regimes...")
    returns = train_df["close"].pct_change()
    regime_detector = MarketRegimeDetector(n_states=2, random_state=42)
    regime_detector.fit(returns)

    # Predict regimes for training period
    train_regimes = regime_detector.predict(returns)

    # Analyze regime characteristics
    regime_stats = regime_detector.get_regime_statistics(returns, train_regimes)

    print("\n✓ HMM Training Complete:")
    for regime_id, stats in regime_stats.items():
        regime_type = "Bull/Low-Vol" if stats["mean_return"] > 0 else "Bear/High-Vol"
        print(f"  Regime {regime_id} ({regime_type}):")
        print(f"    Mean Return: {stats['mean_return']:.4f}")
        print(f"    Volatility: {stats['volatility']:.4f}")
        print(f"    Sharpe: {stats['sharpe']:.2f}")
        print(f"    Frequency: {stats['frequency']:.1%}")

    # Step 3: Optimize RSI parameters for each regime
    print("\n[3/6] Optimizing RSI parameters per regime...")

    # Align train_df with regimes (regimes may be shorter due to NaN)
    min_len = min(len(train_df), len(train_regimes))
    train_df_aligned = train_df.iloc[:min_len]

    regime_params = {}
    for regime_id in range(2):
        print(f"\n  Optimizing for Regime {regime_id}...")
        regime_mask = train_regimes == regime_id
        params = optimize_for_regime(train_df_aligned, regime_mask, regime_id, n_trials=15)

        if params is not None:
            regime_params[regime_id] = params
            print(f"    ✓ Best Sharpe: {params['best_sharpe']:.3f}")
            print(f"    ✓ RSI Period: {params['best_params']['rsi_period']}")
            print(f"    ✓ Oversold: {params['best_params']['oversold']:.1f}")
            print(f"    ✓ Overbought: {params['best_params']['overbought']:.1f}")

    # Step 4: Fetch test data
    print("\n[4/6] Fetching test data (Aug 2 - Sep 1, 2025)...")
    test_df = fetch_data_for_period(symbol, "2025-08-02", "2025-09-01", timeframe)

    # Step 5: Detect regimes in test period
    print("\n[5/6] Detecting regimes in test period...")
    test_returns = test_df["close"].pct_change()
    test_regimes = regime_detector.predict(test_returns)

    test_regime_stats = regime_detector.get_regime_statistics(test_returns, test_regimes)

    print("\n✓ Test Period Regime Distribution:")
    for regime_id, stats in test_regime_stats.items():
        print(f"  Regime {regime_id}: {stats['frequency']:.1%} of test period")

    # Step 6: Backtest with regime switching
    print("\n[6/6] Backtesting with regime-adaptive parameters...")
    results = backtest_with_regime_switching(test_df, test_regimes, regime_params)

    # Results summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    print("\nTraining Period (Jul 1 - Aug 1):")
    print(f"  Detected Regimes: {len(regime_params)}")
    for regime_id, params in regime_params.items():
        if params:
            print(f"  Regime {regime_id} Optimized Sharpe: {params['best_sharpe']:.3f}")

    print("\nForward Test (Aug 2 - Sep 1) with Regime Switching:")
    print(f"  Total Return: {results['total_return']:.2f}%")
    print(f"  Sharpe Ratio: {results['sharpe_ratio']:.3f}")
    print(f"  Win Rate: {results['win_rate']:.1f}%")
    print(f"  Total Trades: {results['total_trades']}")

    print("\n" + "=" * 80)
    print("DECISION TREE")
    print("=" * 80)

    sharpe = results["sharpe_ratio"]

    # Compare to static RSI walk-forward
    print("\n📊 Static RSI Walk-Forward (Reference):")
    print("  Training Sharpe: 4.15")
    print("  Forward Test Sharpe: -2.25 (FAILURE)")
    print("  Conclusion: Parameter instability\n")

    print("📊 HMM Regime-Adaptive Walk-Forward:")
    print("  Training: Optimized per regime")
    print(f"  Forward Test Sharpe: {sharpe:.2f}")

    if sharpe > 1.5:
        print(f"\n✓ SUCCESS: HMM Regime Detection WORKS (Sharpe {sharpe:.2f} > 1.5)")
        print("  → Regime-adaptive parameters solve parameter instability")
        print("  → Recommended: Deploy to paper trading with regime monitoring")
        print("  → Next Step: Integrate with PaperTrader (Phase 3.1)")
        decision = "SUCCESS"
    elif sharpe > 1.0:
        print(f"\n⚠ PARTIAL SUCCESS: Marginal improvement (Sharpe {sharpe:.2f} > 1.0)")
        print("  → Regime detection helps but not dramatically")
        print("  → Recommended: Deploy with strict monitoring OR try online learning")
        print("  → Next Step: 3-regime HMM OR River+ADWIN (12h)")
        decision = "PARTIAL"
    elif sharpe > 0.0:
        print(f"\n⚠ MARGINAL: Positive but weak (0.0 < Sharpe {sharpe:.2f} < 1.0)")
        print("  → Better than static (-2.25) but still weak")
        print("  → Recommended: Try online learning (River+ADWIN, 12h)")
        decision = "MARGINAL"
    else:
        print(f"\n✗ FAILURE: HMM also fails (Sharpe {sharpe:.2f} < 0.0)")
        print("  → Discrete regimes insufficient for crypto chaos")
        print("  → Recommended: Implement online learning (River+ADWIN, 12h)")
        print("  → Alternative: Abandon technical strategies, go full ML")
        decision = "FAILURE"

    print("=" * 80 + "\n")

    return {
        "regime_params": regime_params,
        "test_results": results,
        "decision": decision,
    }


if __name__ == "__main__":
    results = main()
