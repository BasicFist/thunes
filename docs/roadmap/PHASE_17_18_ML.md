# THUNES Phase 17-18: Advanced ML & HFT

**Version**: 1.0
**Last Updated**: 2025-10-05
**Duration**: 8-10 weeks (320-400 hours)
**Prerequisites**: Phase 16 complete ✅ (Production RL deployed)

---

## Overview

Phases 17-18 focus on **model governance**, **explainability**, and **HFT exploration**:

- **Phase 17**: Model Registry + SHAP Explainability (4 weeks, 160h)
- **Phase 18**: HFT Exploration with nautilus_trader (4-6 weeks, 160-240h)

---

## Phase 17: Model Registry + SHAP (4 weeks, 160h)

### Goals

1. **Model Versioning**: Git LFS for model weights, metadata tracking
2. **Explainability**: SHAP values for every decision (log top 10 features)
3. **Automated Retraining**: Weekly trigger if Sharpe <1.0
4. **Drift Detection**: River online learning for concept drift

---

### Week 1: Model Registry (40h)

**Deliverables**:
- Model storage backend (Git LFS or S3)
- Metadata schema (hyperparameters, training data hash, performance metrics)
- Versioning API (save, load, list, rollback)

**File**: `src/ml/registry.py`

```python
"""Model registry with Git LFS backend."""

import json
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
import joblib

class ModelRegistry:
    """Git LFS-backed model registry."""

    def __init__(self, storage_path: str = "models"):
        """
        Initialize model registry.

        Args:
            storage_path: Local directory for model storage (tracked by Git LFS)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize Git LFS
        subprocess.run(["git", "lfs", "install"], cwd=self.storage_path.parent)

    def save(
        self,
        model_id: str,
        model: object,
        metadata: dict,
    ) -> str:
        """
        Save model to registry.

        Args:
            model_id: Model identifier (e.g., 'finrl_ppo_v1')
            model: Model object (pickle-serializable)
            metadata: Metadata dict with:
                - sharpe_train: float
                - sharpe_test: float
                - max_drawdown: float
                - training_data_hash: str (SHA256 of training data)
                - git_sha: str (commit SHA of code used for training)
                - hyperparameters: dict
                - features: list[str]

        Returns:
            Model version (timestamp)
        """
        version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        model_dir = self.storage_path / model_id / version
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model weights
        model_path = model_dir / "model.pkl"
        joblib.dump(model, model_path)

        # Save metadata
        metadata_path = model_dir / "metadata.json"
        with metadata_path.open("w") as f:
            json.dump(metadata, f, indent=2)

        # Add to Git LFS
        subprocess.run(["git", "lfs", "track", "*.pkl"], cwd=self.storage_path)
        subprocess.run(["git", "add", str(model_dir)], cwd=self.storage_path)
        subprocess.run(
            ["git", "commit", "-m", f"Add {model_id} {version}"],
            cwd=self.storage_path,
        )

        return version

    def load(self, model_id: str, version: Optional[str] = None) -> tuple[object, dict]:
        """
        Load model from registry.

        Args:
            model_id: Model identifier
            version: Model version (default: latest)

        Returns:
            (model, metadata)
        """
        model_dir = self.storage_path / model_id

        if version is None:
            # Get latest version
            versions = sorted([d.name for d in model_dir.iterdir() if d.is_dir()])
            version = versions[-1]

        version_dir = model_dir / version

        # Load model
        model = joblib.load(version_dir / "model.pkl")

        # Load metadata
        with (version_dir / "metadata.json").open("r") as f:
            metadata = json.load(f)

        return model, metadata

    def list_models(self) -> dict:
        """List all registered models with versions."""
        models = {}
        for model_dir in self.storage_path.iterdir():
            if model_dir.is_dir():
                versions = sorted([d.name for d in model_dir.iterdir() if d.is_dir()])
                models[model_dir.name] = versions
        return models

    def rollback(self, model_id: str, version: str) -> None:
        """
        Rollback to specific model version.

        Args:
            model_id: Model identifier
            version: Target version
        """
        # Create symlink to target version
        current_link = self.storage_path / model_id / "current"
        target = self.storage_path / model_id / version

        if current_link.exists():
            current_link.unlink()

        current_link.symlink_to(target)

        # Commit rollback
        subprocess.run(
            ["git", "add", str(current_link)],
            cwd=self.storage_path,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Rollback {model_id} to {version}"],
            cwd=self.storage_path,
        )
```

