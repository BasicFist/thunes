# THUNES Comprehensive Production Roadmap 2025

**Status:** Production-Grade Implementation Plan
**Timeline:** 6-8 months (292 hours, ~12h/week)
**Last Updated:** 2025-10-02
**Priority:** Integrates all 10 user requirements + research findings + gap analysis

---

## Executive Summary

This roadmap transforms THUNES from a single-exchange, single-strategy MVP to a **production-grade multi-exchange quantitative trading platform** with enterprise security, advanced strategies, and comprehensive monitoring.

### Current State (Phase A Complete ✅)
- ✅ Position tracking with SQLite
- ✅ Rate limiting (1200/min IP, 50/10sec orders)
- ✅ Circuit breaker (3-state pattern)
- ✅ Pydantic v2 validation
- ⚠️ **Single exchange** (Binance only)
- ⚠️ **Single strategy** (SMA crossover)
- ⚠️ **Fixed position sizing** ($10 quote amount)
- ⚠️ **No security hardening** (no 2FA, no key rotation)

### 10 Critical Requirements Integration

This roadmap addresses **ALL** user requirements:

1. **Multi-Exchange Support** → Tier 2 (CCXT integration: Coinbase Pro, Kraken, Huobi)
2. **Advanced Strategies** → Tier 3 (Mean reversion, momentum, ML-based, pairs trading)
3. **Enhanced UI** → Tier 3 (Web dashboard with real-time updates, visualization)
4. **Improved Risk Management** → Tier 1-3 (Kelly sizing, CVaR, portfolio rebalancing)
5. **Real-Time Streaming** → Tier 2 (Kafka + Flink, multi-exchange WebSockets)
6. **Optimized Backtesting** → Tier 1 (CPCV, parallel processing, ML models)
7. **Enhanced Security** → Tier 4 (2FA, key vault, audits, penetration testing)
8. **Monitoring & Alerting** → Tier 4 (Prometheus + Grafana, PagerDuty integration)
9. **Automated Testing/CI-CD** → Tier 4 (GitHub Actions, 80%+ coverage)
10. **Improved Documentation** → Tier 4 (Docusaurus, API refs, architecture diagrams)

---

## Gap Analysis Summary

### Functional Gaps (Addressed in Tier 1-3)
- ❌ Limited to SMA crossover → **5+ strategies** (mean reversion, momentum, ML, pairs)
- ❌ Single exchange (Binance) → **Multi-exchange** via CCXT (4 exchanges)
- ❌ Basic risk management → **Advanced risk** (Kelly, CVaR, correlation, rebalancing)
- ❌ No regime detection → **HMM regime detection** (Tier 1)
- ❌ Fixed position sizing → **Adaptive Kelly** with VIX scaling (Tier 1)

### Architectural Gaps (Addressed in Tier 2)
- ❌ Poor separation of concerns → **Modular architecture** (data/strategy/execution/analytics)
- ❌ Limited modularity → **Strategy factory pattern** with pluggable components
- ❌ Inefficient data pipelines → **Kafka + Flink streaming** (Tier 2)
- ❌ No async/await → **Asyncio migration** (20h, Tier 2)

### Performance Gaps (Addressed in Tier 1-2)
- ❌ Slow backtesting → **Parallel CPCV** + caching (Tier 1)
- ❌ Inefficient streaming → **WebSocket streams** for all exchanges (Tier 2)
- ❌ Execution bottlenecks → **TWAP/VWAP algorithms** + smart routing (Tier 3)

### Security Gaps (Addressed in Tier 4)
- ❌ No 2FA → **TOTP 2FA** for all API operations (12h)
- ❌ Vulnerable dependencies → **Automated Dependabot** + quarterly audits (8h)
- ❌ No security audits → **Penetration testing** + vulnerability scanning (8h)
- ❌ Plaintext API keys → **HashiCorp Vault** integration (6h)

### Usability Gaps (Addressed in Tier 3-4)
- ❌ Limited UI → **Web dashboard** (React + WebSocket updates, 24h)
- ❌ Incomplete documentation → **Docusaurus site** with guides + API refs (16h)
- ❌ Inefficient error handling → **Structured logging** + error taxonomy (4h)

---

## Tier 1: Foundation & Quick Wins (32 hours)

**Timeline:** Weeks 1-4 (Month 1)
**Priority:** 🔥 Critical - Highest ROI per hour invested

### 1.1 Custom CPCV Implementation (8 hours) ⭐⭐⭐⭐⭐

**Replaces:** MLFinLab dependency (£100/month)
**Benefit:** Superior backtesting validation, saves costs

**Steps:**
1. Implement `CombinatorialPurgedKFold` class (3h)
   - Purging: Remove overlapping training samples
   - Embargoing: Buffer period for serial correlation
   - Chronological consistency

2. Add label end time calculation (2h)
   - Track when each label's information becomes available
   - Required for purging logic

3. Integrate with Optuna optimization (2h)
   - Update `src/optimize/run_optuna.py`
   - Replace simple split with CPCV

4. Testing and validation (1h)
   - Verify purging correctness
   - Validate embargo prevents leakage
   - Compare PBO with simple k-fold

**Files Created/Modified:**
```python
# NEW: src/backtest/validation.py
from sklearn.model_selection import BaseCrossValidator
import numpy as np
import pandas as pd

class CombinatorialPurgedKFold(BaseCrossValidator):
    """
    Custom CPCV implementation (no MLFinLab dependency).

    Based on Lopez de Prado (2018) + 2024 Physica A research.
    """

    def __init__(self, n_splits=5, embargo_pct=0.01):
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct

    def split(self, X, y=None, groups=None):
        """Generate purged + embargoed train/test splits."""
        if not hasattr(X, 'index'):
            raise ValueError("X must have pandas DateTime index")

        indices = np.arange(len(X))
        embargo_size = int(len(X) * self.embargo_pct)
        test_size = len(X) // self.n_splits

        for i in range(self.n_splits):
            # Test set: contiguous block
            test_start = i * test_size
            test_end = (i + 1) * test_size if i < self.n_splits - 1 else len(X)
            test_indices = indices[test_start:test_end]

            # Train set: exclude test + embargo
            train_indices = np.concatenate([
                indices[:test_start],
                indices[min(test_end + embargo_size, len(X)):]
            ])

            # Purging: remove overlapping labels
            if groups is not None:
                train_indices = self._purge_train_samples(
                    train_indices, test_indices, groups
                )

            yield train_indices, test_indices

    def _purge_train_samples(self, train_indices, test_indices, label_times):
        """Remove training samples whose labels overlap with test period."""
        test_start_time = label_times[test_indices].min()
        test_end_time = label_times[test_indices].max()

        train_label_times = label_times[train_indices]
        purged_mask = (
            (train_label_times < test_start_time) |
            (train_label_times > test_end_time)
        )

        return train_indices[purged_mask]

# MODIFY: src/optimize/run_optuna.py (lines 130-160)
# OLD: Simple backtest loop
# NEW: CPCV cross-validation

from src.backtest.validation import CombinatorialPurgedKFold

def objective(trial):
    # ... parameter suggestions ...

    # Calculate label end times (5-day holding period)
    label_times = df.index + pd.Timedelta(days=5)

    # CPCV splitter
    cv = CombinatorialPurgedKFold(n_splits=5, embargo_pct=0.01)

    sharpe_ratios = []
    for train_idx, test_idx in cv.split(df, groups=label_times):
        train_df = df.iloc[train_idx]
        test_df = df.iloc[test_idx]

        # Backtest on test fold
        results = run_backtest(test_df, params)
        sharpe_ratios.append(results['sharpe'])

    # Return mean Sharpe across folds
    return np.mean(sharpe_ratios)
```

**Success Metrics:**
- [ ] PBO (Probability of Backtest Overfitting) < 0.5
- [ ] DSR (Deflated Sharpe Ratio) > 1.5
- [ ] Out-of-sample Sharpe within 20% of in-sample (reduced overfitting)

---

### 1.2 Optuna Multivariate TPE (4 hours) ⭐⭐⭐⭐

**Current:** Basic TPE sampler (line 106 in `run_optuna.py`)
**Upgrade:** Multivariate TPE with parameter dependencies
**Benefit:** 15-30% improvement in convergence speed

**File to Modify:**
```python
# MODIFY: src/optimize/run_optuna.py (lines 106-108)

# BEFORE (current):
sampler = optuna.samplers.TPESampler(seed=42)
pruner = optuna.pruners.MedianPruner()

# AFTER (upgrade):
sampler = optuna.samplers.TPESampler(
    seed=42,
    multivariate=True,        # ← 15-30% improvement!
    group=True,               # ← Handle parameter dependencies
    n_startup_trials=20,      # ← Warmup with random search
    constant_liar=True        # ← For distributed optimization (future)
)

pruner = optuna.pruners.HyperbandPruner(
    min_resource=5,
    max_resource=100,
    reduction_factor=3
)

study = optuna.create_study(
    sampler=sampler,
    pruner=pruner,
    direction='maximize'
)
```

**Testing:**
1. Run benchmark: 100 trials with old sampler → record time + best Sharpe
2. Run benchmark: 100 trials with new sampler → record time + best Sharpe
3. Validate: 15%+ reduction in trials to convergence

**Success Metrics:**
- [ ] 15%+ faster convergence to optimal Sharpe
- [ ] Higher final Sharpe with same trial budget
- [ ] Optuna study visualization shows better exploration

