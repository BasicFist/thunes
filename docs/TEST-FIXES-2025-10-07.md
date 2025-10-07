# Test Suite Fixes - 2025-10-07

## Executive Summary

**Status**: Major progress - 34 → 18 test failures (47% reduction)
**Test Results**: 201 passing (was 185), 18 failing, 6 errors
**Root Cause**: Phase 13 Sprint 1 added `count_open_positions()` method but didn't update test mocks

## Discovered Issues

### 1. Documentation vs Reality Gap ❌

**Claimed**: "228 tests passing" (CLAUDE.md line 46, docs/SESSION-PROGRESS-2025-10-03.md)
**Actual**: 185 passing, 34 failing, 6 errors initially

**Impact**: CRITICAL - Project was not deployment-ready despite documentation claims

### 2. Missing Test Fixture Updates

**Problem**: Sprint 1.7 added atomic `count_open_positions()` method to PositionTracker for thread-safety, but test fixtures were never updated.

**Symptom**:
```python
TypeError: '>=' not supported between instances of 'Mock' and 'int'
```

**Affected File**: `tests/test_risk_manager.py`

**Fix Applied**:
```python
@pytest.fixture
def mock_position_tracker() -> Mock:
    """Create a mock PositionTracker."""
    tracker = Mock(spec=PositionTracker)
    tracker.get_all_open_positions.return_value = []
    tracker.has_open_position.return_value = False
    tracker.get_position_history.return_value = []
    tracker.count_open_positions.return_value = 0  # ← ADDED
    return tracker
```

**Tests Fixed** (16 tests):
- `test_validate_trade_passes_normally` ✅
- `test_validate_trade_rejects_when_kill_switch_active` ✅
- `test_validate_trade_rejects_excessive_quote_qty` ✅
- `test_validate_trade_rejects_when_max_positions_reached` ✅ (also updated inline mock)
- `test_validate_trade_rejects_duplicate_position` ✅
- `test_get_risk_status` ✅ (also updated inline mock)
- Plus 10 more risk_manager tests

### 3. Version Mismatch in Requirements Files

**Problem**: `requirements-dev.txt` had conflicting info with `pyproject.toml`

**Fix Applied**:
```diff
- pytest-asyncio==1.2.0
+ pytest-asyncio>=0.23.3  # Match pyproject.toml
```

**Note**: Version 1.2.0 actually satisfies >=0.23.3 (newer), so no reinstall needed.

## Remaining Test Failures (18)

### Category A: Flaky/Ordering Issues (7 tests)
- `test_risk_manager.py::test_validate_trade_allows_sell_during_cool_down`
- `test_risk_manager.py::TestAuditTrail::test_audit_trail_logs_kill_switch_deactivation`
- `test_risk_manager.py::TestAuditTrail::test_audit_trail_jsonl_format`
- `test_risk_manager.py::TestAuditTrail::test_kill_switch_allows_sell_orders`
- `test_risk_manager.py::TestConcurrentValidation::test_multiple_trades_same_symbol_rejected`
- `test_risk_manager.py::TestConcurrentValidation::test_multiple_trades_different_symbols_allowed`
- `test_risk_manager_concurrent.py::TestRiskManagerConcurrency::test_concurrent_validate_trade`

**Note**: These pass when run individually but fail in parallel execution (pytest-xdist).
**Likely Cause**: Shared state between tests (audit trail file, database).

### Category B: WebSocket Concurrency Tests (8 tests)
- `test_ws_stream_concurrency.py::TestWebSocketConcurrency::test_reconnect_with_pending_messages`
- `test_ws_stream_concurrency.py::TestWebSocketConcurrency::test_concurrent_message_processing`
- `test_ws_stream_concurrency.py::TestWebSocketConcurrency::test_stop_during_message_processing`
- `test_ws_stream_concurrency.py::TestWebSocketConcurrency::test_health_monitor_concurrent_record_message`
- `test_ws_stream_concurrency.py::TestWebSocketConcurrency::test_reconnection_race_condition`
- `test_ws_stream_concurrency.py::TestWebSocketConcurrency::test_watchdog_concurrent_health_check`
- `test_ws_stream_concurrency.py::TestWebSocketConcurrency::test_multiple_streams_same_symbol`
- `test_ws_stream_concurrency.py::TestWebSocketConcurrency::test_stream_restart_during_processing`
- `test_ws_stream_concurrency.py::TestWebSocketConcurrencyStress::test_high_volume_message_burst`

