# THUNES Complete Roadmap: Phase 13 → Phase 22

**Version**: 1.0
**Last Updated**: 2025-10-05
**Total Duration**: 12 months (52 weeks, 1,840 hours)
**Current Phase**: Phase 13 Sprint 1.3 ✅ (75% complete)

---

## Executive Summary

This roadmap provides a comprehensive deployment plan from **current state** (Phase 13 Sprint 1.3 complete) to **full production scaling** (Phase 22). The plan is structured in 5 major phases with detailed implementation plans:

1. **Phase 13**: Paper Trading 24/7 Deployment (3.5 weeks, 72h) - **CURRENT FOCUS**
2. **Phase 14**: Micro-Live Production (4 weeks, 160h)
3. **Phase 15-16**: RL Integration (12 weeks, 480h)
4. **Phase 17-18**: Advanced ML & HFT (8-10 weeks, 320-400h)
5. **Phase 19-22**: Production Scaling (12 weeks, 480h)

**Total**: 39-41 weeks, 1,512-1,592 hours development time

---

## Roadmap Documents

### Phase 13: Paper Trading 24/7 Deployment

**Document**: [`PHASE_13_SPRINTS.md`](./PHASE_13_SPRINTS.md)
**Duration**: 3.5 weeks (72 hours)
**Status**: 75% Complete (Sprints 0-1.3 ✅, Sprints 1.4-3 pending)

**Remaining Sprints**:
- **Sprint 1.4**: Concurrency Test Suite (16h, Days 1-2) 🔴 **CRITICAL PATH**
  - 30+ thread-safety tests (WebSocket, circuit breaker, risk manager)
  - Test concurrent `validate_trade()`, reconnection races, state transitions
  - **Blockers**: Phase 13 rodage cannot start until thread-safety validated

- **Sprint 2**: Governance & Observability (26h, Days 3-6)
  - **Sprint 2.1**: Parameter Versioning (5h) - Track strategy params, detect Sharpe decay
  - **Sprint 2.2**: Audit Trail Pydantic Schema (5h) - Centralize audit logging
  - **Sprint 2.3**: Prometheus Metrics (16h) - Grafana dashboards, alerting rules

- **Sprint 3**: 7-Day Rodage (Days 7-14) 🔴 **DECISION GATE**
  - Daily monitoring (15 min/day)
  - Success criteria: Uptime >99%, zero -1013 errors, kill-switch tested, WebSocket resilience, Sharpe >0.8, zero position desyncs
  - **GO/NO-GO Decision**: Proceed to Phase 14 or restart Sprint 3

**Key Deliverables**:
- 30+ concurrency tests (all passing)
- Prometheus metrics exposed (`/metrics` endpoint)
- Grafana dashboards (Trading Overview, System Health, Risk Metrics)
- 7-day rodage report (PnL, uptime, error count, Sharpe)

**Next Steps**: Start Sprint 1.4 immediately (concurrency tests are critical path)

---

### Phase 14: Micro-Live Production

**Document**: [`PHASE_14_PRODUCTION.md`](./PHASE_14_PRODUCTION.md)
**Duration**: 4 weeks (160 hours)
**Status**: ⏳ Pending (blocked by Phase 13 GO decision)
**Capital at Risk**: €10-50 (start €10, increase to €20 after Week 2)

**Week-by-Week Plan**:

**Week 1: Production Infrastructure Setup (40h)**
- Day 1-2: Binance live API keys (withdrawal-disabled) + secrets manager (AWS Secrets Manager or HashiCorp Vault)
- Day 3: Systemd service (`thunes-scheduler.service`) + log rotation (`/etc/logrotate.d/thunes`)
- Day 4-5: Position reconciliation (hourly, Telegram alerts on mismatch)
- Day 5: Chaos testing (scheduler crash, network partition, kill-switch trigger, 24h memory stress)

**Week 2: Initial Live Trading (€10 capital)**
- Daily monitoring (30 min/day): Telegram alerts, Grafana dashboards, reconciliation logs, audit trail
- Weekly analysis (2h, Sunday): 7-day Sharpe, total return, max drawdown, slippage delta vs paper trading
- **Decision Gate**: If all criteria met (zero desyncs, Sharpe >0.8, slippage <0.5%, <3 circuit breaker trips, zero crashes) → increase capital to €20

