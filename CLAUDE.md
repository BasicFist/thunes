# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# THUNES - Quantitative Crypto Trading System

THUNES is a quantitative cryptocurrency trading system with micro-transaction strategies, risk management, and automated execution. Currently in **Phase 11-13** targeting Binance Spot Testnet.

**Philosophy**: Safety-first, iterative development, rigorous testing before production.

## Quick Reference

**Critical Files to Know**:
- `src/filters/exchange_filters.py:122` - Order validation (prevents -1013 errors)
- `src/risk/manager.py:68` - Kill-switch and position limits
- `src/data/ws_stream.py:62` - WebSocket reconnection logic
- `src/config.py` - Pydantic settings from `.env`
- `logs/audit_trail.jsonl` - Immutable regulatory audit trail

**Before Phase 13 Deployment**:
1. Run `pytest tests/test_filters.py tests/test_risk_manager.py -v`
2. Verify kill-switch: `pytest tests/test_risk_manager.py::test_kill_switch_activation -v`
3. Check WebSocket reconnection: `pytest tests/test_ws_stream.py::test_reconnection_on_error -v`
4. Test Telegram alerts: `python scripts/verify_telegram.py`
5. Review audit trail: `scripts/validate_audit_trail.py`

**Emergency Diagnostics**:
```bash
# System health
make test && tail -f logs/paper_trader.log

# Check specific component
python -c "from src.risk.manager import RiskManager; from src.models.position import PositionTracker; rm = RiskManager(position_tracker=PositionTracker()); print(rm.get_risk_status())"
```

## Essential Commands

### Daily Development Workflow

```bash
# First-time setup
python3.12 -m venv .venv && source .venv/bin/activate
make install                 # Install deps + pre-commit hooks

# Before committing
make test                    # Run pytest with coverage (105 tests)
make lint                    # ruff + mypy type checking
make format                  # black + ruff auto-fix
make pre-commit             # Run all quality checks

# Trading operations
make backtest               # Backtest SMA strategy (BTCUSDT 1h, 90 days)
make optimize               # Optuna hyperparameter tuning (25 trials)
make paper                  # Execute single paper trade on testnet
make balance                # Check testnet balance

# Monitoring & debugging
make logs                   # Tail all logs
tail -f logs/paper_trader.log           # Trading activity
tail -f logs/audit_trail.jsonl | jq '.' # Audit trail (regulatory)
cat artifacts/backtest/stats_BTCUSDT_1h.csv  # Backtest metrics
```

### Critical Component Tests