---

### 1.3 Adaptive Kelly Position Sizing (8 hours) ⭐⭐⭐⭐⭐

**Current:** Fixed $10 quote amount (line 220 in `paper_trader.py`)
**Upgrade:** Fractional Kelly (0.125x) + VIX scaling
**Benefit:** Optimal risk allocation, prevents over-betting

**Files Created/Modified:**
```python
# NEW: src/utils/position_sizing.py
from decimal import Decimal
import pandas as pd

class AdaptiveKellySizer:
    """
    Adaptive Kelly Criterion with volatility scaling.

    Based on 2024 hybrid Kelly + VIX research.
    Fractional Kelly (0.10x-0.15x) prevents over-leveraging.
    """

    def __init__(
        self,
        kelly_fraction: float = 0.125,  # Fractional Kelly
        vix_target: float = 20.0,       # Target volatility
        min_position_pct: float = 0.01,  # 1% min
        max_position_pct: float = 0.10   # 10% max
    ):
        self.kelly_fraction = kelly_fraction
        self.vix_target = vix_target
        self.min_position_pct = min_position_pct
        self.max_position_pct = max_position_pct

    def calculate_position_size(
        self,
        capital: Decimal,
        win_rate: Decimal,          # From recent trades
        avg_win: Decimal,           # Average winning return
        avg_loss: Decimal,          # Average losing return
        current_volatility: Decimal # Rolling 20-day volatility
    ) -> Decimal:
        """
        Calculate optimal position size using adaptive Kelly.

        Formula:
        f = (p*W - (1-p)*L) / W * kelly_fraction * vix_adjustment

        where:
        - p = win rate
        - W = average win
        - L = average loss (positive)
        - kelly_fraction = safety multiplier (0.125)
        - vix_adjustment = inverse volatility scaling
        """
        # Kelly fraction
        numerator = win_rate * avg_win - (1 - win_rate) * avg_loss
        kelly_f = numerator / avg_win if avg_win > 0 else Decimal('0')

        # Apply fractional Kelly (safety margin)
        fractional_kelly = kelly_f * Decimal(str(self.kelly_fraction))

        # VIX/volatility adjustment (inverse scaling)
        vix_adjustment = Decimal(str(self.vix_target)) / max(
            current_volatility, Decimal('0.01')  # Avoid division by zero
        )

        # Final position fraction
        position_fraction = fractional_kelly * vix_adjustment

        # Apply min/max constraints
        position_fraction = max(
            Decimal(str(self.min_position_pct)),
            min(Decimal(str(self.max_position_pct)), position_fraction)
        )

        return capital * position_fraction

    def update_statistics(self, recent_trades: pd.DataFrame):
        """Update win rate and average win/loss from recent trades."""
        if len(recent_trades) < 10:
            # Need minimum trades for statistics
            return None, None, None

        # Use last 30 trades
        recent = recent_trades.tail(30)

        wins = recent[recent['pnl'] > 0]
        losses = recent[recent['pnl'] < 0]

        win_rate = Decimal(str(len(wins) / len(recent)))
        avg_win = Decimal(str(wins['pnl'].mean())) if len(wins) > 0 else Decimal('0')
        avg_loss = abs(Decimal(str(losses['pnl'].mean()))) if len(losses) > 0 else Decimal('0')

        return win_rate, avg_win, avg_loss


# MODIFY: src/live/paper_trader.py (lines 125, 220)

# Add to __init__ (after line 40):
from src.utils.position_sizing import AdaptiveKellySizer
self.position_sizer = AdaptiveKellySizer(kelly_fraction=0.125)

# MODIFY place_market_order method (line 220):
# BEFORE:
quote_amount = Decimal("10")  # Fixed $10

# AFTER:
# Calculate 20-day rolling volatility
recent_prices = self.db_manager.get_recent_prices(symbol, days=20)
volatility = recent_prices['close'].pct_change().std() * Decimal('252').sqrt()

# Get recent trade statistics
recent_trades = self.position_tracker.get_recent_trades(days=30)
win_rate, avg_win, avg_loss = self.position_sizer.update_statistics(recent_trades)

if win_rate is not None:
    # Use Kelly sizing
    capital = self.get_account_balance()
    quote_amount = self.position_sizer.calculate_position_size(
        capital=capital,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        current_volatility=volatility
    )
else:
    # Fallback: fixed 2% of capital
    quote_amount = self.get_account_balance() * Decimal('0.02')

logger.info(f"Adaptive Kelly position size: ${quote_amount} (capital: {capital}, vol: {volatility})")
```

**Success Metrics:**
- [ ] Sharpe ratio improvement > 20%
- [ ] Max drawdown reduction > 15%
- [ ] Position sizes scale inversely with volatility
- [ ] No single position exceeds 10% of capital

---

### 1.4 Dynamic Slippage Model (6 hours) ⭐⭐⭐⭐

**Current:** Fixed 0.05% slippage (line 68 in `strategy.py`)
**Upgrade:** Market impact ∝ sqrt(volume), time-of-day adjustments
**Benefit:** Realistic P&L estimates, better order sizing

**Files Created/Modified:**
```python
# NEW: src/utils/slippage.py
import numpy as np
import pandas as pd

class DynamicSlippageModel:
    """
    Market impact slippage: impact ∝ sqrt(order_volume / market_volume).

    Based on 2024 crypto market microstructure research.
    Accounts for time-of-day liquidity and volatility scaling.
    """

    def __init__(self, base_impact: float = 0.0005):
        self.base_impact = base_impact
        self.hourly_liquidity_factors = self._calculate_liquidity_factors()

    def estimate_slippage(
        self,
        order_volume: float,
        avg_market_volume_1h: float,
        current_hour: int,
        current_volatility: float,
        baseline_volatility: float = 0.02
    ) -> float:
        """
        Estimate slippage for an order.

        Parameters
        ----------
        order_volume : float
            Order size in base currency (e.g., 0.1 BTC)
        avg_market_volume_1h : float
            Average 1-hour market volume
        current_hour : int
            Hour of day (0-23, UTC)
        current_volatility : float
            Current realized volatility (daily)
        baseline_volatility : float
            Baseline volatility for normalization

        Returns
        -------
        float
            Estimated slippage as percentage (e.g., 0.0003 = 0.03%)
        """
        # Market impact: sqrt(volume ratio)
        volume_ratio = order_volume / max(avg_market_volume_1h, 1e-8)
        market_impact = self.base_impact * np.sqrt(volume_ratio)

        # Time-of-day adjustment
        liquidity_factor = self.hourly_liquidity_factors.get(current_hour, 1.0)

        # Volatility adjustment
        vol_factor = current_volatility / baseline_volatility

        # Combined slippage
        total_slippage = market_impact * liquidity_factor * vol_factor

        return total_slippage

    def _calculate_liquidity_factors(self) -> dict:
        """
        Liquidity factors by hour (UTC).

        Higher values = lower liquidity = higher slippage.
        Based on crypto market volume patterns.
        """
        return {
            # Asian low liquidity (00:00-05:00 UTC)
            0: 1.3, 1: 1.4, 2: 1.5, 3: 1.4, 4: 1.3, 5: 1.2,
            # European peak (06:00-11:00 UTC)
            6: 1.0, 7: 0.9, 8: 0.8, 9: 0.8, 10: 0.9, 11: 1.0,
            # US peak (12:00-17:00 UTC)
            12: 0.9, 13: 0.8, 14: 0.7, 15: 0.7, 16: 0.8, 17: 0.9,
            # Evening decline (18:00-23:00 UTC)
            18: 1.0, 19: 1.1, 20: 1.2, 21: 1.2, 22: 1.3, 23: 1.3
        }


# MODIFY: src/backtest/strategy.py (line 68)
from src.utils.slippage import DynamicSlippageModel

class Strategy:
    def __init__(self):
        self.slippage_model = DynamicSlippageModel(base_impact=0.0005)

    def apply_slippage(self, df, signal, order_volume):
        # BEFORE (line 68):
        # slippage_pct = 0.0005  # Fixed 0.05%

        # AFTER:
        current_hour = df.index[-1].hour
        recent_volume = df['volume'].tail(60).mean()  # 1-hour average
        recent_volatility = df['close'].pct_change().tail(20).std()

        slippage_pct = self.slippage_model.estimate_slippage(
            order_volume=order_volume,
            avg_market_volume_1h=recent_volume,
            current_hour=current_hour,
            current_volatility=recent_volatility
        )

        return slippage_pct
```

**Success Metrics:**
- [ ] Backtest P&L matches live trading within 10%
- [ ] Slippage varies realistically (0.02%-0.15% range)
- [ ] Higher slippage during low liquidity hours
- [ ] Larger orders have proportionally higher slippage

---

### 1.5 HMM Regime Detection (6 hours) ⭐⭐⭐⭐

**Current:** Single strategy parameters for all market conditions
**Upgrade:** 2-state HMM (bull/bear), regime-specific parameters
**Benefit:** Better adaptation to changing markets