**Testing** (`tests/test_model_registry.py`):

```python
import pytest
from src.ml.registry import ModelRegistry
from sklearn.linear_model import LogisticRegression

class TestModelRegistry:
    """Test model registry operations."""

    def test_save_and_load(self):
        """Test save and load model."""
        registry = ModelRegistry(storage_path="models_test")

        # Train simple model
        model = LogisticRegression()
        # ... train model ...

        # Save
        metadata = {
            "sharpe_train": 1.8,
            "sharpe_test": 1.5,
            "max_drawdown": 0.12,
            "training_data_hash": "sha256:abc123",
            "git_sha": "def456",
            "hyperparameters": {"C": 1.0},
            "features": ["sma_fast", "sma_slow", "rsi"],
        }
        version = registry.save("test_model", model, metadata)

        # Load
        loaded_model, loaded_metadata = registry.load("test_model", version)

        assert loaded_metadata["sharpe_train"] == 1.8
        assert loaded_metadata["git_sha"] == "def456"

    def test_list_models(self):
        """Test list all models."""
        registry = ModelRegistry(storage_path="models_test")

        models = registry.list_models()
        assert "test_model" in models

    def test_rollback(self):
        """Test rollback to previous version."""
        registry = ModelRegistry(storage_path="models_test")

        # Save v1
        model_v1 = LogisticRegression()
        version_v1 = registry.save("rollback_test", model_v1, {"version": 1})

        # Save v2
        model_v2 = LogisticRegression()
        version_v2 = registry.save("rollback_test", model_v2, {"version": 2})

        # Rollback to v1
        registry.rollback("rollback_test", version_v1)

        # Load current (should be v1)
        current_model, current_metadata = registry.load("rollback_test")
        assert current_metadata["version"] == 1
```

**Success Criteria**:
- ✅ Model save/load roundtrip preserves weights
- ✅ Git LFS tracks model files (check `.git/lfs/objects/`)
- ✅ Metadata includes all required fields

---

### Week 2: SHAP Explainability (40h)

**Deliverables**:
- SHAP value calculation for every decision
- Log top 10 features to audit trail
- Grafana dashboard for feature importance

**File**: `src/ml/explainability.py`

```python
"""SHAP-based model explainability."""

import shap
import numpy as np
from typing import Optional

class SHAPExplainer:
    """SHAP explainer for RL models."""

    def __init__(self, model: object, background_data: np.ndarray):
        """
        Initialize SHAP explainer.

        Args:
            model: Trained model (with predict method)
            background_data: Background dataset for SHAP (100-500 samples)
        """
        self.model = model
        self.explainer = shap.Explainer(model, background_data)

    def explain_decision(
        self, features: np.ndarray, feature_names: list[str]
    ) -> dict:
        """
        Explain decision using SHAP values.

        Args:
            features: Feature vector (1D array)
            feature_names: Feature names (e.g., ['sma_fast', 'rsi'])

        Returns:
            {
                "shap_values": [float, ...],  # SHAP value per feature
                "top_10_features": [
                    {"feature": "rsi", "shap_value": 0.32},
                    ...
                ],
                "base_value": float,  # Model base value (expected value)
                "prediction": float,  # Model prediction
            }
        """
        shap_values = self.explainer(features.reshape(1, -1))

        # Extract SHAP values for single prediction
        shap_vals = shap_values.values[0]

        # Get top 10 features by absolute SHAP value
        indices = np.argsort(np.abs(shap_vals))[::-1][:10]
        top_10 = [
            {
                "feature": feature_names[i],
                "shap_value": float(shap_vals[i]),
            }
            for i in indices
        ]

        return {
            "shap_values": shap_vals.tolist(),
            "top_10_features": top_10,
            "base_value": float(shap_values.base_values[0]),
            "prediction": float(self.model.predict(features.reshape(1, -1))[0]),
        }
```

