# THUNES: Short-Range Improvements Roadmap

**Generated**: 2025-10-06
**Status**: Phase 13 Sprint 1 Complete → Planning Phase 14 Improvements
**Total Items**: 47 enhancements across 10 tiers

## Overview

This document catalogs 47 identified improvements for THUNES, prioritized by impact and effort. Focus on **Tier 1-2** for maximum short-range benefit before Phase 14 deployment.

**Key Metrics**:
- 36 source files, 19 test files
- 228 tests (21% coverage by line count)
- 2 TODOs, minimal technical debt
- Good logging coverage (296 statements)

---

## TIER 1 - Critical (Phase 14 Blockers) 🚨

### 1. Add Health Check Endpoint (1 day)
**Problem**: No `/health` endpoint for production monitoring
**Impact**: Kubernetes/Docker liveness probes fail, can't detect zombie processes
**Files**: Create `src/api/health.py`, add `fastapi==0.115.0` to requirements
**Effort**: 4-6 hours

### 2. Add Graceful Shutdown Handler (1 day)
**Problem**: SIGTERM kills process mid-trade, positions left open
**Impact**: Risk of unclosed positions during deployment/restart
**Files**: `src/live/paper_trader.py`, `src/orchestration/run_scheduler.py`
**Effort**: 6-8 hours

### 3. Add Retry Logic for API Calls (1-2 days)
**Problem**: No retries on transient Binance API failures
**Impact**: Trades fail unnecessarily, manual intervention required
**Files**: `src/data/binance_client.py`, `src/live/paper_trader.py`, add `tenacity==9.0.0`
**Effort**: 1-2 days

### 4. Add Input Validation to CLI Scripts (1 day)
**Problem**: No validation for symbol format, timeframe values, numeric ranges
**Impact**: Cryptic errors when user enters invalid input
**Files**: All 5 CLI entry point scripts
**Effort**: 6-8 hours

---

## TIER 2 - High-Value Quick Wins (1-3 days each) ⚡

### 5. Add Prometheus Metrics Endpoint (2 days)
**Current**: No metrics export, rely on log parsing
**Benefit**: Grafana dashboards, alerting, proper observability
**Files**: `src/risk/manager.py`, `src/live/paper_trader.py`, add `prometheus_client`
**Effort**: 1.5-2 days

### 6. Add Log Rotation (4 hours)
**Problem**: `audit_trail.jsonl` (749KB) and `paper_trader.log` (172KB) grow unbounded
**Impact**: Disk space exhaustion in production
**Files**: `src/utils/logger.py`
**Effort**: 2-4 hours

### 7. Cache Exchange Info Globally (4 hours)
**Problem**: Each `ExchangeFilters` instance fetches full exchange info
**Impact**: Wasted API calls, slower startup
**Files**: Create `src/data/exchange_cache.py`, modify `src/filters/exchange_filters.py`
**Effort**: 3-4 hours

### 8. Add CLI Progress Bars (1 day)
**Problem**: Long-running backtests/optimizations show no progress
**Impact**: User doesn't know if process is stuck
**Files**: `src/backtest/run_backtest.py`, `src/optimize/run_optuna.py`, add `tqdm==4.67.1`
**Effort**: 6-8 hours

### 9. Add Environment Variable Validation (4 hours)
**Problem**: Missing `.env` variables cause cryptic errors
**Impact**: Confusing onboarding, wasted debugging time
**Files**: `src/config.py`, all 5 CLI entry points
**Effort**: 3-4 hours

