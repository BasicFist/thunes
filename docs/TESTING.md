# Testing Guide

## Test Environment Setup

### Quick Start
```bash
# Create and activate virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install development dependencies (includes core + testing)
pip install -r requirements-dev.txt

# Run all tests
make test
```

### Test Categories

**Core Tests** (174 passing, 13 failing):
- `test_config.py` - Configuration and settings validation
- `test_risk_manager.py` - Kill-switch, position limits, audit trail
- `test_circuit_breaker.py` - Fault tolerance and state transitions
- `test_filters.py` - Exchange order validation (prevents -1013 errors)
- `test_ws_stream.py` - WebSocket streaming and reconnection
- `test_position_tracker.py` - Position tracking and SQLite persistence
- `test_performance_tracker.py` - Performance monitoring and decay detection
- `test_scheduler.py` - Job scheduling and orchestration
- `test_telegram.py` - Telegram notifications
- `test_paper_trader_integration.py` - End-to-end paper trading

**Research Tests** (require requirements-research.txt):
- `test_strategy.py` - Backtesting strategies (SMA, RSI)
- Tests requiring `vectorbt`, `optuna`, `hmmlearn`

### Running Tests

```bash
# All tests with coverage
make test
# Output: 190 tests collected, 174 passed, 13 failed, 54% coverage

# Specific test file
pytest tests/test_risk_manager.py -v

# Specific test function
pytest tests/test_filters.py::test_round_price -v

# Skip research tests (for CI with requirements-dev only)
pytest -m "not research"

# Verbose output with tracebacks
pytest -vv --tb=long
```

### Known Test Issues (2025-10-04)

**13 Failing Tests** (pre-existing code issues, not blockers):
- `test_performance_tracker.py` (12 failures) - AttributeError in rolling Sharpe calculation
- `test_position_tracker.py` (1 failure) - AttributeError in history retrieval

These failures do NOT block Sprint 1-3 execution. They should be fixed in a separate maintenance sprint.

### CI/CD Testing

GitHub Actions CI runs with `requirements-dev.txt`:
```yaml
- name: Install dependencies
  run: pip install -r requirements-dev.txt

- name: Run tests
  run: pytest -v --cov=src --cov-report=xml
```

Expected CI results:
- 174+ tests passing
- Coverage >50%
- Build time <3 minutes (down from 10 minutes with full requirements)

### Test Markers

```python
# Mark research tests (skip in CI)
@pytest.mark.research
def test_backtest_strategy():
    ...

# Mark async tests
@pytest.mark.asyncio
async def test_async_function():
    ...
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# View in browser
open htmlcov/index.html

# Terminal coverage report
pytest --cov=src --cov-report=term-missing
```

### Debugging Tests

```bash
# Run with debugger on failure
pytest --pdb

# Stop on first failure
pytest -x

# Show local variables in traceback
pytest -l

# Disable output capture (see print statements)
pytest -s
```

## Sprint 1 Test Requirements

### Sprint 1.1: Test Environment ✅ COMPLETE
- [x] Install requirements-dev.txt in .venv
- [x] Verify 174+ tests pass
- [x] Document test setup in this file

### Sprint 1.4: Concurrency Test Suite (PENDING)
- [ ] Create `tests/test_ws_stream_concurrency.py` (10+ tests)
- [ ] Create `tests/test_circuit_breaker_chaos.py` (10+ tests)
- [ ] Create `tests/test_risk_manager_concurrent.py` (10+ tests)
- [ ] Target: 30+ new tests, all passing

## Troubleshooting

**"ModuleNotFoundError: No module named 'X'"**
- Activate virtual environment: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements-dev.txt`

**"ImportError: No module named 'vectorbt'"**
- Research tests require additional dependencies
- Install: `pip install -r requirements-research.txt`
- Or skip: `pytest -m "not research"`

**Tests hang or timeout**
- Some tests may interact with testnet (slow)
- Skip integration tests: `pytest -m "not integration"`
- Increase timeout: `pytest --timeout=300`

**Coverage too low**
- Run full test suite: `make test`
- Check missing lines: `pytest --cov=src --cov-report=term-missing`
- Add tests for uncovered code paths

---

**Last Updated**: 2025-10-04 by Claude Code (Sprint 1.1)