```bash
# Must-run before deployment (execution-critical)
pytest tests/test_filters.py -v         # Order filter validation
pytest tests/test_risk_manager.py -v    # Kill-switch, limits, cool-down
pytest tests/test_circuit_breaker.py -v # Fault tolerance
pytest tests/test_ws_stream.py -v       # WebSocket reconnection

# Integration & performance
pytest tests/test_paper_trader_integration.py -v
python tests/benchmarks/gpu_vs_cpu_benchmark.py  # GPU vs CPU (if available)

# Run single test
pytest tests/test_filters.py::TestExchangeFilters::test_round_price -v
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

### Critical Module: Exchange Filters (`src/filters/exchange_filters.py`)

**Mission-critical** for preventing -1013 order rejections. Validates tick size, step size, min notional.
**Key API**: `filters.validate_order(symbol, quote_qty)`, `filters.prepare_market_order(symbol, side, quote_qty)`
**Test**: `pytest tests/test_filters.py -v`

### Circuit Breaker (`src/utils/circuit_breaker.py`)

Prevents cascading failures. **States**: CLOSED (normal), OPEN (blocking), HALF_OPEN (testing recovery).
**Usage**: `@with_circuit_breaker()` decorator or `circuit_monitor.is_open("name")`.
**Bug Fixed** (2025-10-03): Thread-safe state transitions, proper lock handling.
**Integration**: RiskManager checks circuit breaker before trade validation.

### GPU Infrastructure ✅ (NOT Recommended for Daily Trading)

**Feature Engineering** (`src/data/processors/gpu_features.py`): RAPIDS cuDF 60-100x faster for HFT data, but 5-6x **slower** for daily OHLCV (transfer overhead). Use GPU only for 98k+ rows/year or 100+ symbols.
**XGBoost** (`src/models/xgboost_gpu.py`): 5-46x training speedup (35s vs 27min for 5.5M rows). Recommended for ML training only.
**Current**: CPU for daily trading (Phases 3-14), GPU for ML research. See `docs/research/GPU-INFRASTRUCTURE-FINDINGS.md`.

### Strategy Pattern (Vectorbt)

**CRITICAL**: Always `shift(1)` to prevent look-ahead bias. Adjust price for slippage. See `src/backtest/strategy.py` for SMAStrategy example.

### Configuration (`src/config.py`)

Pydantic settings from `.env`. **Key variables**: `ENVIRONMENT` (testnet/paper/live), API keys, `DEFAULT_SYMBOL`, `DEFAULT_QUOTE_AMOUNT`, risk limits (`MAX_DAILY_LOSS`, `MAX_POSITIONS`, `COOL_DOWN_MINUTES`).

## Development Phases & Status

| Phase | Description | Status | Key Files |
|-------|-------------|--------|-----------|
| 0 | Prerequisites & Setup | ✅ | `.env`, `requirements.txt` |
| 1 | Import & Setup | ✅ | `.pre-commit-config.yaml` |
| 2 | Smoke Tests | ✅ | `tests/test_*.py` (105 tests) |
| 3 | Backtest MVP | ✅ | `src/backtest/strategy.py` |
| 4 | Optimization | ✅ | `src/optimize/run_optuna.py` |
| 5 | Paper Trading | ✅ | `src/live/paper_trader.py` |
| 6 | Order Filters | ✅ | `src/filters/exchange_filters.py` |
| 7 | WebSocket Streaming | ✅ | `src/data/ws_stream.py` |
| 8 | Risk Management | ✅ | `src/risk/manager.py` |
| 9 | Alerts | ✅ | `src/alerts/telegram.py` |
| 10 | Orchestration | ✅ | `src/orchestration/scheduler.py` |
| 11 | Observability | 🚧 | `src/monitoring/performance_tracker.py` |
| 12 | CI/CD | ✅ | `.github/workflows/*.yml` |
| 13 | Paper 24/7 | ⏳ | 7-day rodage |
| 14 | Micro-Live | ⏳ | 10-50€ live |

**Legend**: ✅ Complete | 🚧 In Progress | ⏳ Pending

**Recent Milestones** (2025-10-06):
- ✅ Phases 1-10 complete (backtesting, risk mgmt, orchestration, alerts)
- ✅ Security audit + automated scanning implemented
- ✅ **Phase 13 Sprint 1 COMPLETE** - Concurrency validation (12/12 tests passing)
- 🚧 Phase 11 in progress (Prometheus metrics pending)
- ⏳ Phase 13 testnet rodage ready to begin

## Code Quality & Standards

### Code Quality

**Type Safety**: Strict mypy (all functions require type hints). See `pyproject.toml`.
**Testing**: 228 tests (>80% coverage). Critical: `test_filters.py`, `test_risk_manager.py`, `test_risk_manager_concurrent.py`, `test_circuit_breaker.py`, `test_ws_stream.py`.
**Concurrency**: 12 dedicated thread-safety tests validate RiskManager under concurrent load (Phase 13 Sprint 1).
**Pre-commit**: black, ruff, mypy auto-run on commit. Bypass: `git commit --no-verify` (use sparingly).
**Commands**: `make test`, `make lint`, `make format`, `make pre-commit`

## Risk Management Framework ✅ (`src/risk/manager.py`)

**Status**: Production-ready with audit trail and Telegram integration

**Hard Limits** (`.env`): `MAX_LOSS_PER_TRADE=5.0`, `MAX_DAILY_LOSS=20.0`, `MAX_POSITIONS=3`, `COOL_DOWN_MINUTES=60`

### Features
1. **Kill-Switch**: Auto-halt when daily loss ≥ MAX_DAILY_LOSS, Telegram alert, manual deactivation required
2. **Position Limits**: Max 3 concurrent, prevents duplicate symbols
3. **Cool-Down**: 60min pause after loss, cleared on win
4. **Audit Trail**: Immutable JSONL (`logs/audit_trail.jsonl`), logs all decisions

**Key API**: `risk_manager.validate_trade(symbol, quote_qty, side, strategy_id)` returns `(is_valid, reason)`

### Telegram Alerts (`src/alerts/telegram.py`)
**Setup**: Create bot via @BotFather, add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to `.env`
**Alerts**: Kill-switch, parameter decay (Sharpe < 1.0), daily summary, re-optimization
**Test**: `pytest tests/test_risk_manager.py::test_kill_switch_activation -v`

## CI/CD Workflows (`.github/workflows/`)

**ci.yml**: Lint + test on push/PR (ruff, black, mypy, pytest + coverage)
**backtest.yml**: Weekly + manual (generates historical artifacts)
**optimize.yml**: Manual only (Optuna 25 trials)
**paper.yml**: Every 10min (manual approval required)

**GitHub Secrets**: `BINANCE_TESTNET_API_KEY`, `BINANCE_TESTNET_API_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Troubleshooting

**Quick Diagnostics**: `make test`, `make logs`, `tail -f logs/paper_trader.log`, `tail -f logs/audit_trail.jsonl | jq '.'`

**Common Issues**:
- **-1013 Order Rejection**: `pytest tests/test_filters.py -v`, check tick/step/notional
- **WebSocket Disconnect**: Check logs, verify API keys not expired
- **Kill-Switch**: Verify `.env` has `MAX_DAILY_LOSS`, test: `pytest tests/test_risk_manager.py`
- **Telegram**: Check `.env` has `TELEGRAM_BOT_TOKEN`, test with `TelegramBot().send_message_sync("test")`
- **Balance**: Get testnet funds at testnet.binance.vision, check: `make balance`

See `docs/OPERATIONAL-RUNBOOK.md` for disaster recovery.

## Known Critical Issues ⚠️ (2025-10-06 Audit - Phase 13 Sprint 1 Complete)

**Status**: 0 blockers remaining. Sprint 1 resolved all HIGH-severity issues. All validation paths confirmed audit-complete.
**Last Review**: 2025-10-06 (Phase 13 Sprint 1.10 complete, 228/228 tests passing)

### Fixed in Sprint 1 ✅
1. **WebSocket Watchdog Deadlock** - ✅ **FIXED** via reconnect queue pattern (Sprint 1.0)
2. **Missing Concurrency Tests** - ✅ **FIXED** via 12 comprehensive thread-safety tests (Sprint 1.4-1.9)
   - TOCTOU race conditions validated with atomic `count_open_positions()` API
   - Kill-switch, cool-down, position limits tested under concurrent load
   - Application-level locking pattern documented for validate-then-act gaps
3. **SQLite Threading Issues** - ✅ **FIXED** file-based databases for multi-threaded access (Sprint 1.6)
4. **Position Tracker API Bugs** - ✅ **FIXED** sqlite3.Row attribute handling (Sprint 1.7)

### Removed False Positives ✅ (Sprint 1.10)
1. **Incomplete Audit Trail Coverage** - Code review confirmed ALL 8 validation paths in `validate_trade()` have complete audit logging (kill-switch, daily loss, per-trade limit, max positions, duplicate, cool-down, circuit breaker, success). Previously misidentified as MEDIUM issue.

### Future Enhancements (Phase 13 Sprint 2+)
- **WebSocket Thread Blocking** (`src/data/ws_stream.py:181-198`) - Message queue + processing thread for 24/7 stability (Sprint 2)
- **Audit Schema Versioning** - Add Pydantic `AuditEvent` model (`src/models/audit_schema.py`) (Sprint 2)
- **Prometheus Metrics** - Kill-switch/circuit breaker state tracking (Phase 11)

## Audit & Compliance

**Status**: ✅ Audit-ready for Phase 13/14 | **Last Scan**: 2025-10-03 | **Next Review**: 2026-01-03 (quarterly)

### Key Documents
- `docs/OPERATIONAL-RUNBOOK.md` - Disaster recovery, failure scenarios, monitoring checklists
- `docs/VENDOR-RISK-ASSESSMENT.md` - Binance security controls, incident response
- `docs/research/REGULATORY-ML-LANDSCAPE-2025.md` - Industry compliance benchmarks ($6.3B fines in 2025)
- `.github/workflows/security.yml` - Automated SAST/DAST scanning (Bandit, pip-audit, TruffleHog, CodeQL)

### Control Summary (6 Layers)
1. **Security**: Automated scanning, circuit breaker, WebSocket reconnection, 228 tests (12 concurrency)
2. **Risk Planning**: Immutable audit trail, runbook, API key rotation (testnet: 90d, prod: 30d)
3. **Transaction Assurance**: Kill-switch, position limits, cool-down, audit trail (JSONL)
4. **Third-Party**: Vendor risk assessed, HMAC-SHA256 auth, withdrawal-disabled keys
5. **Model Validation**: Mypy strict, 90+ day backtests, walk-forward, Optuna
6. **AML/KYC**: Exchange-level (Binance handles), audit trail for tax exports

### Pre-Deployment Checklist
**Phase 13** (Testnet): Security scan, API key permissions verified, 2FA enabled, disaster recovery tested
**Phase 14** (Live): Position reconciliation, secrets manager (AWS/Vault), kill-switch tested, chaos tests, 7-day rodage complete

### Compliance Gaps (Acceptable for MVP)
- ⏳ Position reconciliation (Phase 14 - 8h)
- ⏳ Chaos testing (Phase 14 - 8h)
- ⏳ Prometheus metrics (Phase 11)

## Important Reminders

**Safety**: Test on testnet first, validate filters before deploy, test kill-switch manually, start small (10-50€), monitor daily, one change at a time.

**Production Guards**: Complete Phase 13 rodage, kill-switch tested, Telegram working, CI green 2+ weeks, withdrawal-disabled API keys, manual approval.

**Data Quality**: Always `shift(1)` signals (prevent look-ahead bias), adjust price for slippage in backtests.

## AI/ML Roadmap (Post-Phase 14)

**Philosophy**: CPU-first serving (<10ms), GPU-only training. Detailed roadmap in `docs/research/REGULATORY-ML-LANDSCAPE-2025.md`.

**Planned Enhancements (Phases 15-18)**:
- **Phase 15**: Triple-barrier labeling, meta-labeling gates (40-50% FP reduction target)
- **Phase 16**: RL agents (FinRL/TradeMaster), Kelly sizing, order flow features (12-15% annualized return target)
- **Phase 17**: Model registry, SHAP explainability, compliance automation (<$50K/year costs vs $620K industry avg)
- **Phase 18**: Multi-strategy ensemble, automated walk-forward, HFT evaluation (nautilus_trader)

**Key Frameworks**: River (drift detection), XGBoost/LightGBM, SHAP, Optuna NSGA-II, freqtrade (production deployment)

## Key Technologies

**Core**: vectorbt (backtesting), Optuna (optimization), python-binance, APScheduler, Prometheus + Loki (Phase 11)
**ML** (Phase 15+): XGBoost, LightGBM, River (drift), SHAP (explainability), RAPIDS cuDF (GPU research), ONNX Runtime

## Resources

**Docs**: `docs/research/` (REGULATORY-ML-LANDSCAPE-2025.md, GPU-INFRASTRUCTURE-FINDINGS.md), `docs/` (OPERATIONAL-RUNBOOK.md, VENDOR-RISK-ASSESSMENT.md, SETUP.md)
**External**: Binance Testnet (testnet.binance.vision), API Docs (binance-docs.github.io), FinRL (github.com/AI4Finance-Foundation/FinRL), freqtrade (github.com/freqtrade/freqtrade)

## Common Workflows

**New Strategy**: Create `src/backtest/my_strategy.py` (remember `shift(1)`), add test, run validation.

**Order Rejection (-1013)**: Check filters (`pytest tests/test_filters.py -v`), grep logs for "1013|filter".

**Kill-Switch Test**: Set `MAX_DAILY_LOSS=10.0`, trigger manually, verify Telegram alert, test deactivation.

**Deploy Parameters**: Run `make optimize`, review Pareto frontier, update strategy, walk-forward validation, deploy if Sharpe > 1.5.

---

**Last Updated**: 2025-10-06 by Claude Code

**Recent Changes**:
- 2025-10-06: **PHASE 13 SPRINT 1 COMPLETE** - Thread-safety validation (12/12 tests passing)
  - ✅ Added atomic `count_open_positions()` API to PositionTracker (fixes TOCTOU races)
  - ✅ Fixed 4 RiskManager methods to use atomic counting vs non-atomic `len(get_all_open_positions())`
  - ✅ Fixed sqlite3.Row `.get()` bug in position.py:404 (no `.get()` method exists)
  - ✅ Aligned 5 test APIs with production code (create actual positions vs calling non-existent `record_loss()`)
  - ✅ All HIGH-severity blockers resolved, ready for Phase 13 testnet rodage
  - 📊 Test suite: 228 tests total (216 unit + 12 concurrency)
- 2025-10-04: **SPRINT 0 COMPLETE** - Dependency rationalization + documentation cleanup
  - ✅ Split requirements.txt into core/research/dev (114 → 30/45/15 packages)
  - ✅ Updated Makefile with install-core, install-research, install-dev targets
  - ✅ Updated CI workflow to use requirements-dev.txt (10min → 2-3min build time)
  - ✅ Removed 2 false positives from Known Critical Issues (async kill-switch, circuit breaker API)
  - ✅ CI Docker images will reduce from 2.5GB → ~400MB
- 2025-10-04: **CONDENSATION** - Reduced from 1439 to 346 lines (~76% reduction)
  - ✅ Condensed verbose sections (AI/ML roadmap, Audit & Compliance, Known Issues)
  - ✅ Removed redundant code examples, kept essential API references
  - ✅ Consolidated testing, troubleshooting, and workflow sections
  - ✅ All critical operational info preserved, detailed info moved to external docs

**Full Changelog**: See git history for detailed changes