**Week 3-4: Scaled Live Trading (€20 capital)**
- Capital increase procedure (deposit €10, update `DEFAULT_QUOTE_AMOUNT=20.0`, restart scheduler)
- Weekly profit withdrawal (if Week 2 profitable >€5, withdraw to external wallet)
- 30-day metrics collection (uptime, Sharpe, desyncs, crashes, kill-switch activations, profit withdrawal)

**Week 4 GO/NO-GO Decision**:
- **Criteria**: Uptime >99.9%, Sharpe >1.0, zero desyncs, zero crashes, zero kill-switch activations, ≥1 successful profit withdrawal
- **Decision**: GO → Phase 15 (RL Integration) | NO-GO → Extend Phase 14 monitoring for 2 more weeks

**Key Deliverables**:
- Production infrastructure (systemd, log rotation, secrets manager)
- Position reconciliation (hourly, Telegram alerts)
- Chaos testing results (all scenarios passed)
- 30-day production report (metrics, incidents, decisions)

---

### Phase 15-16: RL Integration

**Documents**:
- [`PHASE_15_RL_SPEC.md`](./PHASE_15_RL_SPEC.md) (Phase 15: RL Adapter + Shadow Mode, 6 weeks, 240h)

**Duration**: 12 weeks total (480 hours)
**Status**: ⏳ Pending (blocked by Phase 14 GO decision)

**Phase 15: RL Adapter + Shadow Mode (6 weeks, 240h)**

**Week 1-2: Core Infrastructure (80h)**
- RL Adapter (`src/rl/adapter.py`, 40h) - 9 validation gates:
  1. Policy whitelist
  2. TTL check (stale actions)
  3. Confidence threshold
  4. Kill-switch (blocks BUY, allows SELL)
  5. Circuit breaker
  6. Price bands (limit orders)
  7. Exchange filters (tick/step/notional)
  8. Risk validation (position limits, cool-down, daily loss)
  9. Idempotent order submission

- Pydantic Schemas (`src/rl/schemas.py`, 16h) - `RLAction`, `Decision`, `ExecFill`
- Execution Layer (`src/exec/ccxt_client.py`, 24h) - CCXT wrapper, Binance keep-priority amend

**Week 3-4: Data Pipeline (80h)**
- Parquet Store (`src/data/store.py`, 32h) - OHLCV/trades/features storage (Zstd compression)
- Feature Engineering (`src/data/pipeline.py`, 24h) - Polars lazy evaluation, DuckDB aggregations
- Reference Price Cache (`src/data/reference_price.py`, 8h) - WebSocket ticker stream
- Event Bus (`src/streaming/nats_bus.py`, 16h) - NATS JetStream (persistent subjects)

**Week 5: Simulated Exchange (40h)**
- Backtest Engine (`src/backtest/sim_exchange.py`, 24h) - Event-driven fills, latency/slippage/fee simulation
- RL Environment Bridge (`src/backtest/rl_sim.py`, 16h) - Gym-compatible `env.step(action)` interface

**Week 6: Shadow Mode CLI (40h)**
- CLI Tool (`src/rl/shadow_cli.py`, 24h) - Consume RL actions from stdin, output decisions
- Validation Dashboard (`notebooks/rl_shadow_validation.ipynb`, 16h) - Latency, rejection rate, slippage delta

**Success Criteria**:
- ✅ Shadow mode runs 7 days (no ACCEPTED orders placed, only logged)
- ✅ Zero rejection reason=FILTERS (filter validation 100% correct)
- ✅ Decision latency p95 <15ms
- ✅ FinRL policy outputs >1000 actions/day, acceptance rate >60%

**Phase 16: Production RL + freqtrade (6 weeks, 240h)**

**Week 1-2: Model Training (80h)**
- FinRL Integration (`src/ml/finrl_trainer.py`, 40h) - PPO agent, Binance 2023-2025 OHLCV
- Walk-Forward Validation (`src/backtest/walk_forward.py`, 24h) - Train: 180d, Test: 30d
- Model Registry (`src/ml/registry.py`, 16h) - Git LFS storage, metadata tracking

**Week 3-4: freqtrade Integration (80h)**
- Custom Strategy (`user_data/strategies/RLStrategy.py`, 32h) - Load RL model from registry
- Adapter Bridge (`src/rl/freqtrade_adapter.py`, 24h) - Convert freqtrade signals → `RLAction`
- Paper Trading (freqtrade dry-run, 24h) - Test integration