**Files Created/Modified:**
```python
# NEW: src/models/regime.py
from hmmlearn.hmm import GaussianHMM
import pandas as pd
import numpy as np

class MarketRegimeDetector:
    """
    Hidden Markov Model for regime detection.

    States: 0=bear/high_vol, 1=bull/low_vol
    Based on 2024-2025 HMM research.
    """

    def __init__(self, n_states: int = 2):
        self.n_states = n_states
        self.model = GaussianHMM(
            n_components=n_states,
            covariance_type="full",
            n_iter=100,
            random_state=42
        )
        self.is_fitted = False
        self.regime_params = {}  # Store regime-specific strategy params

    def fit(self, returns: pd.Series, volatility: pd.Series):
        """Fit HMM to historical data."""
        X = pd.DataFrame({
            'return_1d': returns,
            'return_5d': returns.rolling(5).sum(),
            'volatility_20d': volatility
        }).dropna()

        self.model.fit(X.values)
        self.is_fitted = True

        # Calculate regime statistics
        regimes = self.model.predict(X.values)
        self._calculate_regime_stats(returns, regimes)

        return self

    def predict_current_regime(
        self,
        recent_returns: pd.Series,
        recent_volatility: pd.Series
    ) -> int:
        """Predict current market regime (0=bear, 1=bull)."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        X = pd.DataFrame({
            'return_1d': recent_returns,
            'return_5d': recent_returns.rolling(5).sum(),
            'volatility_20d': recent_volatility
        }).dropna()

        regime = self.model.predict(X.values)
        return regime[-1]

    def _calculate_regime_stats(self, returns: pd.Series, regimes: np.array):
        """Calculate statistics per regime."""
        for regime_id in range(self.n_states):
            mask = regimes == regime_id
            regime_returns = returns[mask]

            self.regime_params[regime_id] = {
                'mean_return': regime_returns.mean(),
                'volatility': regime_returns.std(),
                'sharpe': regime_returns.mean() / regime_returns.std() * np.sqrt(252),
                'frequency': mask.sum() / len(returns),
                # Strategy parameters (tune these via optimization)
                'entry_threshold': -0.5 if regime_id == 0 else -0.3,
                'position_size_mult': 0.5 if regime_id == 0 else 1.0
            }


# MODIFY: src/live/paper_trader.py (add regime detection)

# Add to __init__:
from src.models.regime import MarketRegimeDetector
self.regime_detector = MarketRegimeDetector(n_states=2)

# Train on historical data (one-time setup):
historical_prices = self.fetch_historical_data(symbol, days=365)
returns = historical_prices['close'].pct_change()
volatility = returns.rolling(20).std()
self.regime_detector.fit(returns, volatility)

# In run_strategy method, before placing orders:
recent_returns = recent_df['close'].pct_change().tail(20)
recent_volatility = recent_returns.rolling(20).std()

current_regime = self.regime_detector.predict_current_regime(
    recent_returns, recent_volatility
)

# Adjust parameters based on regime
regime_params = self.regime_detector.regime_params[current_regime]
entry_threshold = regime_params['entry_threshold']
position_mult = regime_params['position_size_mult']

logger.info(f"Current regime: {current_regime} ({'bull' if current_regime == 1 else 'bear'})")
```

**Success Metrics:**
- [ ] Regime detection accuracy > 70% (out-of-sample validation)
- [ ] Sharpe improvement > 15% vs single-parameter strategy
- [ ] Drawdown reduction > 20% in sideways markets
- [ ] Regime transitions detected within 2 days

---

## Tier 2: Architecture Modernization (80 hours)

**Timeline:** Weeks 5-12 (Months 2-3)
**Priority:** ⚡ High - Foundational for Tier 3 features

### 2.1 Separation of Concerns Refactoring (20 hours) 🏗️

**Current:** Data/strategy/execution intertwined
**New:** Modular architecture with clear boundaries

**New Directory Structure:**
```
src/
├── data/                  # Data layer (NEW)
│   ├── __init__.py
│   ├── fetchers/
│   │   ├── binance_fetcher.py
│   │   ├── coinbase_fetcher.py
│   │   ├── kraken_fetcher.py
│   │   └── base_fetcher.py
│   ├── processors/
│   │   ├── ohlcv_processor.py
│   │   ├── orderbook_processor.py
│   │   └── trade_processor.py
│   └── storage/
│       ├── timescaledb.py
│       └── cache.py
│
├── strategies/            # Strategy layer (NEW)
│   ├── __init__.py
│   ├── base_strategy.py
│   ├── sma_crossover.py
│   ├── mean_reversion.py
│   ├── momentum.py
│   ├── ml_strategy.py
│   └── pairs_trading.py
│
├── execution/             # Execution layer (NEW)
│   ├── __init__.py
│   ├── order_manager.py
│   ├── algorithms/
│   │   ├── twap.py
│   │   ├── vwap.py
│   │   └── market.py
│   └── smart_router.py
│
├── analytics/             # Analytics layer (NEW)
│   ├── __init__.py
│   ├── performance.py
│   ├── risk.py
│   ├── reporting.py
│   └── visualization.py
│
├── backtest/              # Existing (updated)
│   ├── strategy.py       # Use strategies/ classes
│   ├── validation.py     # CPCV from Tier 1
│   └── run_backtest.py
│
├── live/                  # Existing (updated)
│   └── paper_trader.py   # Use execution/ + strategies/
│
├── models/                # Existing
│   ├── position.py
│   ├── regime.py         # From Tier 1
│   └── schemas.py
│
└── utils/                 # Existing (expanded)
    ├── position_sizing.py # From Tier 1
    ├── slippage.py       # From Tier 1
    ├── rate_limiter.py
    └── circuit_breaker.py
```

**Key Abstractions:**

```python
# NEW: src/data/fetchers/base_fetcher.py
from abc import ABC, abstractmethod
import pandas as pd

class BaseDataFetcher(ABC):
    """Abstract base class for exchange data fetchers."""

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Fetch OHLCV data."""
        pass

    @abstractmethod
    def fetch_ticker(self, symbol: str) -> dict:
        """Fetch current ticker."""
        pass

    @abstractmethod
    def get_exchange_name(self) -> str:
        """Return exchange name."""
        pass


# NEW: src/strategies/base_strategy.py
from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals from OHLCV data.

        Returns DataFrame with 'signal' column: 1=buy, -1=sell, 0=hold
        """
        pass

    @abstractmethod
    def get_parameters(self) -> dict:
        """Return current strategy parameters."""
        pass

    @abstractmethod
    def set_parameters(self, params: dict):
        """Update strategy parameters."""
        pass


# NEW: src/execution/order_manager.py
from decimal import Decimal
from typing import Optional
from src.models.schemas import Order, OrderStatus

class OrderManager:
    """
    Centralized order management with multi-exchange support.
    """

    def __init__(self, exchange_clients: dict):
        self.exchanges = exchange_clients
        self.active_orders = {}

    def place_order(
        self,
        exchange: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None
    ) -> Order:
        """Place order on specified exchange."""
        client = self.exchanges[exchange]

        # Validate and format parameters
        formatted_price, formatted_qty = self._format_order_params(
            exchange, symbol, price, quantity
        )

        # Place order
        result = client.create_order(
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=formatted_qty,
            price=formatted_price
        )

        # Track order
        order = Order.from_exchange_response(result, exchange)
        self.active_orders[order.id] = order

        return order
```

**Migration Steps:**
1. Create new directory structure (2h)
2. Implement base classes and interfaces (4h)
3. Migrate existing code to new structure (8h)
4. Update imports and dependencies (3h)
5. Testing and validation (3h)

---

### 2.2 Multi-Exchange Support via CCXT (16 hours) 🌍

**Addresses:** User Requirement #1
**Exchanges:** Binance, Coinbase Pro, Kraken, Huobi

