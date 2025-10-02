# Python Libraries for Quantitative Trading (2024)

**Last Updated:** 2025-10-02
**Focus:** Backtesting, optimization, data, analytics

---

## Executive Summary

| Category | THUNES Current | Recommended Upgrade | Priority |
|----------|---------------|---------------------|----------|
| Backtesting | vectorbt | Keep vectorbt | ✅ Good |
| Optimization | Optuna (basic TPE) | Optuna (multivariate TPE) | 🔥 High |
| Data/API | python-binance, ccxt | Add CCXT async | ⚡ Medium |
| Time-Series DB | None (CSV files) | TimescaleDB | 🔥 High |
| Analytics | Custom | Add QuantStats | ⚡ Medium |
| ML Library | None | Add River (online learning) | 📈 Low |
| Financial ML | None | MLFinLab (optional, £100/mo) | 💰 Low |

---

## 1. Backtesting Frameworks

### VectorBT (Current THUNES Choice) ⭐ Recommended

**Strengths:**
- **Speed:** Fully vectorized with NumPy/Numba, 100-1000x faster than Backtrader
- **Scalability:** Can backtest 1000 parameter combinations in seconds
- **Integration:** Works seamlessly with Optuna for optimization
- **THUNES Status:** Already implemented in `src/backtest/strategy.py`

**Weaknesses:**
- **Learning Curve:** Steeper than Backtrader
- **Documentation:** Incomplete (PRO version has better docs)
- **Development:** Free version maintenance-only (new features in PRO)

**Verdict:** **Keep using vectorbt** for THUNES. Speed critical for parameter optimization.

```python
# THUNES current usage
import vectorbt as vbt

# Fast parameter sweep
rsi_windows = [10, 14, 20, 30]
rsi_entry_thresholds = [-0.3, -0.4, -0.5]

pf = vbt.Portfolio.from_signals(
    close=df['close'],
    entries=entries,
    exits=exits,
    init_cash=10000,
    fees=0.001
)

print(pf.stats())
```

---

### Backtrader (Alternative)

**Strengths:**
- **Maturity:** Extensive documentation, large community
- **Live Trading:** Built-in broker integrations (IB, OANDA, Alpaca)
- **Learning:** Best for Python beginners

**Weaknesses:**
- **Speed:** Event-driven (slow), not suitable for large parameter sweeps
- **Development:** Stagnant since 2018

**Verdict:** Not recommended for THUNES. VectorBT's speed advantage is critical.

---

### Zipline (Not Recommended)

**Weaknesses:**
- **Legacy:** Quantopian closed in 2020
- **Maintenance:** Minimal updates
- **Focus:** Equity-centric (not crypto-friendly)

**Verdict:** Skip. Better alternatives available.

---

## 2. Optimization Libraries

### Optuna (Current) ⭐⭐⭐⭐⭐

**THUNES Status:** Implemented in `src/backtest/optimize.py`
**Version:** 3.5.0

**Current Usage (Basic):**
```python
import optuna

def objective(trial):
    rsi_window = trial.suggest_int('rsi_window', 10, 30)
    entry_threshold = trial.suggest_float('entry_threshold', -0.5, -0.2)
    # ... backtest with parameters
    return sharpe_ratio

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100)
```

**Recommended Upgrade (Multivariate TPE):**
```python
sampler = optuna.samplers.TPESampler(
    multivariate=True,     # 15-30% improvement!
    group=True,            # Parameter dependencies
    n_startup_trials=20
)

pruner = optuna.pruners.HyperbandPruner(
    min_resource=5,
    max_resource=100
)

study = optuna.create_study(
    sampler=sampler,
    pruner=pruner,
    direction='maximize'
)
```

**2024-2025 Updates:**
- **GPSampler (Sept 2025):** Gaussian Process Bayesian Optimization
- **Multivariate TPE:** Handles parameter interactions better
- **Hyperband Pruning:** Faster convergence than MedianPruner

**Action Item:** Upgrade to multivariate TPE (4-hour task, Tier 1 priority)

---

## 3. Data & Exchange APIs

### python-binance (Current) ✅

**THUNES Status:** `requirements.txt` version 1.0.19

**Pros:**
- Simple, well-documented
- Synchronous API (easier for beginners)
- Good for single exchange (Binance)

**Cons:**
- Binance-only
- Synchronous (blocks on API calls)
- No built-in rate limiting helpers

**Verdict:** Keep for MVP. Consider CCXT for multi-exchange support.

---

