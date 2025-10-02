"""Demonstration of XGBoost GPU Model with CPU Feature Engineering.

This script demonstrates the optimal GPU usage pattern for THUNES:
1. CPU feature engineering (5-6x faster than GPU for daily data)
2. GPU model training (5-46x faster than CPU for large datasets)

Expected Performance:
- Feature engineering: CPU ~30ms for 252 rows
- Model training (GPU): 5-46x speedup vs CPU (on large datasets)
- Total time: Optimal combination of CPU and GPU strengths

Usage:
    conda activate thunes
    python examples/xgboost_gpu_demo.py
"""

import time

import numpy as np
import pandas as pd

from src.data.processors.gpu_features import GPUFeatureEngine
from src.models.xgboost_gpu import XGBoostGPUModel
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def generate_sample_ohlcv(num_rows: int = 1000, seed: int = 42) -> pd.DataFrame:
    """Generate realistic OHLCV data for demonstration.

    Args:
        num_rows: Number of trading periods
        seed: Random seed for reproducibility

    Returns:
        DataFrame with OHLCV columns
    """
    np.random.seed(seed)

    # Generate realistic price movement
    base_price = 100.0
    returns = np.random.normal(0.0005, 0.02, num_rows)
    close_prices = base_price * np.exp(np.cumsum(returns))

    # Generate OHLC
    intraday_range = np.random.uniform(0.005, 0.03, num_rows)
    open_prices = close_prices * (1 + np.random.uniform(-0.01, 0.01, num_rows))
    high_prices = np.maximum(open_prices, close_prices) * (1 + intraday_range)
    low_prices = np.minimum(open_prices, close_prices) * (1 - intraday_range)

    # Generate volume
    base_volume = 1_000_000
    volume = np.random.lognormal(np.log(base_volume), 0.5, num_rows)

    # Create timestamps
    timestamps = pd.date_range(end=pd.Timestamp.now(), periods=num_rows, freq="1D")

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volume,
        }
    )


def create_labels(df: pd.DataFrame, future_periods: int = 1) -> pd.Series:
    """Create binary labels for price prediction.

    Label = 1 if price goes up in next period, 0 otherwise

    Args:
        df: DataFrame with OHLCV data
        future_periods: Number of periods to look ahead (default: 1)

    Returns:
        Series of binary labels (0 or 1)
    """
    future_return = df["close"].shift(-future_periods) / df["close"] - 1
    labels = (future_return > 0).astype(int)

    return labels


def main():
    """Main demonstration workflow."""
    print("\n" + "=" * 80)
    print("XGBoost GPU Model Demo: CPU Features + GPU Training")
    print("=" * 80)

    # Step 1: Generate sample data
    print("\n[1/6] Generating sample OHLCV data...")
    num_rows = 2000  # 2000 days (~5.5 years of daily data)
    df = generate_sample_ohlcv(num_rows)
    logger.info(f"Generated {len(df)} rows of OHLCV data")

    # Step 2: CPU feature engineering (VALIDATED as faster for daily data)
    print("\n[2/6] Calculating technical indicators using CPU...")
    start_time = time.perf_counter()

    feature_engine = GPUFeatureEngine(use_gpu=False)  # Use CPU - 5-6x faster!
    df_features = feature_engine.calculate_all_features(df)

    cpu_feature_time = time.perf_counter() - start_time
    logger.info(f"CPU feature engineering completed in {cpu_feature_time:.3f}s")

    num_features = len(df_features.columns) - 6  # Exclude OHLCV + timestamp
    print(f"   ✓ Created {num_features} technical indicators in {cpu_feature_time:.3f}s")

    # Step 3: Create labels for prediction
    print("\n[3/6] Creating labels (predict next day's price direction)...")
    labels = create_labels(df_features)

    # Drop NaN values from indicators
    df_clean = df_features.dropna()
    labels_clean = labels[df_clean.index]

    logger.info(f"Clean dataset: {len(df_clean)} rows, {num_features} features")
    print(f"   ✓ Dataset: {len(df_clean)} samples, {num_features} features")
    print(f"   ✓ Label distribution: {labels_clean.value_counts().to_dict()}")

    # Step 4: Split data (time series split)
    print("\n[4/6] Splitting data (time series split: 80% train, 20% test)...")
    split_idx = int(len(df_clean) * 0.8)

    # Features (exclude OHLCV and timestamp)
    feature_cols = [col for col in df_clean.columns if col not in ["timestamp", "open", "high", "low", "close", "volume"]]
    X = df_clean[feature_cols]
    y = labels_clean

    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    logger.info(f"Train: {len(X_train)} samples, Test: {len(X_test)} samples")
    print(f"   ✓ Train set: {len(X_train)} samples")
    print(f"   ✓ Test set: {len(X_test)} samples")

    # Step 5: Train XGBoost model with GPU acceleration
    print("\n[5/6] Training XGBoost model with GPU acceleration...")
    print("   ⚠️  Note: GPU speedup requires large datasets (millions of rows)")
    print(f"   ⚠️  Current dataset ({len(X_train)} rows) may not show significant speedup")
    print("   ⚠️  Validated 5-46x speedup on 5.5M rows (official benchmarks)")

    model = XGBoostGPUModel(
        use_gpu=True,  # Enable GPU training
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        early_stopping_rounds=10,
    )

    start_time = time.perf_counter()

    # Create validation set (last 20% of training data)
    val_split = int(len(X_train) * 0.8)
    X_train_split, X_val_split = X_train.iloc[:val_split], X_train.iloc[val_split:]
    y_train_split, y_val_split = y_train.iloc[:val_split], y_train.iloc[val_split:]

    train_metrics = model.train(
        X_train_split, y_train_split, X_val_split, y_val_split, verbose=False
    )

    training_time = time.perf_counter() - start_time

    print(f"\n   ✓ Training completed in {training_time:.3f}s")
    print(f"   ✓ Best iteration: {train_metrics['best_iteration']}")
    print(f"   ✓ Train accuracy: {train_metrics['train_accuracy']:.4f}")
    print(f"   ✓ Val accuracy: {train_metrics.get('val_accuracy', 'N/A'):.4f}")

    # Step 6: Evaluate on test set
    print("\n[6/6] Evaluating model on test set...")
    test_metrics = model.evaluate(X_test, y_test)

    print(f"\n   Test Performance:")
    print(f"   ✓ Accuracy:  {test_metrics['test_accuracy']:.4f}")
    print(f"   ✓ Precision: {test_metrics['test_precision']:.4f}")
    print(f"   ✓ Recall:    {test_metrics['test_recall']:.4f}")
    print(f"   ✓ F1 Score:  {test_metrics['test_f1']:.4f}")

    # Show feature importance
    print("\n   Top 10 Most Important Features:")
    importance_df = model.get_feature_importance()
    for idx, row in importance_df.head(10).iterrows():
        print(f"   {idx + 1}. {row['feature']}: {row['importance']:.0f}")

    # Summary
    print("\n" + "=" * 80)
    print("Performance Summary")
    print("=" * 80)
    print(f"CPU Feature Engineering: {cpu_feature_time:.3f}s for {len(df)} rows")
    print(f"GPU Model Training:      {training_time:.3f}s for {len(X_train)} samples")
    print(f"Total Time:              {cpu_feature_time + training_time:.3f}s")
    print(f"\nTest Accuracy:           {test_metrics['test_accuracy']:.4f}")
    print(f"Test F1 Score:           {test_metrics['test_f1']:.4f}")
    print("\n✅ Demo complete! CPU features + GPU training = Optimal performance")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