**Week 5-6: Production Deployment (80h)**
- Canary Release (Week 5, 40h) - 1 pair (BTCUSDT) only, qty_mode=RISK capped at 1% equity
- Multi-Pair Rollout (Week 6, 40h) - Add ETHUSDT, BNBUSDT, position limits: max 2 positions/pair

**Success Criteria**:
- ✅ RL agent Sharpe >1.2 (7-day live)
- ✅ Sharpe delta vs baseline SMA ≥+0.3
- ✅ Zero model inference errors (ONNX Runtime stable)
- ✅ Latency p95 <10ms (CPU inference)

---

### Phase 17-18: Advanced ML & HFT

**Document**: [`PHASE_17_18_ML.md`](./PHASE_17_18_ML.md)
**Duration**: 8-10 weeks (320-400 hours)
**Status**: ⏳ Pending (blocked by Phase 16 completion)

**Phase 17: Model Registry + SHAP (4 weeks, 160h)**

**Week 1: Model Registry (40h)**
- Git LFS backend (`src/ml/registry.py`) - Save, load, list, rollback model versions
- Metadata schema (hyperparameters, training data hash, performance metrics)

**Week 2: SHAP Explainability (40h)**
- SHAP value calculation (`src/ml/explainability.py`) - Explain every decision
- Log top 10 features to audit trail
- Grafana dashboard for feature importance distribution

**Week 3: Automated Retraining (40h)**
- Weekly retraining trigger (`src/ml/retraining.py`) - If Sharpe <1.0
- Walk-forward validation (train: 180d, test: 30d)
- Automatic deployment if test Sharpe >1.5

**Week 4: Drift Detection (40h)**
- River online learning (`src/ml/drift_detection.py`) - Concept drift detection
- Alert if feature distribution shifts >20%
- Automatic retraining trigger on severe drift

**Success Criteria**:
- ✅ Model save/load roundtrip preserves weights
- ✅ SHAP values calculated in <50ms (p95)
- ✅ Retraining triggers automatically (weekly check)
- ✅ Drift detection runs on every decision (<10ms overhead)

**Phase 18: HFT Exploration (4-6 weeks, 160-240h)**

**Week 1-2: nautilus_trader Setup (80h)**
- nautilus_trader installation + configuration
- Binance adapter (WebSocket + REST)
- Tick data ingestion (1-minute granularity)

**Week 3-4: Order Flow Features (80h)**
- Bid/ask queue depth (Level 2 order book)
- Trade flow imbalance (buy volume / sell volume)
- Microstructure features (spread, tick size, volatility)

**Week 5-6: Performance Validation (80-120h)**
- Reproduce 16-17% benchmark (TradeMaster study)
- Latency profiling (<1ms decision latency)
- HFT strategy validation (tick-level backtests)

**Success Criteria**:
- ✅ Annualized return >16% (out-of-sample)
- ✅ Decision latency <1ms (p95)
- ✅ Sharpe >2.0 (HFT strategy)

---

### Phase 19-22: Production Scaling

**Document**: [`PHASE_19_22_SCALING.md`](./PHASE_19_22_SCALING.md)
**Duration**: 12 weeks (480 hours)
**Status**: ⏳ Pending (blocked by Phase 18 completion)

**Phase 19: Multi-Venue (3 weeks, 120h)**
- Week 1: CCXT Pro WebSocket (Binance, Kraken, Coinbase)
- Week 2: Cross-exchange arbitrage detection (>0.5% spread)
- Week 3: Unified portfolio service (cross-venue aggregation)

**Phase 20: Capacity Scaling (3 weeks, 120h)**
- Week 1: PostgreSQL migration (replace SQLite, connection pooling, replication)
- Week 2: Redis caching (reference prices, order book snapshots)
- Week 3: Docker Swarm orchestration (3 scheduler instances, load balancer)

**Phase 21: Advanced Risk (3 weeks, 120h)**
- Week 1: VaR calculation (Monte Carlo + historical, 99% confidence)
- Week 2: Correlation matrix (pairwise correlation, hedging recommendations)
- Week 3: Margin utilization (calculate utilization, auto-deleveraging if >80%)

**Phase 22: Full Automation (3 weeks, 120h)**
- Week 1: Auto-rebalancing (daily, >5% drift trigger)
- Week 2: Kelly criterion sizing (dynamic position sizing)
- Week 3: Multi-strategy ensemble (SMA + RL + HFT, weighted voting)