### CCXT (Recommended Addition) ⚡

**Why CCXT:**
- **100+ exchanges:** Unified API (Binance, Coinbase, Kraken, etc.)
- **Async Support:** `ccxt.async_support` with Python 3.7+ asyncio
- **WebSocket:** CCXT Pro (paid) has WebSocket streams
- **Normalization:** Consistent data format across exchanges

**Basic Usage:**
```python
import ccxt

exchange = ccxt.binance({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET',
    'enableRateLimit': True  # Built-in rate limiting!
})

ticker = exchange.fetch_ticker('BTC/USDT')
print(ticker['last'])
```

**Async Usage (Fast):**
```python
import ccxt.async_support as ccxt
import asyncio

async def fetch_multiple_tickers(symbols):
    exchange = ccxt.binance({'enableRateLimit': True})
    tasks = [exchange.fetch_ticker(symbol) for symbol in symbols]
    tickers = await asyncio.gather(*tasks)
    await exchange.close()
    return tickers

# Fetch 10 tickers in parallel
tickers = asyncio.run(fetch_multiple_tickers(['BTC/USDT', 'ETH/USDT', ...]))
```

**When to Upgrade:**
- ✅ Now: If testing strategies on multiple exchanges
- ⏳ Later: For multi-exchange arbitrage (Phase C)
- ⏳ Later: For async data fetching (Phase B)

---

## 4. Time-Series Databases

### TimescaleDB (Recommended) 🔥

**Why TimescaleDB:**
- **Performance:** 20x better insert rate than PostgreSQL
- **SQL Compatibility:** Use familiar SQL queries
- **Compression:** 90%+ compression for historical data
- **Continuous Aggregates:** Auto-compute OHLCV from ticks

**vs InfluxDB:**
| Feature | TimescaleDB | InfluxDB |
|---------|-------------|----------|
| Query Language | SQL | InfluxQL/Flux |
| Joins | ✅ Yes | ❌ Limited |
| Compression | 90%+ | Better (but NoSQL) |
| Learning Curve | Low (SQL) | Medium (new language) |
| Crypto Use Case | ✅ Excellent | ✅ Good |

**Setup for THUNES:**
```sql
-- Create hypertable for tick data
CREATE TABLE ticks (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    price NUMERIC(20,8),
    volume NUMERIC(20,8)
);

SELECT create_hypertable('ticks', 'time');

-- Continuous aggregate for 1-min OHLCV
CREATE MATERIALIZED VIEW ohlcv_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    symbol,
    first(price, time) AS open,
    max(price) AS high,
    min(price) AS low,
    last(price, time) AS close,
    sum(volume) AS volume
FROM ticks
GROUP BY bucket, symbol;
```

**Migration Plan:** Phase B (16 hours, already planned)

---

## 5. Analytics & Reporting

### QuantStats (Recommended Addition)

**Why QuantStats:**
- **Comprehensive Metrics:** Sharpe, Sortino, Calmar, Max DD, etc.
- **Tear Sheets:** HTML reports with plots
- **Benchmark Comparison:** Compare to BTC buy-and-hold

**Installation:**
```bash
pip install quantstats
```

**Usage:**
```python
import quantstats as qs

# Extend pandas for QuantStats
qs.extend_pandas()

# Calculate metrics
returns = strategy_returns  # pd.Series

print(f"Sharpe: {qs.stats.sharpe(returns):.2f}")
print(f"Sortino: {qs.stats.sortino(returns):.2f}")
print(f"Max DD: {qs.stats.max_drawdown(returns):.2%}")
print(f"Calmar: {qs.stats.calmar(returns):.2f}")

# Generate HTML tear sheet
qs.reports.html(returns, output='tearsheet.html', title='THUNES Strategy')

# Plot
qs.plots.snapshot(returns, title='Strategy Performance')
```

**THUNES Integration:**
```python
# In src/backtest/strategy.py

def generate_performance_report(backtest_results):
    """Generate QuantStats report for backtest."""
    import quantstats as qs

    returns = backtest_results['returns']
    benchmark = backtest_results['benchmark_returns']  # BTC buy-and-hold

    # Comparative tear sheet
    qs.reports.html(
        returns,
        benchmark=benchmark,
        output='reports/strategy_performance.html',
        title='THUNES vs Buy-and-Hold'
    )

    return {
        'sharpe': qs.stats.sharpe(returns),
        'sortino': qs.stats.sortino(returns),
        'calmar': qs.stats.calmar(returns),
        'max_drawdown': qs.stats.max_drawdown(returns),
        'win_rate': qs.stats.win_rate(returns)
    }
```

