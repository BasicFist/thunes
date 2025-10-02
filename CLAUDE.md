# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# THUNES - Quantitative Crypto Trading System

## Project Overview

THUNES is a quantitative cryptocurrency trading system implementing micro-transaction strategies (DCA, Grid, HFT) with comprehensive risk management and automated execution. Currently in **MVP Development** phase, targeting Binance Spot Testnet with an SMA Crossover baseline strategy.

**Core Philosophy**: Safety-first, iterative development with rigorous testing before production deployment.

## Essential Commands

### Development Workflow

```bash
# Setup (first time)
python3.12 -m venv .venv
source .venv/bin/activate
make install                 # Install deps + pre-commit hooks

# Code Quality
make test                    # Run pytest with coverage
make lint                    # ruff + mypy type checking
make format                  # black + ruff auto-fix
make pre-commit             # Run all pre-commit hooks

# Trading Operations
make backtest               # Backtest SMA strategy (default: BTCUSDT 1h, 90 days)
make optimize               # Optuna hyperparameter optimization (25 trials)
make paper                  # Execute single paper trade on testnet
make balance                # Check testnet balance

# Monitoring
make logs                   # Tail all logs
cat logs/paper_trader.log   # View trading logs
cat artifacts/backtest/stats_BTCUSDT_1h.csv  # Backtest results
```

### Testing Specific Components

```bash
# Run individual test files
pytest tests/test_strategy.py -v
pytest tests/test_filters.py -v      # Critical: order filter validation
pytest tests/test_circuit_breaker.py -v
pytest tests/test_rate_limiter.py -v

# Run single test
pytest tests/test_filters.py::TestExchangeFilters::test_round_price -v

# GPU benchmark (if NVIDIA GPU available)
python tests/benchmarks/gpu_vs_cpu_benchmark.py
```

### Docker Operations

```bash
make docker-build           # Build image
make docker-run             # Start container (docker-compose)
make docker-stop            # Stop container
```

## Architecture & Code Organization

### High-Level Architecture

```
THUNES/
├── src/
│   ├── backtest/           # Vectorbt backtesting engine
│   │   ├── strategy.py     # SMAStrategy with vectorbt Portfolio
│   │   └── run_backtest.py # CLI entry point
│   │
│   ├── optimize/           # Bayesian optimization (Optuna)
│   │   └── run_optuna.py   # TPE sampler for hyperparameters
│   │
│   ├── live/               # Paper & live trading
│   │   └── paper_trader.py # PaperTrader with order execution
│   │
│   ├── filters/            # CRITICAL: Exchange order validation
│   │   └── exchange_filters.py  # Prevents -1013 errors
│   │
│   ├── data/               # Data fetching & processing
│   │   ├── binance_client.py    # Binance API wrapper
│   │   └── processors/
│   │       └── gpu_features.py  # GPU feature engineering (cuDF/RAPIDS)
│   │
│   ├── models/             # Machine learning models
│   │   ├── xgboost_gpu.py      # GPU-accelerated XGBoost
│   │   ├── position.py         # Position tracking
│   │   └── schemas.py          # Pydantic data models
│   │
│   ├── utils/              # Utilities
│   │   ├── logger.py           # Centralized logging
│   │   ├── circuit_breaker.py  # Fault tolerance
│   │   └── rate_limiter.py     # API rate limiting
│   │
│   ├── risk/               # Risk management (Phase 8)
│   ├── alerts/             # Telegram notifications (Phase 9)
│   └── config.py           # Pydantic settings from .env
│
├── tests/                  # Pytest test suite
│   ├── test_*.py           # Unit tests
│   └── benchmarks/         # Performance benchmarks
│       └── gpu_vs_cpu_benchmark.py
│
├── artifacts/              # Generated outputs
│   ├── backtest/           # Backtest results (CSV)
│   └── optuna/             # Optimization studies
│
├── logs/                   # Application logs
└── .github/workflows/      # CI/CD pipelines
    ├── ci.yml              # Lint + test on push/PR
    ├── backtest.yml        # Weekly backtesting
    ├── optimize.yml        # Manual optimization
    └── paper.yml           # Paper trading (10min intervals)
```

### Critical Module: Exchange Filters

**Location**: `src/filters/exchange_filters.py`

The `ExchangeFilters` class is **mission-critical** for preventing order rejections (-1013 errors). It validates and adjusts orders against Binance exchange rules:

- **Tick Size**: Minimum price increment (e.g., 0.01 for BTCUSDT)
- **Step Size**: Minimum quantity increment (e.g., 0.00001 BTC)
- **Min Notional**: Minimum order value (e.g., 10 USDT)

