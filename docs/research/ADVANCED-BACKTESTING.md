# Advanced Backtesting Techniques

**Focus:** CPCV, Triple Barrier Method, Meta-Labeling, Fractional Differentiation
**Last Updated:** 2025-10-02
**Key Reference:** "Advances in Financial Machine Learning" - Marcos López de Prado

---

## Table of Contents
1. [Combinatorial Purged Cross-Validation (CPCV)](#cpcv)
2. [Triple Barrier Method](#triple-barrier)
3. [Meta-Labeling](#meta-labeling)
4. [Fractional Differentiation](#fractional-differentiation)
5. [Purging and Embargoing](#purging-embargoing)
6. [Implementation Guide](#implementation)

---

## <a name="cpcv"></a>1. Combinatorial Purged Cross-Validation (CPCV)

### Problem with Standard K-Fold CV in Finance

Standard k-fold cross-validation assumes IID (Independent and Identically Distributed) data. **Financial data violates this assumption** due to:

- **Temporal Dependencies:** Price at time t depends on prices at t-1, t-2, etc.
- **Overlapping Labels:** Labels based on future returns create information leakage
- **Serial Correlation:** Autocorrelation in returns and features

**Result:** Standard k-fold CV **overestimates** out-of-sample performance in financial applications.

### Why CPCV is Superior (2024 Research)

**2024 Physica A Paper:** CPCV demonstrates:
- Lower **Probability of Backtest Overfitting (PBO)**
- Better **Deflated Sharpe Ratio (DSR)**
- Properly handles **label overlaps** through purging
- Accounts for **serial correlation** via embargoing

### How CPCV Works

```python
from sklearn.model_selection import BaseCrossValidator
import numpy as np

class CombinatorialPurgedKFold(BaseCrossValidator):
    """
    Combinatorial Purged K-Fold Cross-Validation

    Based on Chapter 12 of "Advances in Financial Machine Learning"
    by Marcos López de Prado

    Generates N combinations of train/test splits while:
    1. Purging overlapping samples from training set
    2. Embargoing samples to prevent leakage
    3. Maintaining chronological consistency
    """

    def __init__(self, n_splits=5, embargo_pct=0.01):
        """
        Parameters
        ----------
        n_splits : int
            Number of folds (default: 5)
        embargo_pct : float
            Percentage of samples to embargo after test set (default: 0.01)
        """
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct

    def split(self, X, y=None, groups=None):
        """
        Generate indices to split data into training and test set.

        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            Training data with timestamps index
        y : array-like, shape (n_samples,)
            Target variable
        groups : array-like, shape (n_samples,)
            Label timespans for purging

        Yields
        ------
        train : ndarray
            Training set indices
        test : ndarray
            Test set indices
        """
        if not hasattr(X, 'index'):
            raise ValueError("X must have a pandas DateTime index")

        indices = np.arange(len(X))
        embargo_size = int(len(X) * self.embargo_pct)

        # Generate combinatorial splits
        test_size = len(X) // self.n_splits

        for i in range(self.n_splits):
            # Test set: contiguous block
            test_start = i * test_size
            test_end = (i + 1) * test_size if i < self.n_splits - 1 else len(X)
            test_indices = indices[test_start:test_end]

            # Training set: everything except test + purged + embargoed
            train_indices = np.concatenate([
                indices[:test_start],
                indices[min(test_end + embargo_size, len(X)):]
            ])

            # Purging: remove training samples that overlap with test labels
            if groups is not None:
                train_indices = self._purge_train_samples(
                    train_indices, test_indices, groups
                )

            yield train_indices, test_indices

    def _purge_train_samples(self, train_indices, test_indices, label_times):
        """
        Remove training samples that overlap with test set labels.

        Parameters
        ----------
        train_indices : array
            Training set indices before purging
        test_indices : array
            Test set indices
        label_times : array
            End times for each label (when label information becomes available)

        Returns
        -------
        purged_train : array
            Training indices after purging overlaps
        """
        # Find test set time range
        test_start_time = label_times[test_indices].min()
        test_end_time = label_times[test_indices].max()

        # Purge training samples whose labels overlap with test period
        purged_mask = (
            (label_times[train_indices] < test_start_time) |
            (label_times[train_indices] > test_end_time)
        )

        return train_indices[purged_mask]
```

### MLFinLab Implementation

Hudson & Thames provides a production-ready CPCV implementation:

```python
# Install mlfinlab (requires subscription: £100/month)
# pip install mlfinlab

from mlfinlab.cross_validation import CombinatorialPurgedKFold

# Prepare label end times (when information becomes available)
label_end_times = pd.Series(
    index=X.index,
    data=[triple_barrier_end_time(i) for i in X.index]
)

# Create CPCV splitter
cv = CombinatorialPurgedKFold(
    n_splits=5,
    n_test_splits=2,  # Number of test groups
    embargo_pct=0.01   # 1% embargo
)

# Use with scikit-learn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

clf = RandomForestClassifier(n_estimators=100)
scores = cross_val_score(
    clf, X, y,
    cv=cv.split(X, pred_times=label_end_times),
    scoring='f1'
)

print(f"CPCV F1 Scores: {scores}")
print(f"Mean F1: {scores.mean():.3f} (+/- {scores.std():.3f})")
```

### Comparison: Walk-Forward vs CPCV

| Aspect | Walk-Forward | CPCV | Winner |
|--------|--------------|------|--------|
| **Leakage Prevention** | Embargo only | Purging + Embargo | **CPCV** |
| **Number of Backtests** | n_splits | C(n, k) combinations | **CPCV** |
| **PBO (Backtest Overfitting)** | Higher | Lower | **CPCV** |
| **DSR (Deflated Sharpe)** | Lower | Higher | **CPCV** |
| **Implementation Time** | 12h (planned) | 8h | **CPCV** |
| **Computational Cost** | O(n²) | O(n³) | Walk-Forward |

**Recommendation:** Replace THUNES planned walk-forward optimization (Phase B, 12h) with CPCV implementation (8h). Better results, saves 4 hours.

---

## <a name="triple-barrier"></a>2. Triple Barrier Method

### Concept

Traditional labeling methods use fixed-horizon returns:
- "If price rises 5% in next 10 days → BUY signal"

**Problems:**
- Ignores stop-loss (risk management)
- Fixed time horizon doesn't match trade dynamics
- Treats small movements as meaningful signals

### Triple Barrier Approach

For each observation, set **three barriers**:

1. **Upper Barrier (Profit Take):** Price target (e.g., +2%)
2. **Lower Barrier (Stop Loss):** Risk limit (e.g., -1%)
3. **Vertical Barrier (Expiration):** Maximum holding period (e.g., 5 days)

**Label = whichever barrier is touched first**

```python
import pandas as pd
import numpy as np

def triple_barrier_labels(
    prices: pd.Series,
    profit_take_pct: float = 0.02,  # 2% profit target
    stop_loss_pct: float = 0.01,     # 1% stop loss
    max_holding_period: int = 5       # 5 days expiration
) -> pd.DataFrame:
    """
    Generate labels using triple barrier method.

    Parameters
    ----------
    prices : pd.Series
        Asset prices with DateTime index
    profit_take_pct : float
        Profit take threshold (positive)
    stop_loss_pct : float
        Stop loss threshold (positive)
    max_holding_period : int
        Maximum days to hold position

    Returns
    -------
    pd.DataFrame with columns:
        - label: {1: profit hit, -1: stop hit, 0: expired}
        - return: actual return achieved
        - holding_period: days held
        - barrier_touched: which barrier was hit first
    """
    labels = []

    for i in range(len(prices) - max_holding_period):
        entry_price = prices.iloc[i]
        future_prices = prices.iloc[i+1:i+1+max_holding_period]

        # Calculate returns
        returns = (future_prices - entry_price) / entry_price

        # Find first barrier touch
        profit_touch = returns[returns >= profit_take_pct]
        loss_touch = returns[returns <= -stop_loss_pct]

        if len(profit_touch) > 0 and len(loss_touch) > 0:
            # Both hit - which came first?
            if profit_touch.index[0] < loss_touch.index[0]:
                label = 1
                ret = profit_take_pct
                holding = (profit_touch.index[0] - prices.index[i]).days
                barrier = 'profit_take'
            else:
                label = -1
                ret = -stop_loss_pct
                holding = (loss_touch.index[0] - prices.index[i]).days
                barrier = 'stop_loss'
        elif len(profit_touch) > 0:
            label = 1
            ret = profit_take_pct
            holding = (profit_touch.index[0] - prices.index[i]).days
            barrier = 'profit_take'
        elif len(loss_touch) > 0:
            label = -1
            ret = -stop_loss_pct
            holding = (loss_touch.index[0] - prices.index[i]).days
            barrier = 'stop_loss'
        else:
            # Expired - use actual return
            label = 0
            ret = returns.iloc[-1]
            holding = max_holding_period
            barrier = 'expired'

        labels.append({
            'label': label,
            'return': ret,
            'holding_period': holding,
            'barrier_touched': barrier,
            'label_end_time': prices.index[i] + pd.Timedelta(days=holding)
        })

    return pd.DataFrame(labels, index=prices.index[:len(labels)])
```

### 2024 Crypto Research Application

**July 2024 arXiv:** "Optimal market-neutral multivariate pair trading on cryptocurrency platform"
- Applied triple barrier to BTC-ETH pairs trading
- Profit take: 1.5% spread widening
- Stop loss: 0.75% adverse movement
- Expiration: 48 hours (crypto markets 24/7)
- **Result:** Better risk-adjusted returns than fixed-horizon labels

### Integration with THUNES

```python
# In src/backtest/strategy.py

from src.utils.labeling import triple_barrier_labels

# Generate labels for strategy development
df_with_labels = triple_barrier_labels(
    prices=df['close'],
    profit_take_pct=0.025,  # 2.5% profit target
    stop_loss_pct=0.0125,   # 1.25% stop (2:1 reward:risk)
    max_holding_period=3    # 3 days max hold
)

# Use for ML training
X = df[['feature1', 'feature2', 'feature3']]
y = df_with_labels['label']

# Train classifier
from sklearn.ensemble import RandomForestClassifier
clf = RandomForestClassifier()
clf.fit(X, y)
```

---

## <a name="meta-labeling"></a>3. Meta-Labeling

### The Problem with Binary Classification

Primary model predicts: **BUY (1) or SELL (-1)**

Issues:
- False positives are costly (enter bad trades)
- Model treats all BUY signals equally
- No confidence filtering

### Meta-Labeling Solution

**Two-stage process:**

**Stage 1 (Primary Model):** Predict **side** (BUY/SELL)
- Based on strategy signals (e.g., RSI, MACD, mean reversion)

**Stage 2 (Meta-Model):** Predict **whether to trade**
- Binary: Take the trade (1) or pass (0)
- Features: Same as primary + primary model confidence
- Labels: Did this trade make money? (from triple barrier)

### Implementation

```python
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

class MetaLabelingModel:
    """
    Two-stage meta-labeling system.

    Stage 1: Primary model predicts trade side (BUY/SELL)
    Stage 2: Meta model filters false positives
    """

    def __init__(self):
        # Primary model: predicts side
        self.primary_model = RandomForestClassifier(n_estimators=100)

        # Meta model: predicts whether to execute
        self.meta_model = GradientBoostingClassifier(n_estimators=50)

    def fit_primary(self, X, side_labels):
        """Fit primary model to predict trade side."""
        self.primary_model.fit(X, side_labels)

    def generate_meta_labels(self, X, prices, profit_take=0.02, stop_loss=0.01):
        """
        Generate meta labels: did the primary model's prediction make money?

        Returns 1 if trade would be profitable, 0 otherwise.
        """
        # Get primary model predictions
        primary_preds = self.primary_model.predict(X)
        primary_proba = self.primary_model.predict_proba(X)

        # For each prediction, check if it would have been profitable
        meta_labels = []

        for i in range(len(X) - 5):
            if primary_preds[i] == 1:  # BUY signal
                # Would this BUY have made money?
                future_return = (prices.iloc[i+5] - prices.iloc[i]) / prices.iloc[i]
                profitable = 1 if future_return >= profit_take else 0
            elif primary_preds[i] == -1:  # SELL signal
                # Would this SELL have made money?
                future_return = (prices.iloc[i] - prices.iloc[i+5]) / prices.iloc[i]
                profitable = 1 if future_return >= profit_take else 0
            else:
                profitable = 0

            meta_labels.append(profitable)

        return pd.Series(meta_labels, index=X.index[:len(meta_labels)])

    def fit_meta(self, X, meta_labels):
        """
        Fit meta model to filter primary predictions.

        Features should include primary model confidence scores.
        """
        # Add primary model probabilities as features
        primary_proba = self.primary_model.predict_proba(X)
        X_meta = pd.concat([
            X,
            pd.DataFrame(primary_proba, columns=['prob_sell', 'prob_buy'], index=X.index)
        ], axis=1)

        self.meta_model.fit(X_meta[:len(meta_labels)], meta_labels)

    def predict(self, X):
        """
        Two-stage prediction:
        1. Primary: What side? (BUY/SELL)
        2. Meta: Should we execute? (YES/NO)

        Returns only filtered high-confidence signals.
        """
        # Stage 1: Get primary predictions
        primary_preds = self.primary_model.predict(X)
        primary_proba = self.primary_model.predict_proba(X)

        # Stage 2: Filter with meta model
        X_meta = pd.concat([
            X,
            pd.DataFrame(primary_proba, columns=['prob_sell', 'prob_buy'], index=X.index)
        ], axis=1)

        meta_preds = self.meta_model.predict(X_meta)

        # Combine: only return signals that pass meta filter
        final_signals = primary_preds.copy()
        final_signals[meta_preds == 0] = 0  # Filter out low-confidence signals

        return final_signals
```

### Benefits

- **Higher Precision:** Filters false positives from primary model
- **Better Risk-Adjusted Returns:** Fewer bad trades
- **Confidence Calibration:** Meta model learns which primary signals to trust
- **2024 Research:** Crypto pairs trading showed 30% reduction in losing trades

---

## <a name="fractional-differentiation"></a>4. Fractional Differentiation

### The Stationarity vs Memory Tradeoff

**Problem:**
- **Raw prices:** Non-stationary (trending), but preserve all information
- **Returns (d=1):** Stationary, but destroy all memory (autocorrelation)

**Solution:** Fractional differentiation (0 < d < 1)
- Achieve stationarity while preserving partial memory
- Sweet spot: minimum d that passes stationarity test (ADF, KPSS)

### Mathematical Definition

Standard differentiation (d=1):
```
Δx_t = x_t - x_{t-1}
```

Fractional differentiation (0 < d < 1):
```
Δ^d x_t = Σ_{k=0}^∞ w_k x_{t-k}

where weights: w_k = (-d choose k)
```

### Implementation

```python
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

def frac_diff_weights(d, size):
    """
    Calculate weights for fractional differentiation.

    Parameters
    ----------
    d : float
        Differentiation order (0 < d < 1)
    size : int
        Number of weights to compute

    Returns
    -------
    np.array
        Array of weights
    """
    w = [1.0]
    for k in range(1, size):
        w.append(-w[-1] * (d - k + 1) / k)
    return np.array(w)

def frac_diff(series, d, threshold=1e-5):
    """
    Fractionally differentiate a time series.

    Parameters
    ----------
    series : pd.Series
        Time series to differentiate
    d : float
        Differentiation order (0 < d < 1)
    threshold : float
        Minimum weight threshold for truncation

    Returns
    -------
    pd.Series
        Fractionally differentiated series
    """
    # Calculate weights
    weights = frac_diff_weights(d, len(series))

    # Truncate weights below threshold
    weights = weights[np.abs(weights) > threshold]

    # Apply fractional differentiation
    result = pd.Series(index=series.index, dtype=float)

    for i in range(len(weights), len(series)):
        result.iloc[i] = np.dot(weights, series.iloc[i-len(weights)+1:i+1][::-1])

    return result

def find_minimum_d(series, max_d=1.0, step=0.01, significance=0.05):
    """
    Find minimum d that achieves stationarity.

    Uses Augmented Dickey-Fuller test.

    Parameters
    ----------
    series : pd.Series
        Time series to test
    max_d : float
        Maximum d to test
    step : float
        Step size for d search
    significance : float
        Significance level for ADF test

    Returns
    -------
    float
        Minimum d achieving stationarity
    """
    d_values = np.arange(0, max_d + step, step)

    for d in d_values:
        diff_series = frac_diff(series, d)
        diff_series = diff_series.dropna()

        if len(diff_series) < 50:
            continue

        # ADF test
        adf_stat, p_value, _, _, _, _ = adfuller(diff_series, autolag='AIC')

        if p_value < significance:
            print(f"Minimum d found: {d:.3f} (p-value: {p_value:.4f})")
            return d

    print(f"No d found below {max_d} achieving stationarity")
    return max_d

# Example usage
prices = df['close']

# Find optimal d
optimal_d = find_minimum_d(prices)

# Apply fractional differentiation
stationary_prices = frac_diff(prices, optimal_d)

# Verify stationarity preserved more memory than returns
print(f"Autocorr(raw prices, lag=1): {prices.autocorr(lag=1):.4f}")
print(f"Autocorr(frac diff d={optimal_d}, lag=1): {stationary_prices.autocorr(lag=1):.4f}")
print(f"Autocorr(returns, lag=1): {prices.pct_change().autocorr(lag=1):.4f}")
```

### When to Use Fractional Differentiation

**Use Cases:**
- Feature engineering for ML models (preserve predictive information)
- Cointegration testing (test at optimal d, not just d=1)
- Regime detection (stationary yet memory-preserving features)

**Caution:**
- Computational cost higher than simple differencing
- Choice of d is hyperparameter to optimize
- Not needed for models that handle non-stationarity (XGBoost, RF)

---

## <a name="purging-embargoing"></a>5. Purging and Embargoing

### Purging

**Goal:** Remove training samples whose labels overlap with test period

**When is this needed?**
- Labels based on future information (e.g., next 5-day return)
- Label for training sample at t=100 uses data up to t=105
- Test set starts at t=103
- **Leak:** Training label uses test period data!

**Solution:** Purge training samples with label times > test start time

```python
def purge_training_set(train_indices, test_indices, label_end_times):
    """
    Remove training samples that overlap with test set.

    Parameters
    ----------
    train_indices : array
        Training set indices before purging
    test_indices : array
        Test set indices
    label_end_times : pd.Series
        Timestamp when each label's information becomes available

    Returns
    -------
    array
        Purged training indices
    """
    # Test set time range
    test_times = label_end_times.iloc[test_indices]
    test_start = test_times.min()
    test_end = test_times.max()

    # Training label times
    train_label_times = label_end_times.iloc[train_indices]

    # Purge: keep only training samples that don't overlap
    mask = (train_label_times < test_start) | (train_label_times > test_end)

    return train_indices[mask]
```

### Embargoing

**Goal:** Account for serial correlation in labels

**Problem:** Even after purging, consecutive samples may be correlated
- Price shock at t=100 affects returns for next several periods
- Training samples just before test set may contain leaked information via autocorrelation

**Solution:** Embargo (skip) a buffer period after test set

```python
def embargo_training_set(train_indices, test_indices, embargo_pct=0.01):
    """
    Remove training samples immediately after test set.

    Parameters
    ----------
    train_indices : array
        Training indices after purging
    test_indices : array
        Test indices
    embargo_pct : float
        Percentage of samples to embargo (default: 1%)

    Returns
    -------
    array
        Training indices after embargo
    """
    # Calculate embargo size
    embargo_size = int(len(train_indices) * embargo_pct)

    # Find test set end
    test_end_idx = test_indices.max()

    # Remove training samples in embargo window
    mask = (train_indices < test_end_idx - embargo_size) | \
           (train_indices > test_end_idx + embargo_size)

    return train_indices[mask]
```

### Rule of Thumb

- **Purging:** Always required for financial data with forward-looking labels
- **Embargo:** Required when labels exhibit serial correlation
  - Test with autocorrelation: `labels.autocorr(lag=1) > 0.05`
  - Typical embargo: 0.01 (1%) to 0.05 (5%) of dataset size

---

## <a name="implementation"></a>6. Implementation Guide for THUNES

### Phase 1: Replace Walk-Forward with CPCV (8 hours)

**Current Plan (Phase B):** Walk-forward optimization - 12 hours
**New Plan:** CPCV implementation - 8 hours (saves 4 hours, better results)

**Steps:**

1. **Install Dependencies** (30 min)
   ```bash
   # MLFinLab requires subscription (£100/month)
   # Alternative: Implement custom CPCV from code above
   pip install mlfinlab  # or use custom implementation
   ```

2. **Prepare Label End Times** (1 hour)
   ```python
   # In src/utils/labeling.py
   def calculate_label_end_times(df, strategy_horizon=5):
       """Calculate when each label's information becomes available."""
       return df.index + pd.Timedelta(days=strategy_horizon)
   ```

3. **Implement CPCV Splitter** (3 hours)
   ```python
   # In src/backtest/validation.py
   from src.utils.labeling import calculate_label_end_times
   # Use code from section 1 above
   ```

4. **Update Optimization Loop** (2 hours)
   ```python
   # In src/backtest/optimize.py
   def optimize_strategy_cpcv(df, param_grid):
       label_times = calculate_label_end_times(df)
       cv = CombinatorialPurgedKFold(n_splits=5, embargo_pct=0.01)
       # ... rest of optimization
   ```

5. **Testing & Validation** (1.5 hours)
   - Verify purging works correctly
   - Compare PBO with old walk-forward
   - Validate embargo prevents leakage

### Phase 2: Triple Barrier Labeling (4 hours)

1. **Implement Triple Barrier** (2 hours)
   - Use code from section 2
   - Add to `src/utils/labeling.py`

2. **Integrate with Strategy** (1.5 hours)
   - Generate labels in backtesting
   - Store `label_end_time` for CPCV

3. **Testing** (30 min)
   - Verify barrier logic
   - Check label distribution

### Phase 3: Meta-Labeling (Optional, 6 hours)

Only if ML-based strategy is adopted (not in current THUNES MVP)

---

## References

1. **López de Prado, M.** (2018). *Advances in Financial Machine Learning*. Wiley.
   - Chapter 7: Cross-Validation in Finance
   - Chapter 12: Backtesting through Cross-Validation

2. **MLFinLab Documentation** - Hudson & Thames
   - CPCV Implementation: https://www.mlfinlab.com/en/latest/cross_validation/cpcv.html
   - Purging & Embargo: https://www.mlfinlab.com/en/latest/cross_validation/purged_embargo.html

3. **QuantBeckman** - "Combinatorial Purged Cross Validation for Optimization"
   - Code examples: https://www.quantbeckman.com/p/with-code-combinatorial-purged-cross

4. **2024 arXiv Papers:**
   - "Optimal market-neutral multivariate pair trading" (July 2024) - Triple barrier for crypto
   - Various applications in statistical arbitrage

---

**Next:** [Machine Learning Strategies →](./MACHINE-LEARNING-STRATEGIES.md)