**Files Created:**
```python
# NEW: src/data/fetchers/ccxt_fetcher.py
import ccxt.async_support as ccxt
import asyncio
import pandas as pd
from src.data.fetchers.base_fetcher import BaseDataFetcher

class CCXTDataFetcher(BaseDataFetcher):
    """
    Unified data fetcher using CCXT for multiple exchanges.

    Supports: Binance, Coinbase Pro, Kraken, Huobi
    """

    SUPPORTED_EXCHANGES = {
        'binance': ccxt.binance,
        'coinbasepro': ccxt.coinbasepro,
        'kraken': ccxt.kraken,
        'huobi': ccxt.huobi
    }

    def __init__(self, exchange_name: str, api_key: str = None, api_secret: str = None):
        if exchange_name not in self.SUPPORTED_EXCHANGES:
            raise ValueError(f"Unsupported exchange: {exchange_name}")

        exchange_class = self.SUPPORTED_EXCHANGES[exchange_name]
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,  # Built-in rate limiting!
            'options': {'defaultType': 'spot'}
        })
        self.exchange_name = exchange_name

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1m',
        limit: int = 1000
    ) -> pd.DataFrame:
        """Fetch OHLCV data (async)."""
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        return df

    async def fetch_ticker(self, symbol: str) -> dict:
        """Fetch current ticker (async)."""
        return await self.exchange.fetch_ticker(symbol)

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Fetch order book."""
        return await self.exchange.fetch_order_book(symbol, limit=limit)

    def get_exchange_name(self) -> str:
        return self.exchange_name

    async def close(self):
        """Close exchange connection."""
        await self.exchange.close()


# NEW: src/data/multi_exchange_aggregator.py
import asyncio
from typing import List
import pandas as pd

class MultiExchangeAggregator:
    """
    Aggregate data from multiple exchanges concurrently.
    """

    def __init__(self, fetchers: List[CCXTDataFetcher]):
        self.fetchers = fetchers

    async def fetch_all_tickers(self, symbol: str) -> dict:
        """Fetch ticker from all exchanges in parallel."""
        tasks = [
            fetcher.fetch_ticker(symbol)
            for fetcher in self.fetchers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        tickers = {}
        for fetcher, result in zip(self.fetchers, results):
            if not isinstance(result, Exception):
                tickers[fetcher.get_exchange_name()] = result

        return tickers

    async def get_best_price(self, symbol: str, side: str) -> tuple:
        """
        Find best price across all exchanges.

        Returns: (exchange_name, price)
        """
        tickers = await self.fetch_all_tickers(symbol)

        if side == 'buy':
            # Best ask (lowest)
            best_exchange = min(
                tickers.items(),
                key=lambda x: x[1]['ask']
            )
        else:
            # Best bid (highest)
            best_exchange = max(
                tickers.items(),
                key=lambda x: x[1]['bid']
            )

        return best_exchange[0], best_exchange[1]['ask' if side == 'buy' else 'bid']


# MODIFY: src/live/paper_trader.py (add multi-exchange support)

from src.data.fetchers.ccxt_fetcher import CCXTDataFetcher
from src.data.multi_exchange_aggregator import MultiExchangeAggregator

class MultiExchangePaperTrader(PaperTrader):
    """Extended paper trader with multi-exchange support."""

    def __init__(self, exchanges: List[dict]):
        # Initialize fetchers for each exchange
        self.fetchers = [
            CCXTDataFetcher(
                exchange_name=ex['name'],
                api_key=ex.get('api_key'),
                api_secret=ex.get('api_secret')
            )
            for ex in exchanges
        ]

        self.aggregator = MultiExchangeAggregator(self.fetchers)

        super().__init__()

    async def place_smart_order(self, symbol: str, side: str, quantity: Decimal):
        """Place order on exchange with best price."""
        best_exchange, best_price = await self.aggregator.get_best_price(symbol, side)

        logger.info(f"Best price for {side} {symbol}: {best_price} on {best_exchange}")

        # Place order on best exchange
        # (execution logic)
```

**Configuration:**
```yaml
# config/exchanges.yaml
exchanges:
  - name: binance
    api_key: ${BINANCE_API_KEY}
    api_secret: ${BINANCE_API_SECRET}
    enabled: true

  - name: coinbasepro
    api_key: ${COINBASE_API_KEY}
    api_secret: ${COINBASE_API_SECRET}
    passphrase: ${COINBASE_PASSPHRASE}
    enabled: true

  - name: kraken
    api_key: ${KRAKEN_API_KEY}
    api_secret: ${KRAKEN_API_SECRET}
    enabled: true

  - name: huobi
    api_key: ${HUOBI_API_KEY}
    api_secret: ${HUOBI_API_SECRET}
    enabled: false  # Enable when ready
```

**Success Metrics:**
- [ ] All 4 exchanges connect successfully
- [ ] CCXT async fetches 100+ tickers in < 2 seconds
- [ ] Best price routing saves > 0.02% per trade
- [ ] Zero API rate limit violations

---

### 2.3 Async/Await Migration (20 hours) - Already Planned

**See:** Phase B in original roadmap
**Benefit:** Non-blocking I/O, 5-10x throughput improvement

**Key Changes:**
- Convert all API calls to `async`/`await`
- Use `asyncio.gather()` for parallel fetching
- Implement async order execution
- Add connection pooling

---

### 2.4 TimescaleDB Migration (16 hours) - Already Planned

**See:** Phase B in original roadmap
**Benefit:** 20x better insert performance vs PostgreSQL

**Schema:**
```sql
-- Hypertable for tick data
CREATE TABLE ticks (
    time TIMESTAMPTZ NOT NULL,
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price NUMERIC(20,8),
    volume NUMERIC(20,8),
    side TEXT
);

SELECT create_hypertable('ticks', 'time');

-- Continuous aggregate for 1-min OHLCV
CREATE MATERIALIZED VIEW ohlcv_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    exchange,
    symbol,
    first(price, time) AS open,
    max(price) AS high,
    min(price) AS low,
    last(price, time) AS close,
    sum(volume) AS volume
FROM ticks
GROUP BY bucket, exchange, symbol;
```

---

### 2.5 Real-Time Data Streaming (8 hours) 📡

**Addresses:** User Requirement #5
**Technology:** WebSocket streams (all exchanges)

**Files Created:**
```python
# NEW: src/data/streaming/websocket_manager.py
import asyncio
import websockets
import json
from typing import Callable, Dict

class WebSocketStreamManager:
    """
    Manage WebSocket connections for real-time data.

    Supports multiple exchanges simultaneously.
    """

    def __init__(self):
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.callbacks: Dict[str, Callable] = {}

    async def connect(self, exchange: str, url: str, callback: Callable):
        """Connect to exchange WebSocket."""
        self.callbacks[exchange] = callback

        async with websockets.connect(url) as ws:
            self.connections[exchange] = ws

            while True:
                try:
                    message = await ws.recv()
                    data = json.loads(message)

                    # Call registered callback
                    await callback(exchange, data)

                except websockets.ConnectionClosed:
                    logger.warning(f"WebSocket closed for {exchange}, reconnecting...")
                    await asyncio.sleep(5)
                    break

    async def subscribe(self, exchange: str, channel: str, symbol: str):
        """Subscribe to a channel (ticker, trades, orderbook)."""
        ws = self.connections.get(exchange)
        if not ws:
            raise ValueError(f"No connection for {exchange}")

        # Exchange-specific subscription messages
        if exchange == 'binance':
            subscribe_msg = {
                "method": "SUBSCRIBE",
                "params": [f"{symbol.lower()}@{channel}"],
                "id": 1
            }
        elif exchange == 'coinbasepro':
            subscribe_msg = {
                "type": "subscribe",
                "product_ids": [symbol],
                "channels": [channel]
            }

        await ws.send(json.dumps(subscribe_msg))


# NEW: src/data/streaming/price_feed.py
from collections import defaultdict
import asyncio

class RealTimePriceFeed:
    """
    Real-time price feed from multiple exchanges.
    """

    def __init__(self):
        self.ws_manager = WebSocketStreamManager()
        self.latest_prices = defaultdict(dict)  # {exchange: {symbol: price}}
        self.price_callbacks = []

    async def start(self, exchanges: List[str], symbols: List[str]):
        """Start WebSocket streams for all exchanges."""
        tasks = []

        for exchange in exchanges:
            for symbol in symbols:
                task = self.ws_manager.connect(
                    exchange=exchange,
                    url=self._get_ws_url(exchange),
                    callback=self._handle_price_update
                )
                tasks.append(task)

        await asyncio.gather(*tasks)

    async def _handle_price_update(self, exchange: str, data: dict):
        """Process price update from WebSocket."""
        # Extract price (exchange-specific parsing)
        price = self._parse_price(exchange, data)
        symbol = self._parse_symbol(exchange, data)

        # Update latest price
        self.latest_prices[exchange][symbol] = price

        # Notify callbacks
        for callback in self.price_callbacks:
            await callback(exchange, symbol, price)

    def get_latest_price(self, exchange: str, symbol: str) -> float:
        """Get latest price (instant, no API call!)."""
        return self.latest_prices.get(exchange, {}).get(symbol)

    def register_callback(self, callback: Callable):
        """Register callback for price updates."""
        self.price_callbacks.append(callback)
```

**Success Metrics:**
- [ ] WebSocket streams from 4 exchanges running simultaneously
- [ ] Price updates < 100ms latency
- [ ] Zero API weight consumption for price fetching
- [ ] Automatic reconnection after disconnects

---

## Tier 3: Advanced Features (100 hours)

**Timeline:** Weeks 13-24 (Months 4-6)
**Priority:** 📈 Medium - Feature expansion

### 3.1 Additional Trading Strategies (24 hours) 🧠

**Addresses:** User Requirement #2

#### 3.1.1 Mean Reversion Strategy (8 hours)
```python
# NEW: src/strategies/mean_reversion.py
from src.strategies.base_strategy import BaseStrategy
import pandas as pd
import numpy as np

class MeanReversionStrategy(BaseStrategy):
    """
    Z-score based mean reversion.

    Entry: |z-score| > threshold
    Exit: z-score crosses zero
    """

    def __init__(
        self,
        lookback_period: int = 20,
        entry_z_threshold: float = 2.0,
        exit_z_threshold: float = 0.5
    ):
        self.lookback = lookback_period
        self.entry_threshold = entry_z_threshold
        self.exit_threshold = exit_z_threshold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate mean reversion signals."""
        # Calculate z-score
        df['sma'] = df['close'].rolling(self.lookback).mean()
        df['std'] = df['close'].rolling(self.lookback).std()
        df['z_score'] = (df['close'] - df['sma']) / df['std']

        # Signals
        df['signal'] = 0

        # Buy when oversold (z-score < -threshold)
        df.loc[df['z_score'] < -self.entry_threshold, 'signal'] = 1

        # Sell when overbought (z-score > +threshold)
        df.loc[df['z_score'] > self.entry_threshold, 'signal'] = -1

        # Exit when z-score crosses zero
        df.loc[abs(df['z_score']) < self.exit_threshold, 'signal'] = 0

        return df
```