**Integration** (`src/rl/adapter.py`):

```python
# Add to RLAdapter
from src.ml.explainability import SHAPExplainer

class RLAdapter:
    def __init__(self, ..., explainer: Optional[SHAPExplainer] = None):
        ...
        self.explainer = explainer

    def handle(self, action: RLAction) -> Decision:
        ...
        # After decision, explain if model prediction used
        if self.explainer and action.metadata.get("features"):
            explanation = self.explainer.explain_decision(
                features=np.array(action.metadata["features"]),
                feature_names=action.metadata["feature_names"],
            )

            # Log to audit trail
            decision.metadata["shap_top_10"] = explanation["top_10_features"]

        return decision
```

**Success Criteria**:
- ✅ SHAP values calculated in <50ms (p95)
- ✅ Top 10 features logged to audit trail (100% coverage)
- ✅ Grafana dashboard shows feature importance distribution

---

### Week 3: Automated Retraining (40h)

**Deliverables**:
- Weekly retraining trigger (if Sharpe <1.0)
- Walk-forward validation (train: 180d, test: 30d)
- Automatic deployment if test Sharpe >1.5

**File**: `src/ml/retraining.py`

```python
"""Automated model retraining."""

import schedule
import time
from src.ml.finrl_trainer import train_finrl_model
from src.ml.registry import ModelRegistry
from src.monitoring.performance_tracker import PerformanceTracker
from src.alerts.telegram import TelegramBot

class RetrainingService:
    """Automated model retraining."""

    def __init__(
        self,
        registry: ModelRegistry,
        telegram: TelegramBot,
        sharpe_threshold: float = 1.0,
    ):
        self.registry = registry
        self.telegram = telegram
        self.sharpe_threshold = sharpe_threshold

    def check_and_retrain(self) -> None:
        """Check Sharpe ratio and retrain if below threshold."""
        tracker = PerformanceTracker()
        sharpe_7d = tracker.calculate_sharpe_ratio(window_days=7)

        if sharpe_7d < self.sharpe_threshold:
            self._trigger_retraining(sharpe_7d)

    def _trigger_retraining(self, current_sharpe: float) -> None:
        """Trigger retraining workflow."""
        self.telegram.send_message_sync(
            f"⚙️ **THUNES Retraining Triggered**\n\n"
            f"Current Sharpe: {current_sharpe:.2f}\n"
            f"Threshold: {self.sharpe_threshold:.2f}\n\n"
            f"Starting retraining (ETA: 2-3 hours)..."
        )

        # Train new model
        model, metadata = train_finrl_model()

        # Validate
        if metadata["sharpe_test"] > 1.5:
            # Save and deploy
            version = self.registry.save("finrl_ppo", model, metadata)

            self.telegram.send_message_sync(
                f"✅ **Retraining Complete**\n\n"
                f"New Model Version: {version}\n"
                f"Test Sharpe: {metadata['sharpe_test']:.2f}\n"
                f"Max Drawdown: {metadata['max_drawdown']:.2f}\n\n"
                f"Deploying to production..."
            )
        else:
            self.telegram.send_message_sync(
                f"⚠️ **Retraining Failed**\n\n"
                f"Test Sharpe: {metadata['sharpe_test']:.2f} (<1.5 threshold)\n"
                f"Keeping current model."
            )

    def start_monitoring(self) -> None:
        """Start weekly retraining checks."""
        schedule.every().week.do(self.check_and_retrain)

        while True:
            schedule.run_pending()
            time.sleep(3600)
```