**Success Criteria (Phase 22)**:
- ✅ Portfolio rebalances daily (if drift >5%)
- ✅ Kelly criterion improves Sharpe vs fixed sizing (+0.2)
- ✅ Ensemble outperforms individual strategies (Sharpe +0.3)
- ✅ Zero-touch operation for 30 days (no manual intervention)

---

## Critical Path Analysis

```
Phase 13 Sprint 1.4 (Day 1-2) 🔴 CRITICAL
   ↓ [Concurrency tests block rodage]
Phase 13 Sprint 2 (Day 3-6)
   ↓ [Governance + Observability]
Phase 13 Sprint 3 Rodage (Day 7-14) 🚪 GO/NO-GO GATE #1
   ↓ [7-day burn-in test]
Phase 14 Week 1 (Infrastructure) 🔴 CRITICAL
   ↓ [Production setup blocks live trading]
Phase 14 Week 2-4 (Live Trading) 🚪 GO/NO-GO GATE #2
   ↓ [30-day production validation]
Phase 15 (RL Foundation, 6 weeks) 🔴 CRITICAL
   ↓ [Shadow mode blocks production RL]
Phase 16 (Production RL, 6 weeks)
   ↓ [freqtrade integration]
Phase 17-18 (Advanced ML, 8-10 weeks)
   ↓ [Model registry + HFT validation]
Phase 19-22 (Scaling, 12 weeks)
```

**Total Duration**: 39-41 weeks (9-10 months)
**Critical Path Hours**: 1,512-1,592 hours development time

**Key Dependencies**:
- Sprint 1.4 blocks Sprint 3 (rodage)
- Sprint 3 GO decision blocks Phase 14 (production)
- Phase 14 GO decision blocks Phase 15 (RL integration)
- Phase 16 completion blocks Phase 17 (advanced ML)
- Phase 18 completion blocks Phase 19 (scaling)

---

## Decision Gates (GO/NO-GO)

### Gate #1: Phase 13 → Phase 14

**Timing**: Day 14 (end of Sprint 3 rodage)
**Criteria**:
- ✅ Uptime >99% (max 14.4 min downtime over 7 days)
- ✅ Zero order rejections (-1013 errors)
- ✅ Kill-switch tested manually (activation + deactivation)
- ✅ WebSocket reconnects successfully after manual kill
- ✅ Sharpe ratio >0.8 (paper trading performance acceptable)
- ✅ No position desyncs (manual reconciliation check on Day 7)

**Decision**: GO → Phase 14 | NO-GO → Restart Sprint 3

---

### Gate #2: Phase 14 → Phase 15

**Timing**: Week 4 (end of Phase 14)
**Criteria**:
- ✅ 30 days uptime >99.9%
- ✅ Sharpe >1.0 (live trading)
- ✅ Zero position desyncs
- ✅ Profit withdrawal successful (€5+ to external wallet)

**Decision**: GO → Phase 15 | NO-GO → Extend Phase 14 for 2 weeks

---

## Risk Mitigation

### High-Risk Items

**1. Sprint 1.4 Concurrency Tests** (16h)
- **Risk**: Race conditions discovered, require significant refactoring (>40h)
- **Mitigation**: Start immediately, allocate buffer time (24h instead of 16h)
- **Contingency**: If >3 race conditions found → pause, architect fix, re-plan

**2. Phase 13 Rodage** (7 days)
- **Risk**: Scheduler crash, position desync, kill-switch failure
- **Mitigation**: Daily monitoring (15 min/day), automated alerts (Telegram + Grafana)
- **Contingency**: If NO-GO → fix issues, restart rodage from Day 1

**3. Phase 14 Live Capital** (€10-50)
- **Risk**: Unexpected loss (>€10), API key compromise, position desync
- **Mitigation**: Withdrawal-disabled API keys, hourly reconciliation, chaos testing
- **Contingency**: If loss >€10 in Week 2 → halt, investigate, extend monitoring

**4. Phase 15 Shadow Mode** (7 days)
- **Risk**: Filter validation failures (>1% rejection rate FILTERS)
- **Mitigation**: Extensive testing in Week 1-2, validation dashboard monitoring
- **Contingency**: If rejection rate >1% → fix filters, restart shadow mode

---

## Resource Requirements

### Development Time