#### 3.1.2 Momentum Strategy (8 hours)
```python
# NEW: src/strategies/momentum.py
from src.strategies.base_strategy import BaseStrategy
import pandas as pd

class MomentumStrategy(BaseStrategy):
    """
    Dual momentum: absolute + relative.

    Absolute: Asset vs cash (risk-free)
    Relative: Asset vs benchmark (BTC)
    """

    def __init__(
        self,
        lookback_period: int = 20,
        min_momentum: float = 0.05  # 5% threshold
    ):
        self.lookback = lookback_period
        self.min_momentum = min_momentum

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate momentum signals."""
        # Calculate returns over lookback period
        df['momentum'] = df['close'].pct_change(self.lookback)

        # Absolute momentum: positive return
        df['abs_momentum'] = df['momentum'] > self.min_momentum

        # Signals
        df['signal'] = 0
        df.loc[df['abs_momentum'], 'signal'] = 1  # Long when momentum positive

        return df
```

#### 3.1.3 ML-Based Strategy (8 hours)
```python
# NEW: src/strategies/ml_strategy.py
from src.strategies.base_strategy import BaseStrategy
from sklearn.ensemble import RandomForestClassifier
import pandas as pd

class MLStrategy(BaseStrategy):
    """
    Machine learning based strategy using RandomForest.

    Features: Technical indicators + regime + volatility
    Label: Next-period return direction
    """

    def __init__(self, model_path: str = None):
        self.model = RandomForestClassifier(n_estimators=100)
        self.is_trained = False

        if model_path:
            self.load_model(model_path)

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate ML features."""
        df['rsi'] = self._calculate_rsi(df['close'], 14)
        df['macd'] = self._calculate_macd(df['close'])
        df['bb_width'] = self._bollinger_bandwidth(df['close'], 20)
        df['volume_sma_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['volatility'] = df['close'].pct_change().rolling(20).std()

        return df

    def train(self, df: pd.DataFrame, future_returns: pd.Series):
        """Train ML model."""
        df_features = self.generate_features(df)

        feature_cols = ['rsi', 'macd', 'bb_width', 'volume_sma_ratio', 'volatility']
        X = df_features[feature_cols].dropna()

        # Binary labels: 1 if future return positive, 0 otherwise
        y = (future_returns > 0).astype(int)
        y = y.loc[X.index]

        self.model.fit(X, y)
        self.is_trained = True

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate signals from ML predictions."""
        if not self.is_trained:
            raise ValueError("Model not trained. Call train() first.")

        df_features = self.generate_features(df)
        feature_cols = ['rsi', 'macd', 'bb_width', 'volume_sma_ratio', 'volatility']
        X = df_features[feature_cols].dropna()

        # Predict probabilities
        proba = self.model.predict_proba(X)

        # Signal based on confidence
        df['signal'] = 0
        df.loc[X.index[proba[:, 1] > 0.6], 'signal'] = 1   # High confidence buy
        df.loc[X.index[proba[:, 0] > 0.6], 'signal'] = -1  # High confidence sell

        return df
```

**Strategy Factory:**
```python
# NEW: src/strategies/factory.py
from typing import Dict
from src.strategies.base_strategy import BaseStrategy
from src.strategies.sma_crossover import SMAStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.ml_strategy import MLStrategy

class StrategyFactory:
    """Factory for creating strategy instances."""

    STRATEGIES: Dict[str, type] = {
        'sma_crossover': SMAStrategy,
        'mean_reversion': MeanReversionStrategy,
        'momentum': MomentumStrategy,
        'ml': MLStrategy
    }

    @classmethod
    def create(cls, strategy_name: str, **params) -> BaseStrategy:
        """Create strategy instance by name."""
        if strategy_name not in cls.STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        strategy_class = cls.STRATEGIES[strategy_name]
        return strategy_class(**params)

    @classmethod
    def list_strategies(cls) -> list:
        """List available strategies."""
        return list(cls.STRATEGIES.keys())
```

---

### 3.2 Statistical Arbitrage: BTC-ETH Pairs (12 hours) 📊

**Addresses:** Advanced strategy requirement
**Based on:** July 2024 arXiv research

```python
# NEW: src/strategies/pairs_trading.py
from src.strategies.base_strategy import BaseStrategy
from statsmodels.tsa.stattools import coint
import pandas as pd
import numpy as np

class CointegrationPairsStrategy(BaseStrategy):
    """
    Cointegration-based pairs trading for BTC-ETH.

    Method:
    1. Test for cointegration (Engle-Granger)
    2. Calculate hedge ratio
    3. Trade spread mean reversion
    """

    def __init__(
        self,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        lookback: int = 60
    ):
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.lookback = lookback
        self.hedge_ratio = None

    def test_cointegration(self, price1: pd.Series, price2: pd.Series) -> bool:
        """Test if two price series are cointegrated."""
        score, pvalue, _ = coint(price1, price2)

        # Cointegrated if p-value < 0.05
        return pvalue < 0.05

    def calculate_spread(
        self,
        btc_prices: pd.Series,
        eth_prices: pd.Series
    ) -> pd.Series:
        """
        Calculate spread: BTC - hedge_ratio * ETH
        """
        # Linear regression to find hedge ratio
        from sklearn.linear_model import LinearRegression

        X = eth_prices.values.reshape(-1, 1)
        y = btc_prices.values

        model = LinearRegression()
        model.fit(X, y)

        self.hedge_ratio = model.coef_[0]

        # Spread = BTC - β*ETH
        spread = btc_prices - self.hedge_ratio * eth_prices

        return spread

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate pairs trading signals.

        df should contain both BTC and ETH prices.
        """
        # Calculate spread
        spread = self.calculate_spread(df['btc_close'], df['eth_close'])

        # Z-score of spread
        spread_sma = spread.rolling(self.lookback).mean()
        spread_std = spread.rolling(self.lookback).std()
        z_score = (spread - spread_sma) / spread_std

        # Signals
        df['signal'] = 0

        # Long spread when oversold (short BTC, long ETH)
        df.loc[z_score < -self.entry_z, 'signal'] = 1

        # Short spread when overbought (long BTC, short ETH)
        df.loc[z_score > self.entry_z, 'signal'] = -1

        # Exit when spread reverts
        df.loc[abs(z_score) < self.exit_z, 'signal'] = 0

        df['z_score'] = z_score
        df['spread'] = spread

        return df
```

---

### 3.3 Enhanced Web UI (24 hours) 🖥️

**Addresses:** User Requirement #3
**Technology:** React + WebSocket + Recharts

**Features:**
- Real-time price charts (TradingView-style)
- Strategy performance dashboard
- Order book visualization
- Position tracking
- Risk metrics panel
- Alert management

**File Structure:**
```
frontend/
├── package.json
├── src/
│   ├── App.tsx
│   ├── components/
│   │   ├── Dashboard.tsx
│   │   ├── PriceChart.tsx
│   │   ├── OrderBook.tsx
│   │   ├── PositionTable.tsx
│   │   ├── RiskPanel.tsx
│   │   └── AlertManager.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   └── usePriceData.ts
│   └── api/
│       └── client.ts
└── public/
    └── index.html
```

**Backend API:**
```python
# NEW: src/api/app.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio

app = FastAPI(title="THUNES API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """WebSocket endpoint for real-time prices."""
    await websocket.accept()

    # Subscribe to price feed
    async def send_price_updates():
        while True:
            # Get latest prices from all exchanges
            prices = await aggregator.fetch_all_tickers("BTC/USDT")

            await websocket.send_json({
                "type": "price_update",
                "data": prices,
                "timestamp": datetime.utcnow().isoformat()
            })

            await asyncio.sleep(1)  # 1Hz updates

    await send_price_updates()

@app.get("/api/positions")
async def get_positions():
    """Get current positions."""
    positions = position_tracker.get_all_positions()
    return {"positions": [p.dict() for p in positions]}

@app.get("/api/performance")
async def get_performance():
    """Get strategy performance metrics."""
    return {
        "sharpe": 1.85,
        "sortino": 2.34,
        "max_drawdown": -0.12,
        "total_return": 0.34
    }
```

---

### 3.4 Portfolio Risk Management (16 hours) 📉

**Addresses:** User Requirement #4
**Features:** Dynamic sizing, rebalancing, correlation analysis, CVaR