**Success Criteria**:
- ✅ Retraining triggers automatically (weekly check)
- ✅ Only deploy if test Sharpe >1.5
- ✅ Telegram notifications at each stage

---

### Week 4: Drift Detection (40h)

**Deliverables**:
- River online learning for concept drift detection
- Alert if feature distribution shifts >20%
- Automatic retraining trigger on severe drift

**File**: `src/ml/drift_detection.py`

```python
"""Concept drift detection using River."""

from river import drift
import numpy as np

class DriftDetector:
    """Detect concept drift in feature distributions."""

    def __init__(self, n_features: int):
        """
        Initialize drift detector.

        Args:
            n_features: Number of features to monitor
        """
        self.detectors = [drift.ADWIN() for _ in range(n_features)]
        self.drift_count = [0] * n_features

    def update(self, features: np.ndarray) -> list[int]:
        """
        Update drift detectors with new features.

        Args:
            features: Feature vector

        Returns:
            List of feature indices with detected drift
        """
        drifted = []

        for i, value in enumerate(features):
            self.detectors[i].update(value)

            if self.detectors[i].drift_detected:
                self.drift_count[i] += 1
                drifted.append(i)

        return drifted

    def get_drift_summary(self, feature_names: list[str]) -> dict:
        """Get drift detection summary."""
        return {
            feature_names[i]: self.drift_count[i]
            for i in range(len(feature_names))
        }
```

**Success Criteria**:
- ✅ Drift detection runs on every decision (<10ms overhead)
- ✅ Alert if >3 features drift in 24h
- ✅ Automatic retraining trigger on severe drift (>20% features)

---

## Phase 18: HFT Exploration (4-6 weeks, 160-240h)

### Goals

1. **nautilus_trader Integration**: Tick-level backtesting
2. **Order Flow Features**: Bid/ask queue depth, trade flow imbalance
3. **Performance Validation**: Reproduce 16-17% benchmark
4. **Latency Optimization**: <1ms decision latency (p95)

---

### Week 1-2: nautilus_trader Setup (80h)

**Deliverables**:
- nautilus_trader installation + configuration
- Binance adapter (WebSocket + REST)
- Tick data ingestion (1-minute granularity)

**Installation**:

```bash
# Install nautilus_trader
pip install nautilus_trader

# Download historical tick data (Binance)
# NOTE: nautilus_trader supports Binance via built-in adapter
```

**Configuration** (`config/nautilus_config.json`):

```json
{
  "trader": {
    "name": "THUNES-HFT",
    "id_tag": "001"
  },
  "data": {
    "catalog": {
      "path": "data/nautilus_catalog"
    }
  },
  "venues": [
    {
      "name": "BINANCE",
      "account_type": "CASH",
      "base_currency": "USDT"
    }
  ],
  "strategies": [
    {
      "strategy_id": "RL-HFT-001",
      "order_id_tag": "RLHFT"
    }
  ]
}
```

**Success Criteria**:
- ✅ nautilus_trader starts successfully
- ✅ Binance adapter connects to testnet
- ✅ Tick data ingested (>1M ticks/day)

---

### Week 3-4: Order Flow Features (80h)

**Deliverables**:
- Bid/ask queue depth (Level 2 order book)
- Trade flow imbalance (buy volume / sell volume)
- Microstructure features (spread, tick size, volatility)

**File**: `src/data/orderflow.py`