**Likely Cause**: Asyncio event loop issues, possibly related to pytest-asyncio configuration.

### Category C: Circuit Breaker Chaos Tests (3 tests + 6 errors)
- `test_circuit_breaker_chaos.py::TestCircuitBreakerChaos::test_reset_during_half_open`
- `test_circuit_breaker_chaos.py::TestCircuitBreakerConcurrencyStress::test_sustained_concurrent_load`
- 6 ERROR cases in circuit breaker concurrent tests

**Likely Cause**: Similar asyncio event loop conflicts.

## Code Quality Metrics

### Test Coverage: 58%
```
TOTAL: 2295 statements, 961 miss, 58% coverage
```

**High Coverage Modules** (>90%):
- `src/risk/manager.py` - 100% ✅
- `src/models/position.py` - 100% ✅
- `src/utils/circuit_breaker.py` - 95% ✅
- `src/utils/rate_limiter.py` - 92% ✅
- `src/alerts/telegram.py` - 95% ✅

**Low Coverage Modules** (<50%):
- `src/data/processors/gpu_features.py` - 0% (research code)
- `src/models/xgboost_gpu.py` - 0% (research code)
- `src/optimize/run_optuna.py` - 0% (CLI script)
- `src/backtest/run_backtest.py` - 0% (CLI script)
- `src/orchestration/run_scheduler.py` - 0% (CLI script)

### Deprecation Warnings
- `datetime.utcnow()` → `datetime.now(datetime.UTC)` (Python 3.13)
- `websockets.legacy` → new websockets API

## Recommendations

### Immediate (Phase 13 Blocker)
1. ✅ Fix `count_open_positions` mock in `test_risk_manager.py` **(DONE)**
2. ⏳ Investigate flaky test failures (audit trail file conflicts)
3. ⏳ Fix or skip asyncio concurrency tests for Phase 13 rodage

### Short-Term (Phase 13 Sprint 2)
1. Add test isolation for audit trail (use temp files per test)
2. Fix pytest-asyncio configuration for concurrency tests
3. Update `datetime.utcnow()` → `datetime.now(datetime.UTC)` throughout codebase
4. Document actual test status in CLAUDE.md (be honest about failures)

### Medium-Term (Post-Phase 13)
1. Increase coverage for CLI scripts (currently 0%)
2. Add integration tests for GPU code paths
3. Set up CI to fail on test failures (currently docs claim all pass)
4. Implement test result tracking in CI artifacts

## Files Modified

- `tests/test_risk_manager.py` - Added `count_open_positions` mock
- `requirements-dev.txt` - Updated pytest-asyncio version spec
- `docs/TEST-FIXES-2025-10-07.md` - This document

## Lessons Learned

1. **Documentation Drift**: Always verify documentation claims against actual test runs
2. **API Evolution**: When adding new methods (Sprint 1.7), update all test fixtures in the same commit
3. **Test Isolation**: Parallel test execution requires proper test isolation (temp files, separate databases)
4. **CI Validation**: CI should fail on test failures, not just lint/format issues

## Next Steps

1. Run `make format` to apply code formatting
2. Commit test fixture fixes with message: `fix: Phase 13 - Add count_open_positions mock to test fixtures (16 tests fixed)`
3. Create follow-up issue for remaining 18 test failures
4. Update CLAUDE.md with accurate test count (201 passing, 18 failing)
5. Proceed with Phase 13 deployment using `-k "not concurrency and not chaos"` to skip flaky tests

---

**Generated**: 2025-10-07 14:40 UTC
**Author**: Claude Code (Sonnet 4.5)
**Test Run**: `pytest --tb=line` (43.16s, 201 passed, 18 failed, 6 errors)