```python
# NEW: src/analytics/portfolio.py
import pandas as pd
import numpy as np
from scipy.optimize import minimize

class PortfolioManager:
    """
    Portfolio-level risk management.

    Features:
    - Correlation analysis
    - Portfolio rebalancing
    - CVaR optimization
    - Risk parity allocation
    """

    def __init__(self, risk_free_rate: float = 0.0):
        self.risk_free_rate = risk_free_rate
        self.current_weights = {}

    def calculate_correlation_matrix(
        self,
        returns: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix for portfolio assets.

        returns: DataFrame with asset returns as columns
        """
        return returns.corr()

    def calculate_cvar(
        self,
        returns: pd.Series,
        confidence_level: float = 0.95
    ) -> float:
        """
        Calculate Conditional Value-at-Risk (CVaR / ES).

        CVaR = Expected loss beyond VaR threshold.
        """
        # VaR at confidence level
        var = returns.quantile(1 - confidence_level)

        # CVaR: mean of returns below VaR
        cvar = returns[returns <= var].mean()

        return abs(cvar)

    def optimize_portfolio_cvar(
        self,
        returns: pd.DataFrame,
        target_cvar: float = 0.05
    ) -> dict:
        """
        Optimize portfolio weights to minimize CVaR.

        Returns: Optimal weights for each asset
        """
        n_assets = len(returns.columns)

        def portfolio_cvar(weights):
            portfolio_returns = (returns * weights).sum(axis=1)
            return self.calculate_cvar(portfolio_returns)

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},  # Sum to 1
            {'type': 'ineq', 'fun': lambda w: w}  # Non-negative
        ]

        # Initial guess: equal weights
        x0 = np.ones(n_assets) / n_assets

        # Optimize
        result = minimize(
            portfolio_cvar,
            x0,
            method='SLSQP',
            constraints=constraints
        )

        return dict(zip(returns.columns, result.x))

    def rebalance_portfolio(
        self,
        current_positions: dict,
        target_weights: dict,
        total_value: float
    ) -> dict:
        """
        Calculate trades needed to rebalance to target weights.

        Returns: {asset: trade_amount}
        """
        trades = {}

        for asset, target_weight in target_weights.items():
            current_value = current_positions.get(asset, 0)
            target_value = total_value * target_weight

            trade_amount = target_value - current_value

            if abs(trade_amount) > 0.01 * total_value:  # 1% threshold
                trades[asset] = trade_amount

        return trades
```

---

### 3.5 TWAP/VWAP Execution Algorithms (8 hours) ⚡

**Addresses:** Improved execution requirement
**Benefit:** Reduce market impact for large orders

```python
# NEW: src/execution/algorithms/twap.py
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta

class TWAPExecutor:
    """
    Time-Weighted Average Price execution.

    Splits large order into equal slices over time period.
    """

    def __init__(self, order_manager):
        self.order_manager = order_manager

    async def execute_twap(
        self,
        exchange: str,
        symbol: str,
        side: str,
        total_quantity: Decimal,
        duration_minutes: int,
        num_slices: int = 10
    ):
        """
        Execute TWAP order.

        Parameters:
        - total_quantity: Total order size
        - duration_minutes: Time to complete order
        - num_slices: Number of child orders
        """
        slice_quantity = total_quantity / num_slices
        interval_seconds = (duration_minutes * 60) / num_slices

        logger.info(
            f"TWAP: {total_quantity} {symbol} over {duration_minutes}min "
            f"({num_slices} slices of {slice_quantity})"
        )

        for i in range(num_slices):
            # Place slice order
            order = await self.order_manager.place_order(
                exchange=exchange,
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=slice_quantity
            )

            logger.info(f"TWAP slice {i+1}/{num_slices}: {order.id}")

            # Wait for next interval
            if i < num_slices - 1:
                await asyncio.sleep(interval_seconds)


# NEW: src/execution/algorithms/vwap.py
class VWAPExecutor:
    """
    Volume-Weighted Average Price execution.

    Splits order proportionally to historical volume profile.
    """

    def __init__(self, order_manager):
        self.order_manager = order_manager

    async def execute_vwap(
        self,
        exchange: str,
        symbol: str,
        side: str,
        total_quantity: Decimal,
        duration_minutes: int,
        historical_volumes: pd.Series
    ):
        """
        Execute VWAP order.

        historical_volumes: Hourly volume profile for the time period
        """
        # Calculate volume percentages
        total_volume = historical_volumes.sum()
        volume_pcts = historical_volumes / total_volume

        # Calculate slice quantities
        slice_quantities = [total_quantity * pct for pct in volume_pcts]

        # Execute slices
        for i, slice_qty in enumerate(slice_quantities):
            order = await self.order_manager.place_order(
                exchange=exchange,
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=slice_qty
            )

            logger.info(f"VWAP slice {i+1}: {order.id} ({slice_qty})")

            # Wait proportional to volume
            interval = (duration_minutes * 60) * volume_pcts[i]
            await asyncio.sleep(interval)
```

---

### 3.6 Apache Kafka + Flink Streaming (16 hours) 🚀

**Addresses:** User Requirement #5 (advanced streaming)
**Benefit:** Handle 100,000+ events/second

**Architecture:**
```
WebSocket Feeds → Kafka Topics → Flink Processing → TimescaleDB
                                      ↓
                                  Real-time Alerts
                                  Strategy Signals
                                  Risk Calculations
```

**Files:**
```python
# NEW: src/streaming/kafka_producer.py
from kafka import KafkaProducer
import json

class MarketDataProducer:
    """Produce market data to Kafka topics."""

    def __init__(self, bootstrap_servers: list):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    async def send_price_update(self, exchange: str, symbol: str, data: dict):
        """Send price update to Kafka."""
        topic = f"prices.{exchange}.{symbol}"

        message = {
            'exchange': exchange,
            'symbol': symbol,
            'price': data['last'],
            'volume': data['volume'],
            'timestamp': datetime.utcnow().isoformat()
        }

        self.producer.send(topic, value=message)


# NEW: src/streaming/flink_processor.py
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors import FlinkKafkaConsumer
from pyflink.common.serialization import SimpleStringSchema

class RealTimeProcessor:
    """Flink stream processor for market data."""

    def __init__(self):
        self.env = StreamExecutionEnvironment.get_execution_environment()

    def process_price_stream(self):
        """Process price updates from Kafka."""
        # Kafka source
        kafka_consumer = FlinkKafkaConsumer(
            topics='prices.*',
            deserialization_schema=SimpleStringSchema(),
            properties={'bootstrap.servers': 'localhost:9092'}
        )

        # Read stream
        price_stream = self.env.add_source(kafka_consumer)

        # Process: calculate moving averages
        price_stream \
            .key_by(lambda x: x['symbol']) \
            .window(TumblingEventTimeWindows.of(Time.seconds(60))) \
            .apply(CalculateVWAP())

        # Execute
        self.env.execute("Price Stream Processor")
```

---

## Tier 4: Production Hardening (80 hours)

**Timeline:** Weeks 25-32 (Months 7-8)
**Priority:** 🛡️ Critical for Production

### 4.1 Enhanced Security (28 hours) 🔒

**Addresses:** User Requirement #7

#### 4.1.1 2FA Implementation (12 hours)
```python
# NEW: src/security/two_factor.py
import pyotp
import qrcode
from fastapi import HTTPException

class TwoFactorAuth:
    """TOTP-based 2FA for API operations."""

    def __init__(self):
        self.secret = pyotp.random_base32()

    def generate_qr_code(self, user_email: str) -> str:
        """Generate QR code for 2FA setup."""
        totp = pyotp.TOTP(self.secret)
        uri = totp.provisioning_uri(
            name=user_email,
            issuer_name="THUNES Trading"
        )

        # Generate QR code
        qr = qrcode.make(uri)
        return qr  # Return as image

    def verify_token(self, token: str) -> bool:
        """Verify 2FA token."""
        totp = pyotp.TOTP(self.secret)
        return totp.verify(token, valid_window=1)

    def require_2fa(self, operation: str):
        """Decorator to require 2FA for operations."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                token = kwargs.get('totp_token')
                if not token or not self.verify_token(token):
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid 2FA token"
                    )
                return await func(*args, **kwargs)
            return wrapper
        return decorator


# MODIFY: src/api/app.py
from src.security.two_factor import TwoFactorAuth

twofa = TwoFactorAuth()

@app.post("/api/orders")
@twofa.require_2fa("place_order")
async def place_order(order: OrderRequest, totp_token: str):
    """Place order (requires 2FA)."""
    # ... order placement logic
```

#### 4.1.2 HashiCorp Vault Integration (6 hours)
```python
# NEW: src/security/vault.py
import hvac

class VaultSecretManager:
    """Manage API keys and secrets in HashiCorp Vault."""

    def __init__(self, vault_url: str, token: str):
        self.client = hvac.Client(url=vault_url, token=token)

    def get_api_key(self, exchange: str) -> dict:
        """Retrieve API key from Vault."""
        secret_path = f"secret/data/exchanges/{exchange}"

        response = self.client.secrets.kv.v2.read_secret_version(
            path=secret_path
        )

        return response['data']['data']

    def rotate_api_key(self, exchange: str, new_key: str, new_secret: str):
        """Rotate API key."""
        self.client.secrets.kv.v2.create_or_update_secret(
            path=f"secret/data/exchanges/{exchange}",
            secret={
                'api_key': new_key,
                'api_secret': new_secret,
                'rotated_at': datetime.utcnow().isoformat()
            }
        )
```

#### 4.1.3 Security Audits & Vulnerability Scanning (8 hours)
```bash
# NEW: .github/workflows/security.yml
name: Security Audit

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  push:
    branches: [main]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Bandit (Python security)
        run: |
          pip install bandit
          bandit -r src/ -f json -o bandit-report.json

      - name: Run Safety (dependency vulnerabilities)
        run: |
          pip install safety
          safety check --json > safety-report.json

      - name: Run Trivy (container scanning)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'

      - name: Upload results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: bandit-report.json
```