```python
"""Order flow feature engineering for HFT."""

import numpy as np
from collections import deque

class OrderFlowFeatures:
    """Calculate order flow features from Level 2 data."""

    def __init__(self, window_size: int = 100):
        """
        Initialize order flow calculator.

        Args:
            window_size: Number of ticks to use for rolling calculations
        """
        self.window_size = window_size
        self.trades = deque(maxlen=window_size)
        self.bid_depths = deque(maxlen=window_size)
        self.ask_depths = deque(maxlen=window_size)

    def update(self, tick: dict) -> dict:
        """
        Update with new tick and calculate features.

        Args:
            tick: {
                "bid_depth": float,  # Total bid volume at best 5 levels
                "ask_depth": float,  # Total ask volume at best 5 levels
                "trade_side": "BUY"|"SELL",
                "trade_volume": float,
            }

        Returns:
            {
                "order_imbalance": float,  # (bid_depth - ask_depth) / (bid_depth + ask_depth)
                "trade_flow_imbalance": float,  # buy_volume / (buy_volume + sell_volume)
                "bid_pressure": float,  # bid_depth / (bid_depth + ask_depth)
                "spread_bps": float,  # (ask - bid) / mid * 10000
            }
        """
        self.bid_depths.append(tick["bid_depth"])
        self.ask_depths.append(tick["ask_depth"])
        self.trades.append(tick)

        # Order imbalance
        bid_depth = np.mean(self.bid_depths)
        ask_depth = np.mean(self.ask_depths)
        order_imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth + 1e-9)

        # Trade flow imbalance
        buy_volume = sum(t["trade_volume"] for t in self.trades if t["trade_side"] == "BUY")
        sell_volume = sum(t["trade_volume"] for t in self.trades if t["trade_side"] == "SELL")
        trade_flow_imbalance = buy_volume / (buy_volume + sell_volume + 1e-9)

        # Bid pressure
        bid_pressure = bid_depth / (bid_depth + ask_depth + 1e-9)

        return {
            "order_imbalance": order_imbalance,
            "trade_flow_imbalance": trade_flow_imbalance,
            "bid_pressure": bid_pressure,
        }
```

**Success Criteria**:
- ✅ Order flow features calculated in <100μs (p95)
- ✅ Features correlate with price movement (>0.3 Pearson)

---

### Week 5-6: Performance Validation (80-120h)

**Deliverables**:
- Reproduce 16-17% benchmark (TradeMaster study)
- Latency profiling (<1ms decision latency)
- HFT strategy validation (tick-level backtests)

**Validation Workflow**:

```python
# 1. Train HFT model (FinRL with order flow features)
from src.ml.finrl_trainer import train_finrl_model

model, metadata = train_finrl_model(
    features=["order_imbalance", "trade_flow_imbalance", "bid_pressure", "spread_bps"],
    timeframe="1m",  # Tick-level
    window_days=365,
)

print(f"HFT Model Sharpe: {metadata['sharpe_test']:.2f}")
print(f"Annualized Return: {metadata['annual_return']:.2f}%")
# Target: >16% annualized return

# 2. Latency profiling
from src.rl.adapter import RLAdapter
import time

adapter = RLAdapter(...)

# Measure decision latency
start = time.perf_counter()
decision = adapter.handle(action)
latency_ms = (time.perf_counter() - start) * 1000

print(f"Decision Latency: {latency_ms:.2f}ms")
# Target: <1ms (p95)

# 3. Backtest with nautilus_trader
# (Use nautilus_trader backtesting engine)
```

**Success Criteria**:
- ✅ Annualized return >16% (out-of-sample)
- ✅ Decision latency <1ms (p95)
- ✅ Sharpe >2.0 (HFT strategy)

---

## Summary Checklist

**Phase 17**:
- [ ] Implement model registry (Git LFS backend)
- [ ] Add SHAP explainability (log top 10 features)
- [ ] Deploy automated retraining (weekly check, Sharpe <1.0 trigger)
- [ ] Implement drift detection (River ADWIN)

**Phase 18**:
- [ ] Install nautilus_trader
- [ ] Configure Binance adapter (tick data ingestion)
- [ ] Implement order flow features (bid/ask depth, trade flow imbalance)
- [ ] Validate HFT performance (>16% return, <1ms latency, Sharpe >2.0)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-05
**Author**: Claude Code (Automated ML Roadmap)