**Usage Pattern**:
```python
from src.filters.exchange_filters import ExchangeFilters

filters = ExchangeFilters(client)

# Validate before placing order
is_valid, msg = filters.validate_order(symbol="BTCUSDT", quote_qty=10.0)
if not is_valid:
    raise ValueError(f"Order validation failed: {msg}")

# Prepare market order with automatic validation
order_params = filters.prepare_market_order(
    symbol="BTCUSDT",
    side="BUY",
    quote_qty=10.0
)
```

**Testing**: Always run `pytest tests/test_filters.py -v` after modifying order logic.

### GPU Infrastructure

**Status**: ✅ Implemented but **NOT recommended for daily trading**

The project includes GPU-accelerated components for future HFT use cases:

1. **Feature Engineering** (`src/data/processors/gpu_features.py`):
   - Uses NVIDIA RAPIDS cuDF for 60-100x speedup on minute/tick data
   - **Benchmark finding**: GPU is 5-6x **slower** than CPU for daily OHLCV data
   - Transfer overhead (~180ms) dominates computation time (~30ms CPU vs ~5ms GPU)
   - **Use GPU only for**: HFT (98k+ rows/year), multi-symbol portfolios (100+ symbols)

2. **XGBoost GPU Model** (`src/models/xgboost_gpu.py`):
   - Validated 5-46x speedup for model training on large datasets
   - GPU training: ~35 sec vs CPU training: ~27 min (5.5M rows)
   - **Recommended for**: ML model training, prediction at scale

**Current Recommendation**: Use CPU for daily trading (Phases 3-14). Reserve GPU for ML research and HFT experiments.

See `docs/research/GPU-INFRASTRUCTURE-FINDINGS.md` for detailed benchmarks.

### Strategy Implementation Pattern

The project uses **vectorized backtesting** with vectorbt for speed:

```python
# In src/backtest/strategy.py
class SMAStrategy:
    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        # CRITICAL: Shift close prices to prevent look-ahead bias
        close = df["close"].shift(1)

        fast_sma = vbt.MA.run(close, self.fast_window)
        slow_sma = vbt.MA.run(close, self.slow_window)

        entries = fast_sma.ma_crossed_above(slow_sma)
        exits = fast_sma.ma_crossed_below(slow_sma)

        return entries, exits

    def backtest(self, df: pd.DataFrame, ...) -> vbt.Portfolio:
        # Adjust price for slippage (realistic modeling)
        price = df["close"] * (1 + slippage)

        return vbt.Portfolio.from_signals(
            close=price,
            entries=entries,
            exits=exits,
            init_cash=initial_capital,
            fees=fees
        )
```

**Key Pattern**: Always shift signals by 1 period to avoid look-ahead bias. Vectorbt's `from_signals()` method handles position sizing and portfolio accounting.

### Configuration Management

**Location**: `src/config.py`

Uses Pydantic for type-safe configuration from `.env`:

```python
from src.config import settings

# Environment-aware API credentials
api_key = settings.api_key      # Auto-selects testnet or prod
api_secret = settings.api_secret

# Risk parameters
if settings.is_production:
    # Extra validation for live trading
    assert settings.max_daily_loss < 100.0
```

**Environment Variables** (`.env`):
```bash
# Binance (Testnet)
BINANCE_TESTNET_API_KEY=your_key
BINANCE_TESTNET_API_SECRET=your_secret

# Trading
ENVIRONMENT=testnet  # or "paper" or "live"
DEFAULT_SYMBOL=BTCUSDT
DEFAULT_TIMEFRAME=1h
DEFAULT_QUOTE_AMOUNT=10.0

# Risk Management (Phase 8)
MAX_LOSS_PER_TRADE=5.0
MAX_DAILY_LOSS=20.0
MAX_POSITIONS=3
COOL_DOWN_MINUTES=60
```

## Development Phases & Status

| Phase | Description | Status | Key Files |
|-------|-------------|--------|-----------|
| 0 | Prerequisites & Setup | ✅ | `.env`, `requirements.txt` |
| 1 | Import & Setup | ✅ | `.pre-commit-config.yaml` |
| 2 | Smoke Tests | ✅ | `tests/test_*.py` |
| 3 | Backtest MVP | ✅ | `src/backtest/` |
| 4 | Optimization | ✅ | `src/optimize/run_optuna.py` |
| 5 | Paper Trading | ✅ | `src/live/paper_trader.py` |
| 6 | Order Filters | ✅ | `src/filters/exchange_filters.py` |
| 7 | WebSocket Streaming | 🚧 | `src/data/ws_stream.py` (to create) |
| 8 | Risk Management | 🚧 | `src/risk/manager.py` (to create) |
| 9 | Alerts | 🚧 | `src/alerts/telegram.py` (to create) |
| 10 | Orchestration | 🚧 | APScheduler jobs |
| 11 | Observability | 🚧 | Prometheus metrics |
| 12 | CI/CD | ✅ | `.github/workflows/*.yml` |
| 13 | Paper 24/7 | ⏳ | 7-day rodage |
| 14 | Micro-Live | ⏳ | 10-50€ live |