#### 4.1.4 Penetration Testing (2 hours setup)
```python
# NEW: tests/security/test_penetration.py
import pytest
from src.api.app import app

class TestPenetrationSecurity:
    """Penetration testing scenarios."""

    def test_sql_injection(self):
        """Test SQL injection vulnerabilities."""
        # Attempt SQL injection in order placement
        malicious_input = "'; DROP TABLE orders; --"
        response = app.test_client().post(
            '/api/orders',
            json={'symbol': malicious_input}
        )

        assert response.status_code == 400  # Rejected

    def test_xss_attack(self):
        """Test XSS vulnerabilities."""
        xss_payload = "<script>alert('XSS')</script>"
        response = app.test_client().post(
            '/api/strategy',
            json={'name': xss_payload}
        )

        assert '<script>' not in response.data.decode()

    def test_rate_limit_bypass(self):
        """Test rate limit bypass attempts."""
        # Attempt 1000 requests in 1 second
        for i in range(1000):
            response = app.test_client().get('/api/prices')

        # Should be rate limited
        assert response.status_code == 429
```

---

### 4.2 Comprehensive Monitoring & Alerting (20 hours) 📊

**Addresses:** User Requirement #8
**Technology:** Prometheus + Grafana + PagerDuty

#### 4.2.1 Prometheus Metrics (8 hours)
```python
# NEW: src/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

class MetricsCollector:
    """Prometheus metrics for THUNES."""

    def __init__(self):
        # Order metrics
        self.orders_total = Counter(
            'thunes_orders_total',
            'Total orders placed',
            ['exchange', 'side', 'status']
        )

        self.order_latency = Histogram(
            'thunes_order_latency_seconds',
            'Order placement latency',
            ['exchange']
        )

        # Strategy metrics
        self.strategy_signals = Counter(
            'thunes_strategy_signals_total',
            'Strategy signals generated',
            ['strategy', 'signal_type']
        )

        self.portfolio_value = Gauge(
            'thunes_portfolio_value_usd',
            'Current portfolio value in USD'
        )

        # Risk metrics
        self.sharpe_ratio = Gauge(
            'thunes_sharpe_ratio',
            'Current Sharpe ratio'
        )

        self.max_drawdown = Gauge(
            'thunes_max_drawdown',
            'Current maximum drawdown'
        )

        # System metrics
        self.api_errors = Counter(
            'thunes_api_errors_total',
            'API errors',
            ['exchange', 'error_type']
        )

    def record_order(self, exchange: str, side: str, status: str, latency: float):
        """Record order placement."""
        self.orders_total.labels(exchange=exchange, side=side, status=status).inc()
        self.order_latency.labels(exchange=exchange).observe(latency)

    def update_portfolio_value(self, value: float):
        """Update portfolio value."""
        self.portfolio_value.set(value)

    def start_metrics_server(self, port: int = 8000):
        """Start Prometheus metrics HTTP server."""
        start_http_server(port)


# MODIFY: src/live/paper_trader.py
from src.monitoring.metrics import MetricsCollector

class PaperTrader:
    def __init__(self):
        self.metrics = MetricsCollector()
        self.metrics.start_metrics_server(port=8000)

    async def place_order(self, ...):
        start_time = time.time()

        # Place order
        result = await self._place_order_internal(...)

        # Record metrics
        latency = time.time() - start_time
        self.metrics.record_order(
            exchange=exchange,
            side=side,
            status=result.status,
            latency=latency
        )
```

#### 4.2.2 Grafana Dashboards (6 hours)
```json
// NEW: grafana/dashboards/thunes_overview.json
{
  "dashboard": {
    "title": "THUNES Trading Overview",
    "panels": [
      {
        "title": "Portfolio Value (USD)",
        "targets": [
          {
            "expr": "thunes_portfolio_value_usd"
          }
        ],
        "type": "graph"
      },
      {
        "title": "Sharpe Ratio",
        "targets": [
          {
            "expr": "thunes_sharpe_ratio"
          }
        ],
        "type": "stat"
      },
      {
        "title": "Orders by Exchange",
        "targets": [
          {
            "expr": "sum by (exchange) (rate(thunes_orders_total[5m]))"
          }
        ],
        "type": "piechart"
      },
      {
        "title": "Order Latency (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, thunes_order_latency_seconds)"
          }
        ],
        "type": "graph"
      }
    ]
  }
}
```

#### 4.2.3 PagerDuty Integration (6 hours)
```python
# NEW: src/monitoring/alerts.py
import pdpyras
from enum import Enum

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertManager:
    """PagerDuty alert management."""

    def __init__(self, api_key: str):
        self.session = pdpyras.APISession(api_key)
        self.service_id = "THUNES_SERVICE_ID"

    def send_alert(
        self,
        title: str,
        description: str,
        severity: AlertSeverity,
        details: dict = None
    ):
        """Send alert to PagerDuty."""
        event = {
            'routing_key': self.service_id,
            'event_action': 'trigger',
            'payload': {
                'summary': title,
                'severity': severity.value,
                'source': 'THUNES',
                'custom_details': details or {}
            }
        }

        self.session.post('/incidents', json=event)

    def alert_on_max_drawdown(self, current_dd: float, threshold: float = 0.15):
        """Alert if max drawdown exceeds threshold."""
        if current_dd > threshold:
            self.send_alert(
                title=f"Max Drawdown Alert: {current_dd:.1%}",
                description=f"Drawdown {current_dd:.1%} exceeds threshold {threshold:.1%}",
                severity=AlertSeverity.CRITICAL,
                details={
                    'current_drawdown': current_dd,
                    'threshold': threshold,
                    'portfolio_value': self.get_portfolio_value()
                }
            )

    def alert_on_api_failure(self, exchange: str, error: str):
        """Alert on API failures."""
        self.send_alert(
            title=f"API Failure: {exchange}",
            description=f"Exchange API error: {error}",
            severity=AlertSeverity.ERROR,
            details={
                'exchange': exchange,
                'error': error,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
```

---

### 4.3 Automated Testing & CI/CD (16 hours) 🧪

**Addresses:** User Requirement #9
**Target:** 80%+ code coverage

#### 4.3.1 Comprehensive Test Suite (10 hours)
```python
# tests/test_strategies.py
import pytest
from src.strategies.factory import StrategyFactory

class TestStrategies:
    """Test all trading strategies."""

    @pytest.fixture
    def sample_data(self):
        # Generate sample OHLCV data
        return generate_ohlcv_data(days=100)

    @pytest.mark.parametrize('strategy_name', [
        'sma_crossover',
        'mean_reversion',
        'momentum',
        'ml'
    ])
    def test_strategy_signals(self, strategy_name, sample_data):
        """Test that each strategy generates valid signals."""
        strategy = StrategyFactory.create(strategy_name)

        df_with_signals = strategy.generate_signals(sample_data)

        # Verify signal column exists
        assert 'signal' in df_with_signals.columns

        # Verify signals are valid (-1, 0, or 1)
        assert df_with_signals['signal'].isin([-1, 0, 1]).all()

        # Verify no NaN signals
        assert not df_with_signals['signal'].isna().any()


# tests/test_execution.py
class TestOrderExecution:
    """Test order execution logic."""

    @pytest.mark.asyncio
    async def test_twap_execution(self):
        """Test TWAP algorithm."""
        executor = TWAPExecutor(order_manager)

        # Execute TWAP order
        await executor.execute_twap(
            exchange='binance',
            symbol='BTC/USDT',
            side='buy',
            total_quantity=Decimal('1.0'),
            duration_minutes=10,
            num_slices=5
        )

        # Verify 5 child orders were placed
        assert len(order_manager.orders) == 5

        # Verify each slice is ~0.2 BTC
        for order in order_manager.orders:
            assert abs(order.quantity - Decimal('0.2')) < Decimal('0.01')


# tests/test_risk.py
class TestRiskManagement:
    """Test risk management components."""

    def test_kelly_sizing(self):
        """Test Kelly position sizing."""
        sizer = AdaptiveKellySizer(kelly_fraction=0.125)

        position_size = sizer.calculate_position_size(
            capital=Decimal('10000'),
            win_rate=Decimal('0.55'),
            avg_win=Decimal('0.03'),
            avg_loss=Decimal('0.02'),
            current_volatility=Decimal('0.025')
        )

        # Position should be between 1% and 10% of capital
        assert Decimal('100') <= position_size <= Decimal('1000')

    def test_cvar_calculation(self):
        """Test CVaR calculation."""
        portfolio_mgr = PortfolioManager()

        # Generate sample returns
        returns = pd.Series(np.random.normal(0.001, 0.02, 1000))

        cvar = portfolio_mgr.calculate_cvar(returns, confidence_level=0.95)

        # CVaR should be positive and reasonable
        assert 0 < cvar < 0.1
```

#### 4.3.2 GitHub Actions CI/CD (6 hours)
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run tests with coverage
        run: |
          pytest --cov=src --cov-report=xml --cov-report=term-missing

      - name: Check coverage threshold
        run: |
          coverage report --fail-under=80

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run flake8
        run: |
          pip install flake8
          flake8 src/ --max-line-length=100

      - name: Run mypy (type checking)
        run: |
          pip install mypy
          mypy src/ --ignore-missing-imports

  deploy:
    needs: [test, lint]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v3

      - name: Build Docker image
        run: |
          docker build -t thunes:latest .

      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push thunes:latest

      - name: Deploy to production
        run: |
          # Deployment script (SSH to server, pull image, restart services)
          ./bin/deploy.sh
