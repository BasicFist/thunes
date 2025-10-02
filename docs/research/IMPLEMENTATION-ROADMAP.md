# THUNES Implementation Roadmap

**Based on:** 2024-2025 Research Findings
**Total Effort:** 196 hours across 4 tiers
**Timeline:** 5-6 months (part-time)
**Last Updated:** 2025-10-02

---

## Quick Reference

| Tier | Focus | Hours | Timeline | Priority |
|------|-------|-------|----------|----------|
| **Tier 1** | Immediate High ROI | 32h | 2-4 weeks | 🔥 Critical |
| **Tier 2** | Architecture Modernization | 64h | 4-8 weeks | ⚡ High |
| **Tier 3** | Advanced Strategies | 56h | 8-12 weeks | 📈 Medium |
| **Tier 4** | Production Hardening | 44h | 12-16 weeks | 🛡️ Low |

---

## Tier 1: Immediate High ROI (32 hours)

### 1. CPCV Implementation (8 hours) ⭐⭐⭐⭐⭐

**Replaces:** Planned walk-forward optimization (Phase B, 12 hours)
**Benefit:** Superior backtesting validation, saves 4 hours

**Steps:**
1. Implement `CombinatorialPurgedKFold` class (3h)
2. Add purging and embargoing logic (2h)
3. Update optimization loop in `src/backtest/optimize.py` (2h)
4. Testing and validation (1h)

**Files to Modify:**
- Create: `src/backtest/validation.py`
- Modify: `src/backtest/optimize.py`
- Create: `tests/test_cpcv.py`

**Success Metrics:**
- PBO (Probability of Backtest Overfitting) < 0.5
- DSR (Deflated Sharpe Ratio) > 1.5

**Code Example:**
```python
from src.backtest.validation import CombinatorialPurgedKFold

cv = CombinatorialPurgedKFold(n_splits=5, embargo_pct=0.01)
for train, test in cv.split(X, groups=label_end_times):
    # Train on purged + embargoed data
    model.fit(X[train], y[train])
    # Test on isolated period
    score = model.score(X[test], y[test])
```

---

### 2. Optuna Multivariate TPE (4 hours) ⭐⭐⭐⭐

**Current:** Basic TPE sampler
**Upgrade:** Multivariate TPE with grouped parameters
**Benefit:** 15-30% improvement in hyperparameter optimization

**Steps:**
1. Update Optuna sampler configuration (1h)
2. Enable multivariate and group options (1h)
3. Add pruning strategy (MedianPruner → HyperbandPruner) (1h)
4. Re-run optimization benchmarks (1h)

**File to Modify:**
- `src/backtest/optimize.py`

**Code Change:**
```python
# Before:
sampler = optuna.samplers.TPESampler()

# After:
sampler = optuna.samplers.TPESampler(
    multivariate=True,        # 15-30% improvement
    group=True,               # Handle parameter dependencies
    n_startup_trials=20,
    constant_liar=True        # For distributed optimization
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

**Success Metrics:**
- 15%+ reduction in trials to convergence
- Higher final Sharpe ratio with same trial budget

---

### 3. Adaptive Kelly Position Sizing (8 hours) ⭐⭐⭐⭐⭐

**Current:** Fixed $10 quote amount
**Upgrade:** Fractional Kelly with VIX/volatility scaling
**Benefit:** Optimal risk allocation, prevents over-betting

**Steps:**
1. Implement Kelly Criterion calculator (2h)
2. Add volatility scaling (VIX or rolling std) (2h)
3. Integrate with `PaperTrader` (3h)
4. Backtesting validation (1h)

**Files to Modify:**
- Create: `src/utils/position_sizing.py`
- Modify: `src/live/paper_trader.py`

**Implementation:**
```python
from decimal import Decimal

class AdaptiveKellySizer:
    """
    Adaptive Kelly position sizing with volatility scaling.

    Based on 2024 hybrid Kelly + VIX research.
    """

    def __init__(
        self,
        kelly_fraction: float = 0.125,  # Fractional Kelly (0.10x-0.15x)
        vix_target: float = 20.0,
        min_position_pct: float = 0.01,
        max_position_pct: float = 0.10
    ):
        self.kelly_fraction = kelly_fraction
        self.vix_target = vix_target
        self.min_position_pct = min_position_pct
        self.max_position_pct = max_position_pct

    def calculate_position_size(
        self,
        capital: Decimal,
        win_rate: Decimal,
        avg_win: Decimal,
        avg_loss: Decimal,
        current_volatility: Decimal
    ) -> Decimal:
        """
        Calculate optimal position size using adaptive Kelly.

        Formula: f = (p*W - (1-p)*L) / W * kelly_fraction * vix_adjustment
        """
        # Kelly fraction
        numerator = win_rate * avg_win - (1 - win_rate) * avg_loss
        kelly_f = numerator / avg_win

        # Apply fractional Kelly (safety margin)
        fractional_kelly = kelly_f * Decimal(str(self.kelly_fraction))

        # VIX/volatility adjustment (inverse scaling)
        vix_adjustment = Decimal(str(self.vix_target)) / current_volatility

        # Final position fraction
        position_fraction = fractional_kelly * vix_adjustment

        # Apply min/max constraints
        position_fraction = max(
            Decimal(str(self.min_position_pct)),
            min(Decimal(str(self.max_position_pct)), position_fraction)
        )

        return capital * position_fraction