**Action Item:** Add QuantStats for better reporting (2-hour task)

---

## 6. Machine Learning - Online Learning

### River (Recommended for Tier 2)

**Why River:**
- **Online Learning:** Train incrementally (no batch retraining)
- **Drift Detection:** ADWIN automatically detects regime changes
- **Lightweight:** Faster than scikit-learn for streaming data

**Example:**
```python
from river import drift, linear_model, preprocessing, metrics

# Online logistic regression with drift detection
model = preprocessing.StandardScaler() | linear_model.LogisticRegression()
drift_detector = drift.ADWIN()
metric = metrics.Accuracy()

for x, y in data_stream:
    # Predict
    y_pred = model.predict_one(x)

    # Update metric
    metric.update(y, y_pred)

    # Train
    model.learn_one(x, y)

    # Drift detection
    drift_detector.update(int(y != y_pred))
    if drift_detector.drift_detected:
        print(f"Drift detected! Resetting model at sample {i}")
        model = preprocessing.StandardScaler() | linear_model.LogisticRegression()
```

**When to Use:**
- ✅ Tier 2: After async architecture (continuous learning)
- ✅ Non-stationary markets (crypto volatility)
- ❌ Not needed for simple technical strategies (THUNES MVP)

---

## 7. Financial Machine Learning - MLFinLab

### MLFinLab by Hudson & Thames (Optional)

**Pros:**
- **Complete:** CPCV, triple barrier, fractional differentiation, meta-labeling
- **Production-Ready:** Well-tested implementations
- **Documentation:** Comprehensive guides and examples

**Cons:**
- **Cost:** £100/month per user
- **Learning Curve:** Requires understanding Lopez de Prado's book

**Free Alternatives:**
- Custom implementation (8-hour CPCV task from roadmap)
- Use code from [ADVANCED-BACKTESTING.md](./ADVANCED-BACKTESTING.md)

**Verdict:** Optional. Implement custom CPCV first (Tier 1), evaluate MLFinLab later if scaling to multiple strategies.

---

## Recommended Additions for THUNES

### Immediate (Tier 1)
1. **Optuna Multivariate TPE** - 4 hours, 15-30% optimization improvement
2. **QuantStats** - 2 hours, better performance reporting

### Short-Term (Tier 2)
3. **CCXT Async** - 4 hours, multi-exchange + async data fetching
4. **TimescaleDB** - 16 hours (already planned), production data storage

### Medium-Term (Tier 3)
5. **River + ADWIN** - 12 hours, online learning with drift detection

### Optional
6. **MLFinLab** - £100/month OR custom implementations (Tier 1 roadmap)

---

## Installation Commands

```bash
# Current THUNES (Phase A complete)
pip install python-binance==1.0.19 vectorbt==0.26.2 optuna==3.5.0

# Tier 1 additions
pip install quantstats

# Tier 2 additions
pip install ccxt==4.2.25 river==0.21.0

# TimescaleDB (requires PostgreSQL)
# See: https://docs.timescale.com/install/latest/

# Optional
pip install mlfinlab  # Requires subscription
```

---

## Comparison Table

| Library | Current | Speed | Learning Curve | THUNES Fit | Priority |
|---------|---------|-------|----------------|------------|----------|
| **vectorbt** | ✅ | ⚡⚡⚡⚡⚡ | Medium | Perfect | Keep |
| **Backtrader** | ❌ | ⚡ | Easy | Poor | Skip |
| **Optuna** | ✅ (basic) | ⚡⚡⚡⚡ | Easy | Excellent | Upgrade |
| **python-binance** | ✅ | ⚡⚡⚡ | Easy | Good | Keep |
| **CCXT** | ❌ | ⚡⚡⚡⚡ | Medium | Future | Add Later |
| **TimescaleDB** | ❌ | ⚡⚡⚡⚡⚡ | Medium | Excellent | Add (Tier 2) |
| **QuantStats** | ❌ | ⚡⚡⚡ | Easy | Excellent | Add (Tier 1) |
| **River** | ❌ | ⚡⚡⚡⚡ | Medium | Good | Add (Tier 2) |
| **MLFinLab** | ❌ | ⚡⚡⚡ | Hard | Optional | Evaluate |

---

**Next:** See [IMPLEMENTATION-ROADMAP.md](./IMPLEMENTATION-ROADMAP.md) for integration timeline.