**Legend**: ✅ Complete | 🚧 In Progress | ⏳ Pending

### Phase 7: WebSocket Streaming (Next Priority)

**Goal**: Real-time bookTicker/aggTrade for faster signal detection

**Implementation Pattern**:
```python
# src/data/ws_stream.py (to create)
from binance.streams import ThreadedWebsocketManager

class BinanceWSStream:
    def __init__(self, symbol: str):
        self.twm = ThreadedWebsocketManager(api_key=..., api_secret=...)
        self.twm.start()

    def start_book_ticker(self, callback):
        self.twm.start_symbol_book_ticker_socket(
            callback=callback,
            symbol=self.symbol
        )

    # Implement reconnection logic (exponential backoff)
    # Add ping/pong watchdog for connection health
```

**Testing Requirements**:
- 1+ hour stability test
- Reconnection after network interruption
- Graceful degradation to REST if WebSocket fails

## Code Quality & Standards

### Type Safety

**Strict mypy configuration** in `pyproject.toml`:
```toml
[tool.mypy]
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
```

**All functions must have type hints**:
```python
def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI indicator.

    Args:
        prices: Close price series
        period: RSI period (default: 14)

    Returns:
        RSI values (0-100)
    """
    delta = prices.diff()
    # ... implementation
    return rsi
```

### Testing Standards

- **Unit tests**: All utility functions and models
- **Integration tests**: Order execution, filter validation
- **Benchmarks**: Performance-critical paths (GPU vs CPU)
- **Coverage target**: >80% (enforced in CI)

**Run tests before committing**:
```bash
make test           # Full test suite
make pre-commit     # All quality checks
```

### Pre-commit Hooks

Automatically run on `git commit`:
- `black`: Code formatting (line-length: 100)
- `ruff`: Linting (pycodestyle, pyflakes, isort)
- `mypy`: Type checking
- `pytest`: Unit tests (optional, can be slow)

**Bypass for WIP commits** (use sparingly):
```bash
git commit --no-verify -m "WIP: debugging strategy"
```

## Risk Management Framework

### Hard Limits (Non-Negotiable)

**Configured in `.env`**:
```bash
MAX_LOSS_PER_TRADE=5.0      # USDT
MAX_DAILY_LOSS=20.0         # USDT
MAX_POSITIONS=3             # Concurrent trades
COOL_DOWN_MINUTES=60        # After loss
```

**Implementation Pattern (Phase 8)**:
```python
# src/risk/manager.py (to create)
class RiskManager:
    def validate_trade(self, quote_qty: float) -> tuple[bool, str]:
        # Check daily loss limit
        if self.daily_loss >= settings.max_daily_loss:
            return False, "KILL_SWITCH: Daily loss limit exceeded"

        # Check per-trade limit
        if quote_qty > settings.max_loss_per_trade:
            return False, f"Trade size {quote_qty} exceeds max {settings.max_loss_per_trade}"

        # Check position count
        if len(self.open_positions) >= settings.max_positions:
            return False, "Max position limit reached"

        return True, "OK"
```

### Kill-Switch Testing

**Before going live** (Phase 14):
```bash
# Manually trigger max loss to verify kill-switch
# 1. Set MAX_DAILY_LOSS=10.0 in .env
# 2. Execute losing trades until limit hit
# 3. Verify trading stops and Telegram alert sent
```

## CI/CD Workflows

### GitHub Actions Pipelines

**CI (`.github/workflows/ci.yml`)**:
- Triggers: Push to `main`/`develop`, all PRs
- Jobs: ruff, black, mypy, pytest with coverage
- Codecov integration (coverage reports)

**Backtest (`.github/workflows/backtest.yml`)**:
- Triggers: Weekly schedule, manual dispatch
- Generates artifacts for historical performance tracking

**Optimize (`.github/workflows/optimize.yml`)**:
- Triggers: Manual only
- Runs Optuna with 25 trials, uploads study results

**Paper Trading (`.github/workflows/paper.yml`)**:
- Triggers: Every 10 minutes (requires manual approval)
- Uses testnet API keys from GitHub Secrets

### Required GitHub Secrets