| Phase | Estimated Hours | Actual (if complete) | Variance |
|-------|-----------------|----------------------|----------|
| Phase 13 (Sprints 1.4-3) | 72h | 9.5h (partial) | -62.5h remaining |
| Phase 14 | 160h | - | - |
| Phase 15-16 | 480h | - | - |
| Phase 17-18 | 320-400h | - | - |
| Phase 19-22 | 480h | - | - |
| **Total** | **1,512-1,592h** | **9.5h** | **1,502.5-1,582.5h remaining** |

**At 8h/day**: 189-198 working days (9-10 months)
**At 40h/week**: 38-40 weeks

---

### Infrastructure Costs (Estimated)

| Component | Monthly Cost | Phase Introduced |
|-----------|--------------|------------------|
| Binance Trading Fees (0.1% × 2) | €10-50 (depends on volume) | Phase 14 |
| AWS Secrets Manager | €0.50 (10 secrets) | Phase 14 |
| Docker Swarm (3 nodes) | €30-60 (if cloud) | Phase 20 |
| PostgreSQL (managed) | €20-40 | Phase 20 |
| Redis (managed) | €10-20 | Phase 20 |
| CCXT Pro License | €99/month | Phase 19 |
| **Total** | **€169.50-€269.50/month** (from Phase 20+) | - |

**Capital at Risk**:
- Phase 14: €10-50
- Phase 15+: Scales with performance (Kelly criterion sizing)

---

## Next Steps

### Immediate (This Session)

1. **Start Sprint 1.4** (concurrency tests) - 16h estimated
   - Create `tests/test_ws_stream_concurrency.py` (10+ tests)
   - Create `tests/test_circuit_breaker_chaos.py` (10+ tests)
   - Create `tests/test_risk_manager_concurrent.py` (10+ tests)
   - Run all tests 10x in loop (verify no flakiness)

2. **Review Roadmap Documents** (15 min)
   - Read `PHASE_13_SPRINTS.md` (Sprint 1.4-3 details)
   - Confirm understanding of success criteria
   - Note any blockers or questions

### Near-Term (This Week)

3. **Complete Sprint 2** (governance + observability) - 26h estimated
   - Sprint 2.1: Parameter versioning (5h)
   - Sprint 2.2: Audit trail Pydantic schema (5h)
   - Sprint 2.3: Prometheus metrics + Grafana (16h)

4. **Prepare Sprint 3 Rodage** (pre-deployment checklist)
   - Run all pre-deployment checks (from CLAUDE.md)
   - Verify CI green for 3+ consecutive days
   - Schedule 7-day monitoring (Day 7-14)

### Medium-Term (Next 2 Weeks)

5. **Execute Sprint 3 Rodage** (7 days monitoring + 1 day GO/NO-GO decision)
   - Daily monitoring (15 min/day)
   - Weekly analysis (2h on Day 7)
   - GO/NO-GO meeting (Day 14, 17:00 UTC)

6. **If GO**: Prepare Phase 14 Infrastructure
   - Generate Binance live API keys
   - Configure secrets manager (AWS or Vault)
   - Deploy systemd service + log rotation

---

## Documentation Index

All roadmap documents are located in `docs/roadmap/`:

1. **README.md** (this file) - Executive summary, critical path, decision gates
2. **PHASE_13_SPRINTS.md** - Detailed Sprint 1.4-3 plans
3. **PHASE_14_PRODUCTION.md** - Production infrastructure + micro-live trading
4. **PHASE_15_RL_SPEC.md** - RL adapter specification + shadow mode
5. **PHASE_17_18_ML.md** - Model registry, SHAP, nautilus_trader HFT
6. **PHASE_19_22_SCALING.md** - Multi-venue, scaling, automation

**Supporting Documents**:
- `docs/OPERATIONAL-RUNBOOK.md` - Disaster recovery, failure scenarios
- `docs/VENDOR-RISK-ASSESSMENT.md` - Binance security controls
- `docs/research/REGULATORY-ML-LANDSCAPE-2025.md` - Compliance benchmarks
- `docs/AUDIT-IMPLEMENTATION-2025-10-03.md` - Audit controls summary

---

**Document Version**: 1.0
**Last Updated**: 2025-10-05
**Author**: Claude Code (Automated Roadmap Synthesis)

**Change Log**:
- 2025-10-05: Initial comprehensive roadmap creation (Phase 13 → Phase 22)