```

**Success Metrics:**
- Sharpe ratio improvement > 20%
- Maximum drawdown reduction > 15%
- No overleveraging (max position < 10% capital)

---

### 4. Dynamic Slippage Model (6 hours) ⭐⭐⭐⭐

**Current:** 0.05% flat slippage assumption
**Upgrade:** Market impact ∝ sqrt(volume), time-of-day adjustments
**Benefit:** More accurate P&L estimates, better order sizing

**Steps:**
1. Analyze historical volume patterns (1h)
2. Implement sqrt market impact model (2h)
3. Add time-of-day / volatility adjustments (2h)
4. Update backtesting slippage (1h)

**File to Modify:**
- Create: `src/utils/slippage.py`
- Modify: `src/backtest/strategy.py`

**Implementation:**
```python
import numpy as np
import pandas as pd

class DynamicSlippageModel:
    """
    Market impact slippage model: impact ∝ sqrt(order_volume / market_volume)

    Based on 2024 crypto market microstructure research.
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
            Size of order in base currency
        avg_market_volume_1h : float
            Average 1-hour market volume
        current_hour : int
            Hour of day (0-23)
        current_volatility : float
            Current realized volatility
        baseline_volatility : float
            Baseline volatility for normalization

        Returns
        -------
        float
            Estimated slippage as percentage
        """
        # Market impact: proportional to sqrt(volume ratio)
        volume_ratio = order_volume / avg_market_volume_1h
        market_impact = self.base_impact * np.sqrt(volume_ratio)

        # Time-of-day adjustment (lower liquidity = higher slippage)
        liquidity_factor = self.hourly_liquidity_factors.get(current_hour, 1.0)

        # Volatility adjustment
        vol_factor = current_volatility / baseline_volatility

        # Combined slippage
        total_slippage = market_impact * liquidity_factor * vol_factor

        return total_slippage

    def _calculate_liquidity_factors(self) -> dict:
        """
        Liquidity factors by hour (UTC).
        Based on crypto market volume patterns.
        """
        # Higher values = lower liquidity = higher slippage
        return {
            0: 1.3, 1: 1.4, 2: 1.5, 3: 1.4, 4: 1.3, 5: 1.2,  # Asian low
            6: 1.0, 7: 0.9, 8: 0.8, 9: 0.8, 10: 0.9, 11: 1.0, # European peak
            12: 0.9, 13: 0.8, 14: 0.7, 15: 0.7, 16: 0.8, 17: 0.9, # US peak
            18: 1.0, 19: 1.1, 20: 1.2, 21: 1.2, 22: 1.3, 23: 1.3  # Evening decline
        }
```

**Success Metrics:**
- Backtest P&L more closely matches live trading (< 10% difference)
- Slippage estimates vary realistically by time and volatility

---

### 5. HMM Regime Detection (6 hours) ⭐⭐⭐⭐

**Current:** Single strategy parameters for all market conditions
**Upgrade:** 2-3 state HMM, train specialist models per regime
**Benefit:** Better parameter adaptation, higher Sharpe in sideways markets

**Steps:**
1. Install and configure hmmlearn (30 min)
2. Implement 2-state HMM (bull/bear) (2h)
3. Train regime-specific strategy parameters (2h)
4. Integrate with live trading (1h)
5. Backtesting validation (30 min)

**Files to Modify:**
- Create: `src/models/regime.py`
- Modify: `src/live/paper_trader.py`

**Implementation:**
```python
from hmmlearn.hmm import GaussianHMM
import pandas as pd
import numpy as np