```

---

### 4.4 Comprehensive Documentation (16 hours) 📖

**Addresses:** User Requirement #10
**Technology:** Docusaurus

#### 4.4.1 Documentation Site (10 hours)
```
docs/
├── docusaurus.config.js
├── sidebars.js
├── src/
│   ├── pages/
│   │   └── index.md
│   └── css/
│       └── custom.css
└── docs/
    ├── getting-started/
    │   ├── installation.md
    │   ├── configuration.md
    │   └── first-trade.md
    ├── user-guides/
    │   ├── strategies.md
    │   ├── risk-management.md
    │   ├── multi-exchange.md
    │   └── backtesting.md
    ├── api-reference/
    │   ├── rest-api.md
    │   ├── websocket-api.md
    │   └── python-api.md
    └── architecture/
        ├── overview.md
        ├── data-flow.md
        ├── strategy-framework.md
        └── security.md
```

**Sample Documentation:**
```markdown
# docs/user-guides/strategies.md

# Trading Strategies

THUNES supports multiple trading strategies out of the box:

## Available Strategies

### 1. SMA Crossover
Classic momentum strategy using moving average crossovers.

**Parameters:**
- `fast_period`: Fast SMA window (default: 10)
- `slow_period`: Slow SMA window (default: 30)

**Usage:**
\`\`\`python
from src.strategies.factory import StrategyFactory

strategy = StrategyFactory.create(
    'sma_crossover',
    fast_period=10,
    slow_period=30
)
\`\`\`

### 2. Mean Reversion
Z-score based mean reversion strategy.

**Parameters:**
- `lookback_period`: Window for mean/std calculation (default: 20)
- `entry_z_threshold`: Entry threshold (default: 2.0)

**Usage:**
\`\`\`python
strategy = StrategyFactory.create(
    'mean_reversion',
    lookback_period=20,
    entry_z_threshold=2.0
)
\`\`\`

## Creating Custom Strategies

Extend `BaseStrategy` to create your own:

\`\`\`python
from src.strategies.base_strategy import BaseStrategy

class MyCustomStrategy(BaseStrategy):
    def generate_signals(self, df):
        # Your logic here
        pass
\`\`\`

See [Architecture → Strategy Framework](../architecture/strategy-framework.md) for details.
```

#### 4.4.2 API Documentation (4 hours)
```python
# Use FastAPI auto-generated OpenAPI docs

# src/api/app.py
app = FastAPI(
    title="THUNES Trading API",
    description="Production-grade quantitative trading platform",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Endpoints automatically documented via Pydantic models
@app.post(
    "/api/orders",
    response_model=OrderResponse,
    summary="Place Trading Order",
    description="""
    Place a new trading order on specified exchange.

    **Requires 2FA authentication.**

    Supported order types:
    - MARKET: Immediate execution at current price
    - LIMIT: Execution at specified price or better
    - TWAP: Time-weighted average price algorithm
    - VWAP: Volume-weighted average price algorithm
    """
)
async def place_order(order: OrderRequest, totp_token: str):
    ...
```

#### 4.4.3 Architecture Diagrams (2 hours)
```python
# Use mermaid diagrams in documentation

# docs/architecture/data-flow.md

## Data Flow Architecture

\`\`\`mermaid
graph TD
    A[Exchange WebSockets] --> B[Kafka Topics]
    B --> C[Flink Stream Processor]
    C --> D[TimescaleDB]
    C --> E[Strategy Engine]
    E --> F[Order Manager]
    F --> G[Multi-Exchange Router]
    G --> H[Binance]
    G --> I[Coinbase Pro]
    G --> J[Kraken]
    G --> K[Huobi]

    D --> L[Analytics Engine]
    L --> M[Grafana Dashboard]

    C --> N[Alert Manager]
    N --> O[PagerDuty]
\`\`\`
```

---

## Implementation Sequence (Month-by-Month)

### Month 1: Tier 1 Foundation (32h)
**Week 1-2:** CPCV (8h) + Optuna (4h) = 12h
- Custom CPCV implementation (no MLFinLab)
- Multivariate TPE upgrade (3-line change)
- Backtesting validation

**Week 3:** Dynamic Slippage (6h) + Kelly Sizing Start (4h) = 10h
- Market impact model
- Time-of-day adjustments
- Kelly framework setup

**Week 4:** Kelly Sizing Complete (4h) + HMM Regime (6h) = 10h
- VIX scaling integration
- HMM training and testing

**Deliverable:** 25% Sharpe improvement, PBO < 0.5

---

### Month 2-3: Tier 2 Architecture (80h)

**Month 2:**
- Week 1-2: Separation of concerns refactoring (20h)
- Week 3-4: Multi-exchange CCXT integration (16h)

**Month 3:**
- Week 1-2: Async/await migration (20h)
- Week 3: TimescaleDB migration (16h)
- Week 4: Real-time streaming setup (8h)

**Deliverable:** Multi-exchange platform, async architecture, scalable data layer

---

### Month 4-6: Tier 3 Advanced Features (100h)

**Month 4:**
- Week 1-2: Additional strategies (24h)
  - Mean reversion (8h)
  - Momentum (8h)
  - ML-based (8h)
- Week 3-4: Pairs trading (12h) + TWAP/VWAP (8h) = 20h

**Month 5:**
- Week 1-3: Enhanced Web UI (24h)
  - React dashboard (12h)
  - WebSocket integration (6h)
  - Charts and visualization (6h)
- Week 4: Portfolio risk management (16h)

**Month 6:**
- Week 1-4: Kafka + Flink streaming (16h)

**Deliverable:** 5+ strategies, web dashboard, streaming architecture

---

### Month 7-8: Tier 4 Production Hardening (80h)

**Month 7:**
- Week 1-2: Security (28h)
  - 2FA (12h)
  - Vault integration (6h)
  - Security audits (8h)
  - Penetration testing (2h)
- Week 3-4: Monitoring & alerting (20h)

**Month 8:**
- Week 1-2: CI/CD & testing (16h)
- Week 3-4: Documentation (16h)

**Deliverable:** Production-ready platform with security, monitoring, and docs

---

## Total Effort Summary

| Tier | Focus | Hours | Weeks | Priority |
|------|-------|-------|-------|----------|
| **Tier 1** | Foundation | 32h | 4 | 🔥 Critical |
| **Tier 2** | Architecture | 80h | 8 | ⚡ High |
| **Tier 3** | Features | 100h | 12 | 📈 Medium |
| **Tier 4** | Production | 80h | 8 | 🛡️ Critical |
| **TOTAL** | | **292h** | **32 weeks** | |

**Timeline:** 8 months @ ~12 hours/week (part-time)

---

## Success Metrics

### Tier 1 Completion
- [ ] Sharpe Ratio > 1.8 (baseline: ~1.2)
- [ ] Max Drawdown < 15% (baseline: ~20%)
- [ ] PBO < 0.5 (lower overfitting)
- [ ] Position sizes scale with volatility

### Tier 2 Completion
- [ ] 4 exchanges integrated and operational
- [ ] API latency < 100ms (async)
- [ ] Data insert rate > 10,000 ticks/sec
- [ ] WebSocket streams running 24/7

### Tier 3 Completion
- [ ] 5+ strategies available
- [ ] Web dashboard with real-time updates
- [ ] Portfolio CVaR < 5%
- [ ] TWAP/VWAP reduce slippage by 20%+

### Tier 4 Completion
- [ ] Test coverage > 80%
- [ ] Zero critical security vulnerabilities
- [ ] Mean Time To Recovery (MTTR) < 5 minutes
- [ ] Complete documentation site live

---

## Risk Mitigation

### Technical Risks
1. **CPCV Complexity** → Thorough unit testing, compare with MLFinLab patterns
2. **Multi-Exchange Differences** → CCXT abstraction layer handles inconsistencies
3. **WebSocket Reliability** → Auto-reconnection with exponential backoff
4. **Data Pipeline Failures** → Dead letter queues, retry logic, monitoring

### Operational Risks
1. **API Rate Limits** → Built-in rate limiting, intelligent backoff
2. **Exchange Downtime** → Multi-exchange redundancy, smart routing
3. **Security Breaches** → 2FA, Vault, regular audits, penetration testing
4. **Over-Optimization** → CPCV prevents overfitting, out-of-sample validation

### Rollback Plans
- **Tier 1:** Keep old optimization in separate branch for 2 weeks
- **Tier 2:** Blue-green deployment, instant rollback capability
- **Tier 3:** Feature flags for new strategies (disable without redeployment)
- **Tier 4:** Staging environment mirrors production

---

## Next Steps

### Week 1 (Immediate)
1. ✅ Review this roadmap with stakeholders
2. ✅ Set up development environment
3. ✅ Create Tier 1 feature branch
4. 🚀 **Start:** Optuna multivariate TPE (4h quick win)

### Week 2-4
5. Implement custom CPCV (8h)
6. Dynamic slippage model (6h)
7. Adaptive Kelly sizing (8h)
8. HMM regime detection (6h)

### Month 2+
9. Begin Tier 2 architecture modernization
10. Continuous deployment to staging environment
11. Weekly progress reviews and metric tracking

---

**Roadmap Status:** ✅ Complete and approved
**Last Updated:** 2025-10-02
**Next Review:** After Tier 1 completion (estimated 4 weeks)
**Maintainer:** THUNES Development Team

---

**Legend:**
- 🔥 Critical priority
- ⚡ High priority
- 📈 Medium priority
- 🛡️ Production requirement
- ⭐ High ROI per hour invested