### 10. Replace Print with Logger (2 hours)
**Problem**: 20 `print()` statements go to stdout (can't filter/rotate)
**Impact**: Logs mixed with output, can't control verbosity
**Files**: 3 CLI scripts (backtest, auto_reopt, run_optuna)
**Effort**: 1-2 hours

---

## TIER 3 - Testing Gaps (2-5 days) 🧪

### 11. Add Integration Tests for Paper Trader (2 days)
**Gap**: Only 1 integration test exists
**Needed**: End-to-end workflow tests (backtest → optimize → paper → monitor)
**Files**: Create `tests/test_e2e_workflow.py`
**Effort**: 2 days

### 12. Add Exchange Filter Edge Cases (1 day)
**Gap**: No tests for invalid symbols, API errors, cache invalidation
**Files**: Extend `tests/test_filters.py`
**Effort**: 1 day

### 13. Add Performance Tracker Tests (1 day)
**Gap**: `src/monitoring/performance_tracker.py` has ZERO tests
**Files**: Create `tests/test_performance_tracker.py`
**Effort**: 1 day

### 14. Add Telegram Alert Tests (4 hours)
**Gap**: Mock tests exist, but no integration tests
**Files**: Extend `tests/test_telegram.py`
**Effort**: 4 hours

### 15. Add CLI Argument Validation Tests (1 day)
**Gap**: No tests for invalid args (should raise ValueError)
**Files**: Create `tests/test_cli_validation.py`
**Effort**: 1 day

---

## TIER 4 - Code Quality (1-3 days) 🎯

### 16. Extract Hardcoded Constants (1 day)
**Problem**: Magic numbers scattered (60s cache, 5 retries)
**Solution**: Move to `src/config.py` or class constants
**Files**: All modules
**Effort**: 1 day

### 17. Add Type Hints to All Functions (2 days)
**Gap**: ~15% of functions missing return type hints
**Files**: Run `mypy --strict` to find gaps
**Effort**: 2 days

### 18. Split Large Files (2 days)
**Problem**: 3 files >500 lines (ws_stream, risk_manager, paper_trader)
**Solution**: Extract sub-modules
**Files**: `src/data/ws_stream.py` (501 lines), `src/risk/manager.py` (497 lines)
**Effort**: 2 days

### 19. Add Docstring Examples (1 day)
**Gap**: Docstrings lack examples for complex functions
**Files**: All public APIs
**Effort**: 1 day

### 20. Remove Dead Code (4 hours)
**Finding**: 1 empty `pass` in `circuit_breaker.py:170`
**Files**: `src/utils/circuit_breaker.py`
**Effort**: 4 hours

---

## TIER 5 - Performance Optimizations (1-3 days) ⚡

### 21. Use Async for API Calls (3 days)
**Benefit**: 3-5x faster multi-symbol operations
**Caution**: Major refactor, save for Phase 15+
**Files**: `src/data/binance_client.py`
**Effort**: 3 days

### 22. Optimize Daily PnL Calculation (1 day)
**Problem**: Queries ALL positions daily (slow with 1000+ trades)
**Solution**: Add index on `entry_time`, filter `WHERE entry_time >= today`
**Files**: `src/models/position.py`, `src/risk/manager.py`
**Effort**: 1 day

### 23. Batch WebSocket Subscriptions (1 day)
**Problem**: Separate WS connection per symbol
**Solution**: Single connection with multiple symbols
**Files**: `src/data/ws_stream.py`
**Effort**: 1 day

### 24. Reduce Log Volume (4 hours)
**Problem**: 296 log statements, many at DEBUG/INFO level
**Solution**: Demote non-critical to DEBUG, add `LOG_LEVEL` env var
**Files**: All modules
**Effort**: 4 hours

---

## TIER 6 - Documentation (1-2 days) 📚

### 25. Add API Reference Docs (2 days)
**Tool**: Sphinx autodoc or mkdocs
**Output**: HTML docs from docstrings
**Files**: Create `docs/api/` directory
**Effort**: 2 days

### 26. Add Architecture Diagrams (1 day)
**Tool**: Mermaid.js or draw.io
**Output**: Component diagram, sequence diagram for trade flow
**Files**: `docs/ARCHITECTURE.md`
**Effort**: 1 day

### 27. Add Troubleshooting Guide (1 day)
**Content**: Common errors + solutions (e.g., -1013, kill-switch)
**Files**: `docs/TROUBLESHOOTING.md`
**Effort**: 1 day

### 28. Add Performance Tuning Guide (4 hours)
**Content**: GPU vs CPU, caching, rate limits
**Files**: `docs/PERFORMANCE.md`
**Effort**: 4 hours

---

## TIER 7 - Feature Additions (2-10 days) 🚀

### 29. Add Multi-Timeframe Support (3 days)
**Benefit**: Trend on 1h, entry on 5m (common pattern)
**Files**: `src/backtest/strategy.py`, `src/live/paper_trader.py`
**Effort**: 2-3 days

### 30. Add Stop-Loss Orders (2 days) ⚠️ CRITICAL FOR PHASE 14
**Benefit**: Automated risk control (don't rely on kill-switch alone)
**Files**: `src/risk/manager.py`, `src/live/paper_trader.py`
**Effort**: 2 days

### 31. Add Trailing Stop (1 day)
**Benefit**: Lock in profits automatically
**Files**: `src/risk/manager.py`
**Effort**: 1 day

### 32. Add Limit Orders (2 days)
**Benefit**: Reduce slippage vs market orders
**Files**: `src/live/paper_trader.py`
**Effort**: 2 days

### 33. Add Multi-Symbol Support (5 days)
**Benefit**: Portfolio diversification
**Challenge**: Need position limits per symbol + global
**Files**: `src/backtest/run_backtest.py`, `src/risk/manager.py`
**Effort**: 5 days

### 34. Add Walk-Forward Analysis (3 days)
**Benefit**: Prevent overfitting (critical for ML phases)
**Implementation**: 6-fold cross-validation
**Files**: `src/backtest/run_backtest.py`
**Effort**: 3 days

### 35. Add CCXT Integration (1 week) - RECOMMENDED
**Benefit**: 50+ exchanges instead of Binance-only
**Files**: `src/data/binance_client.py` → `src/data/exchange_client.py`
**Effort**: 1 week

---

## TIER 8 - DevOps & Deployment (3-10 days) 🐳

### 36. Add Docker Compose (1 day)
**Benefit**: One-command setup (db + app + metrics)
**Files**: Create `docker-compose.yml`
**Effort**: 1 day

### 37. Add Kubernetes Manifests (3 days)
**Benefit**: Production deployment on K8s
**Files**: Create `k8s/deployment.yaml`, `k8s/service.yaml`
**Effort**: 3 days

### 38. Add Helm Chart (2 days)
**Benefit**: Parameterized K8s deployments
**Files**: Create `helm/thunes/`
**Effort**: 2 days

### 39. Add GitHub Release Automation (1 day)
**Benefit**: Semantic versioning + changelogs
**Files**: `.github/workflows/release.yml`
**Effort**: 1 day

### 40. Add Performance Benchmarks (2 days)
**Benefit**: Track performance regressions
**Files**: `tests/benchmarks/benchmark_suite.py`
**Effort**: 2 days

---

## TIER 9 - Security & Compliance (1-3 days) 🔒

### 41. Add Secrets Scanning Pre-commit (2 hours)
**Tool**: detect-secrets
**Files**: `.pre-commit-config.yaml`
**Effort**: 2 hours

### 42. Add SBOM Generation (4 hours)
**Tool**: syft or cyclonedx
**Files**: `.github/workflows/sbom.yml`
**Effort**: 4 hours

### 43. Add License Compliance Check (4 hours)
**Tool**: pip-licenses
**Files**: `.github/workflows/license-check.yml`
**Effort**: 4 hours

### 44. Add Dependency Update Automation (1 day)
**Tool**: Dependabot or Renovate
**Files**: `.github/dependabot.yml`
**Effort**: 1 day

---

## TIER 10 - UX & Convenience (1-5 days) 🎨

### 45. Add Rich Console Output (1 day)
**Tool**: rich library
**Benefit**: Pretty tables, syntax highlighting
**Files**: All CLI scripts
**Effort**: 1 day

### 46. Add Config Wizard (2 days)
**Benefit**: Interactive `.env` setup
**Implementation**: `python -m src.setup`
**Files**: Create `src/setup.py`
**Effort**: 2 days

### 47. Add Status Dashboard (5 days)
**Tool**: Streamlit or Gradio
**Benefit**: Real-time monitoring without Grafana
**Files**: Create `src/dashboard/app.py`
**Effort**: 5 days

---

## Priority Matrix

### High Impact, Low Effort (Do First)
- #3: Retry logic (1-2 days)
- #6: Log rotation (4 hours)
- #7: Cache exchange info (4 hours)
- #9: Env validation (4 hours)
- #10: Replace print with logger (2 hours)
- #30: Stop-loss orders (2 days) ⚠️ CRITICAL

### High Impact, Medium Effort (Do Next)
- #1: Health check (1 day)
- #2: Graceful shutdown (1 day)
- #4: Input validation (1 day)
- #5: Prometheus metrics (2 days)
- #35: CCXT integration (1 week)

### High Impact, High Effort (Phase 15+)
- #21: Async API calls (3 days)
- #33: Multi-symbol (5 days)
- #34: Walk-forward (3 days)
- #47: Status dashboard (5 days)

---

## Recommended Implementation Sequence

### Week 1 (Phase 14 Blockers)
1. #30: Stop-loss orders (2 days) ⚠️
2. #1: Health check (1 day)
3. #2: Graceful shutdown (1 day)
4. #4: Input validation (1 day)

### Week 2 (Production Hardening)
5. #3: Retry logic (1-2 days)
6. #5: Prometheus metrics (2 days)
7. #6: Log rotation (4 hours)
8. #9: Env validation (4 hours)

### Week 3 (Quality & Testing)
9. #10: Replace print statements (2 hours)
10. #7: Cache exchange info (4 hours)
11. #11-15: Testing gaps (2-5 days)

### Week 4+ (Scaling)
12. #35: CCXT integration (1 week)
13. #29: Multi-timeframe (3 days)
14. #34: Walk-forward (3 days)

---

## Effort Summary

**By Tier**:
- Tier 1 (Critical): 4-5 days
- Tier 2 (Quick Wins): 7-9 days
- Tier 3 (Testing): 5-8 days
- Tier 4 (Quality): 5-7 days
- Tier 5 (Performance): 5-7 days
- Tier 6 (Docs): 4-5 days
- Tier 7 (Features): 17-24 days
- Tier 8 (DevOps): 8-12 days
- Tier 9 (Security): 2-4 days
- Tier 10 (UX): 8-13 days

**Total**: 60-90 days (3 months for all 47 items)

**Critical Path** (Tier 1-2): 15-20 days for 80% of production-readiness benefits

---

## Status Tracking

**Completed**: 0/47
**In Progress**: 0/47
**Planned**: 47/47

**Next Milestone**: Phase 14 deployment (requires Tier 1 + #30)

---

**Last Updated**: 2025-10-06
**Maintained By**: THUNES Development Team
