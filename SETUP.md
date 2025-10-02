# THUNES Setup Guide

## Quick Start Checklist

### Phase 0: Prerequisites ✅

- [ ] Create Binance Spot Testnet account at https://testnet.binance.vision/
- [ ] Generate API keys (trading only, no withdrawal permissions)
- [ ] (Optional) Create Telegram bot via @BotFather
- [ ] (Optional) Get Telegram chat ID

### Phase 1: Local Setup

```bash
# Navigate to project
cd THUNES

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
make install

# Configure environment
cp .env.template .env
# Edit .env with your credentials:
#   BINANCE_TESTNET_API_KEY=...
#   BINANCE_TESTNET_API_SECRET=...
```

**DoD**: Pre-commit hooks installed, no errors on `make pre-commit`

### Phase 2: Smoke Tests

```bash
# Run quality checks
make lint

# Run tests
make test
```

**DoD**: All tests pass, linting clean ✅

### Phase 3: Backtest MVP

```bash
# Run backtest (default: BTCUSDT 1h, 90 days)
make backtest

# Check output
cat artifacts/backtest/stats_BTCUSDT_1h.csv
```

**Expected Output**:
- Total Return %
- Sharpe Ratio
- Max Drawdown %
- Win Rate %
- Total Trades

**DoD**: Artifacts generated, stats displayed ✅

### Phase 4: Optimization

```bash
# Run Optuna (25 trials, ~5 minutes)
make optimize

# Check results
cat artifacts/optuna/study.csv
```

**Expected Output**:
- Best parameters (fast_window, slow_window)
- Best Sharpe Ratio
- Trial history

**DoD**: `study.csv` exists, best params identified ✅

### Phase 5: Paper Trading

```bash
# Check testnet balance first
make balance

# Run paper trade (single execution)
make paper
```

**Expected Outcomes**:
1. **Signal detected**: Market order placed (check Binance Testnet UI)
2. **No signal**: Message "No signal - no trade"
3. **Error**: Check logs with `cat logs/paper_trader.log`

**DoD**: Order executed if signal present, no -1013 errors ✅

### Phase 6: Order Filters (Critical)

Filters are already implemented in `src/filters/exchange_filters.py`.

**Validation**:
```bash
# Run filter tests
pytest tests/test_filters.py -v

# Run paper trading for 24h and monitor
# (No -1013 "Filter failure" errors should occur)
```

**DoD**: No filter rejections, all orders pass validation ✅

---

## Next Phases (7-14)

### Phase 7: WebSocket Streaming 🚧

**Goal**: Real-time bookTicker/aggTrade for faster signals

**Tasks**:
- Create `src/data/ws_stream.py`
- Implement reconnection logic (exponential backoff)
- Add ping/pong watchdog
- Test stability for 1+ hour

**Files to create**:
- `src/data/ws_stream.py`
- `tests/test_ws_stream.py`

### Phase 8: Risk Management 🚧

**Goal**: Hard limits to prevent runaway losses

**Tasks**:
- Implement kill-switch (max daily loss)
- Add cool-down mechanism
- Position size limits
- Create `src/risk/manager.py`

**Configuration** (in `.env`):
```bash
MAX_LOSS_PER_TRADE=5.0
MAX_DAILY_LOSS=20.0
MAX_POSITIONS=3
COOL_DOWN_MINUTES=60
```

### Phase 9: Telegram Alerts 🚧

**Goal**: Real-time notifications

**Tasks**:
- Create `src/alerts/telegram.py`
- Implement `info()`, `warn()`, `crit()` methods
- Send alerts for: trades, errors, daily PNL
- Test all notification types

### Phase 10: Orchestration 🚧

**Goal**: Automated scheduling

**Tasks**:
- Create `src/orchestration/scheduler.py`
- Set up APScheduler jobs:
  - Data collection (1m/5m)
  - Signal generation (5m/15m)
  - Paper execution (continuous)
  - Daily reports (EOD)
- Prevent job overlaps

### Phase 11: Observability 🚧

**Goal**: Metrics and structured logging

**Tasks**:
- Expose Prometheus metrics
- Create Grafana dashboard
- Implement JSON logging
- Add correlation IDs