**Navigate to**: Settings → Secrets → Actions

```bash
BINANCE_TESTNET_API_KEY=your_testnet_key
BINANCE_TESTNET_API_SECRET=your_testnet_secret
TELEGRAM_BOT_TOKEN=your_bot_token       # Optional
TELEGRAM_CHAT_ID=your_chat_id           # Optional
```

**Variables**:
```bash
TZ=Europe/Paris
```

## Common Debugging Patterns

### "Filter failure: -1013" (Order Rejection)

**Root cause**: Order violates exchange filters (tick/step/notional)

**Debug steps**:
```bash
# 1. Check exchange filters
python -c "
from binance.client import Client
from src.config import settings
client = Client(settings.api_key, settings.api_secret, testnet=True)
from src.filters.exchange_filters import ExchangeFilters
filters = ExchangeFilters(client)
print(f'Tick size: {filters.get_tick_size(\"BTCUSDT\")}')
print(f'Step size: {filters.get_step_size(\"BTCUSDT\")}')
print(f'Min notional: {filters.get_min_notional(\"BTCUSDT\")}')
"

# 2. Validate test order
python -c "
from src.filters.exchange_filters import ExchangeFilters
# ... (client setup)
is_valid, msg = filters.validate_order('BTCUSDT', quote_qty=10.0)
print(f'Valid: {is_valid}, Message: {msg}')
"

# 3. Run filter tests
pytest tests/test_filters.py -v
```

### GPU Not Available (cuDF Import Error)

**Expected behavior**: Automatic CPU fallback

```python
# In src/data/processors/gpu_features.py
try:
    import cudf
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    warnings.warn("cuDF not available. Using CPU fallback.")
```

**To install GPU support** (requires CUDA 11.2+):
```bash
conda install -c rapidsai -c conda-forge cudf
```

**Verify GPU**:
```bash
python -c "import cudf; print(cudf.__version__)"
python tests/benchmarks/gpu_vs_cpu_benchmark.py
```

### Insufficient Balance (Testnet)

**Solution**:
1. Request testnet funds: https://testnet.binance.vision/
2. Or reduce quote amount:
   ```bash
   # In .env
   DEFAULT_QUOTE_AMOUNT=5.0  # Reduce from 10.0
   ```

## Important Reminders

### Safety Checklist

1. **Always test on testnet first** - Never skip to production
2. **Validate order filters** - Run `pytest tests/test_filters.py` before deploying
3. **Test kill-switch manually** - Trigger max loss scenario before Phase 14
4. **Start small** - 10-50 EUR when going live (Phase 14)
5. **Monitor daily** - Check logs and PnL every 24h minimum
6. **One change at a time** - Don't modify multiple parameters simultaneously

### Production Deployment Guards

**Before setting `ENVIRONMENT=live`**:
- [ ] Phase 13 (Paper 24/7) completed successfully
- [ ] Kill-switch tested and verified
- [ ] Telegram alerts working
- [ ] CI green for 2+ weeks
- [ ] API keys have trading-only permissions (no withdrawals)
- [ ] Manual approval from project owner

### Data Quality

**Look-ahead bias prevention**:
```python
# ALWAYS shift signals by 1 period in backtesting
close = df["close"].shift(1)  # Use previous bar for signal generation
```

**Realistic slippage modeling**:
```python
# In backtesting, adjust price for slippage + fees
price = df["close"] * (1 + slippage)  # e.g., slippage=0.0005 (0.05%)
```

## Key Technologies & Documentation

- **Backtesting**: [vectorbt](https://vectorbt.dev/) - Vectorized portfolio simulation
- **Optimization**: [Optuna](https://optuna.org/) - Bayesian hyperparameter tuning (TPE)
- **Exchange**: [python-binance](https://github.com/sammchardy/python-binance) - Binance API wrapper
- **ML**: [XGBoost](https://xgboost.readthedocs.io/) - Gradient boosting (GPU-accelerated)
- **GPU**: [RAPIDS cuDF](https://docs.rapids.ai/api/cudf/stable/) - GPU DataFrames (60-100x speedup on HFT data)
- **Monitoring**: Prometheus + Loki (Phase 11)
- **Scheduling**: APScheduler (Phase 10)

## Additional Resources

- **Research Docs**: `docs/research/` - Quantitative techniques, GPU benchmarks, ML strategies
- **Setup Guide**: `SETUP.md` - Detailed phase-by-phase instructions
- **Binance Testnet**: https://testnet.binance.vision/
- **Binance API Docs**: https://binance-docs.github.io/apidocs/spot/en/

---

**Last Updated**: 2025-10-02 by Claude Code