class MarketRegimeDetector:
    """
    Hidden Markov Model for regime detection.

    States: 0=bear/high_vol, 1=bull/low_vol
    Based on 2024-2025 HMM research showing superiority over clustering.
    """

    def __init__(self, n_states: int = 2):
        self.n_states = n_states
        self.model = GaussianHMM(
            n_components=n_states,
            covariance_type="full",
            n_iter=100
        )
        self.is_fitted = False

    def fit(self, returns: pd.Series, volatility: pd.Series):
        """
        Fit HMM to historical data.

        Features:
        - 1-day returns
        - 5-day returns
        - 20-day rolling volatility
        """
        X = pd.DataFrame({
            'return_1d': returns,
            'return_5d': returns.rolling(5).sum(),
            'volatility_20d': volatility
        }).dropna()

        self.model.fit(X.values)
        self.is_fitted = True

        return self

    def predict_current_regime(
        self,
        recent_returns: pd.Series,
        recent_volatility: pd.Series
    ) -> int:
        """
        Predict current market regime.

        Returns
        -------
        int
            Regime state (0=bear/high_vol, 1=bull/low_vol)
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        X = pd.DataFrame({
            'return_1d': recent_returns,
            'return_5d': recent_returns.rolling(5).sum(),
            'volatility_20d': recent_volatility
        }).dropna()

        regime = self.model.predict(X.values)
        return regime[-1]  # Current regime

    def get_regime_statistics(self, returns: pd.Series, regimes: np.array):
        """
        Calculate statistics per regime.
        """
        stats = {}
        for regime_id in range(self.n_states):
            mask = regimes == regime_id
            regime_returns = returns[mask]

            stats[regime_id] = {
                'mean_return': regime_returns.mean(),
                'volatility': regime_returns.std(),
                'sharpe': regime_returns.mean() / regime_returns.std() * np.sqrt(252),
                'frequency': mask.sum() / len(returns)
            }

        return stats

# Usage in paper trader
regime_detector = MarketRegimeDetector(n_states=2)
regime_detector.fit(historical_returns, historical_volatility)

current_regime = regime_detector.predict_current_regime(recent_returns, recent_vol)

# Use regime-specific parameters
if current_regime == 0:  # Bear/high-vol
    entry_threshold = -0.5  # More conservative
    position_size_mult = 0.5
else:  # Bull/low-vol
    entry_threshold = -0.3  # More aggressive
    position_size_mult = 1.0
```

**Success Metrics:**
- Regime detection accuracy > 70% (validated on out-of-sample data)
- Sharpe ratio improvement > 15% vs single-parameter strategy
- Drawdown reduction in sideways markets > 20%

---

## Tier 2: Architecture Modernization (64 hours)

### 1. Async/Await Migration (20 hours) - Already Planned
**See:** Phase B in original roadmap

### 2. TimescaleDB Migration (16 hours) - Already Planned
**See:** Phase B in original roadmap
**Benefit:** 20x better insert performance vs PostgreSQL

### 3. Temporal Fusion Transformer (16 hours)
**Current:** RSI + MACD technical indicators
**Upgrade:** TFT for multi-horizon forecasting with attention
**Benefit:** Better capture of temporal dependencies

### 4. River Online Learning + ADWIN (12 hours)
**Current:** Static models, periodic retraining
**Upgrade:** Continuous learning with drift detection
**Benefit:** Adapt to market regime changes automatically

---

## Tier 3: Advanced Strategies (56 hours)

### 1. Statistical Arbitrage: BTC-ETH Pairs (12 hours)
**Based on:** July 2024 arXiv research
**Method:** Cointegration + mean reversion

### 2. TWAP/VWAP Execution (10 hours)
**For:** Large order splitting
**Benefit:** Reduce market impact

### 3. Reinforcement Learning Baseline (16 hours)
**Algorithm:** DQN (Deep Q-Network)
**Benchmark:** 12.3% ROI from 2024 research

### 4. Triple Barrier + Meta-Labeling (10 hours)
**See:** [ADVANCED-BACKTESTING.md](./ADVANCED-BACKTESTING.md)

### 5. Fractional Differentiation (8 hours)
**Use:** Feature engineering with memory preservation

---

## Tier 4: Production Hardening (44 hours)

### 1. Apache Kafka + Flink Streaming (16 hours)
**Replace:** Synchronous data fetching
**Benefit:** Real-time event processing at scale

### 2. CVaR Risk Management (8 hours)
**Current:** Basic max drawdown monitoring
**Upgrade:** Conditional Value-at-Risk portfolio limits

### 3. SHAP Model Interpretability (6 hours)
**For:** ML model explainability
**Benefit:** Understand feature importance

### 4. Smart Order Routing (10 hours)
**Method:** Split orders across exchanges
**Benefit:** Better execution prices

### 5. MEV Protection (4 hours)
**Method:** Flashbots integration
**Benefit:** Prevent front-running

---

## Implementation Schedule (5 Months)

### Month 1: Tier 1 Critical Path
- **Week 1:** Optuna multivariate TPE (4h) + Dynamic slippage (6h) = 10h
- **Week 2:** CPCV implementation (8h)
- **Week 3:** Adaptive Kelly sizing (8h)
- **Week 4:** HMM regime detection (6h) + Testing/integration (4h)

**Deliverables:** 32h Tier 1 complete, all high-ROI enhancements live

### Month 2: Tier 2 Architecture (Part 1)
- **Week 1-2:** Async/await migration (20h)
- **Week 3-4:** TimescaleDB migration (16h)

**Deliverables:** Modern async architecture, scalable time-series storage

### Month 3: Tier 2 Architecture (Part 2) + Tier 3 Start
- **Week 1-2:** Temporal Fusion Transformer (16h)
- **Week 3:** River + ADWIN online learning (12h)
- **Week 4:** BTC-ETH pairs trading setup (4h)

**Deliverables:** Advanced ML models, online learning capability

### Month 4: Tier 3 Advanced Strategies
- **Week 1-2:** BTC-ETH pairs trading complete (8h remaining) + TWAP/VWAP (10h)
- **Week 3-4:** Reinforcement learning baseline (16h)

**Deliverables:** Statistical arbitrage live, execution algorithms, RL baseline

### Month 5: Tier 3 Completion + Tier 4 Start
- **Week 1:** Triple barrier + meta-labeling (10h)
- **Week 2:** Fractional differentiation (8h) + Kafka+Flink start (8h)
- **Week 3:** Kafka+Flink completion (8h remaining) + CVaR (8h)
- **Week 4:** SHAP (6h) + Smart order routing (10h)

**Deliverables:** All Tier 3 complete, partial Tier 4

### Month 6: Production Hardening
- **Week 1:** Smart order routing completion + MEV protection (4h)
- **Week 2-4:** Integration testing, optimization, documentation (12h)

**Total:** 196 hours over 5-6 months (part-time: ~10h/week)

---

## Success Metrics by Tier

### Tier 1 (Immediate High ROI)
- [ ] Sharpe Ratio improvement > 25%
- [ ] Max Drawdown reduction > 20%
- [ ] PBO (Probability of Backtest Overfitting) < 0.5
- [ ] Optimization convergence 15% faster

### Tier 2 (Architecture)
- [ ] API latency < 100ms (async)
- [ ] Data insert rate > 10,000 ticks/sec (TimescaleDB)
- [ ] Forecast accuracy improvement > 10% (TFT)
- [ ] Drift detection catches regime changes within 2 days (River+ADWIN)

### Tier 3 (Advanced Strategies)
- [ ] Pairs trading Sharpe > 1.5
- [ ] Order execution slippage < 0.03%
- [ ] RL baseline profitability demonstrated
- [ ] Meta-labeling reduces false signals by 30%

### Tier 4 (Production)
- [ ] System handles 100,000+ events/second (Kafka+Flink)
- [ ] CVaR violations < 1% of trading days
- [ ] Model decisions explainable via SHAP
- [ ] Smart routing saves > 0.02% per trade
- [ ] Zero MEV sandwich attacks

---

## Risk & Dependencies

### Critical Risks
1. **CPCV Complexity:** Custom implementation may have bugs
   - **Mitigation:** Use MLFinLab library (£100/month) or thorough testing

2. **Regime Detection Overfitting:** HMM may fit noise
   - **Mitigation:** Out-of-sample validation, minimum regime duration

3. **ML Model Complexity:** TFT/RL may not beat simple strategies
   - **Mitigation:** Benchmark against current strategy, keep if Sharpe > 1.5

### Dependencies
- **Tier 2 depends on Tier 1:** Async architecture requires stable base
- **Tier 3 depends on Tier 2:** Advanced strategies need infrastructure
- **Tier 4 depends on Tier 3:** Production systems need proven strategies

---

## Quick Wins (Can Start Immediately)

1. **Optuna Multivariate TPE** (4h) - Zero dependencies, immediate 15-30% optimization improvement
2. **Dynamic Slippage** (6h) - Improves backtest realism immediately
3. **HMM Regime Detection** (6h) - Can run alongside current strategy

**Total Quick Wins:** 16 hours for 3 high-impact enhancements with no architectural changes required.

---

## Next Steps

**This Week:**
1. Review this roadmap with stakeholders
2. Prioritize: Confirm Tier 1 as starting point
3. Quick win: Implement Optuna multivariate TPE (4h)

**Next Week:**
4. Begin CPCV implementation (8h)
5. Set up testing framework for new components

**Month 1 Goal:**
Complete all Tier 1 enhancements (32h), measure improvement in Sharpe ratio and drawdown.

---

**Roadmap Status:** Living document, update after each tier completion
**Last Updated:** 2025-10-02
**Next Review:** After Tier 1 completion (est. 1 month)