### Phase 12: CI/CD ✅

**Already complete!**

**Setup GitHub Secrets**:
1. Go to repo Settings → Secrets → Actions
2. Add secrets:
   - `BINANCE_TESTNET_API_KEY`
   - `BINANCE_TESTNET_API_SECRET`
   - `TELEGRAM_BOT_TOKEN` (optional)
   - `TELEGRAM_CHAT_ID` (optional)
3. Add variable:
   - `TZ=Europe/Paris`

### Phase 13: Paper 24/7 ⏳

**Goal**: 7-day continuous run without critical issues

**Monitoring**:
```bash
# Run in background
nohup python -m src.live.paper_trader --symbol BTCUSDT --quote 10 --tf 1h &

# Monitor logs
tail -f logs/paper_trader.log

# Check daily
grep "ERROR\|CRITICAL" logs/paper_trader.log
```

**Metrics to track**:
- PnL (realistic with fees + slippage)
- Max drawdown per day
- Order rejection rate
- WebSocket stability
- Kill-switch triggers

**DoD**: 7 days without critical incidents ⏳

### Phase 14: Micro-Live ⏳

**⚠️ DANGER ZONE - REAL MONEY**

**Prerequisites**:
- ✅ Phase 13 completed successfully
- ✅ Kill-switch tested
- ✅ Telegram alerts working
- ✅ CI green for 2+ weeks

**Checklist before going live**:
- [ ] Set `ENVIRONMENT=live` in `.env`
- [ ] Add production API keys
- [ ] Verify permissions (trading only, no withdrawals)
- [ ] Set ultra-conservative limits:
  ```bash
  DEFAULT_QUOTE_AMOUNT=10.0  # Start with 10 EUR/USDT
  MAX_DAILY_LOSS=15.0
  MAX_POSITIONS=1  # Single position only
  ```
- [ ] Test kill-switch manually
- [ ] Confirm Telegram alerts arrive
- [ ] Manual approval required

**DoD**: 1-2 weeks live without exceeding limits ⏳

---

## Common Commands

```bash
# Development
make install        # Install deps + pre-commit
make test          # Run tests
make lint          # Check code quality
make format        # Format code

# Trading
make backtest      # Run backtest
make optimize      # Optimize params
make paper         # Paper trade (single)
make balance       # Check testnet balance

# Docker
make docker-build  # Build image
make docker-run    # Start container
make docker-stop   # Stop container

# Logs
make logs          # Tail all logs
cat logs/paper_trader.log  # View specific log
```

## Troubleshooting

### "ModuleNotFoundError"
```bash
# Ensure venv is activated
source .venv/bin/activate

# Reinstall dependencies
make install
```

### "API key invalid" (testnet)
- Verify keys are from https://testnet.binance.vision (NOT production!)
- Check `.env` has correct `BINANCE_TESTNET_API_KEY`
- Regenerate keys if needed

### "Filter failure: -1013"
- Order filters should prevent this
- Check logs for details: `cat logs/paper_trader.log`
- Run filter tests: `pytest tests/test_filters.py -v`

### "Insufficient balance" (testnet)
- Request testnet funds: https://testnet.binance.vision/
- Reduce `DEFAULT_QUOTE_AMOUNT` in `.env`

### Tests fail on import
```bash
# Install in editable mode
pip install -e .
```

---

## Resources

- **Binance Testnet**: https://testnet.binance.vision/
- **Binance API Docs**: https://binance-docs.github.io/apidocs/spot/en/
- **Vectorbt Docs**: https://vectorbt.dev/
- **Optuna Docs**: https://optuna.org/
- **Tutorial Reference**: [Original French tutorial from agent]

---

## Safety Reminders

1. **Always start with testnet** - Never skip directly to production
2. **Test kill-switch** - Manually trigger max loss to verify it works
3. **Small amounts** - Start with 10-50 EUR when going live
4. **Monitor daily** - Check logs and PnL every 24h minimum
5. **One change at a time** - Don't modify multiple parameters simultaneously
6. **Paper trade changes first** - Every strategy tweak needs paper validation

---

**Good luck, and trade safe! 🚀**
