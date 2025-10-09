# Contributing to THUNES

Thank you for your interest in contributing to THUNES! This document provides guidelines for contributing to the project.

---

## 📚 Before You Start

### Required Reading
1. **[AGENTS.md](../AGENTS.md)** - Repository guidelines and coding standards
2. **[CLAUDE.md](../CLAUDE.md)** - Comprehensive development guide
3. **[README.md](../README.md)** - Project overview
4. **[docs/TESTING.md](../docs/TESTING.md)** - Testing requirements

### Project Status
**Current Phase**: Phase 13 (Binance Spot Testnet Deployment)
**Deployment Readiness**: 51% → 72% (post-drill) → 81% (post-rodage)
**Test Coverage**: 203/225 tests passing (90.2%)

---

## 🚀 Quick Start for Contributors

### 1. Fork & Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/THUNES.git
cd THUNES
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
make install              # Production + development dependencies
# OR for specific sets:
make install-core         # Core dependencies only (30 packages)
make install-dev          # + Development tools (15 packages)
make install-research     # + Research/ML libraries (45 packages)

# Set up pre-commit hooks
pre-commit install
```

### 3. Configure Environment

```bash
# Copy environment template
cp .env.template .env

# Edit .env with your Binance testnet credentials
# Get testnet API keys from: https://testnet.binance.vision
```

### 4. Verify Setup

```bash
# Run tests to verify environment
make test

# Run linters
make lint

# Format code
make format
```

---

## 🛠️ Development Workflow

### Branch Naming

Use descriptive branch names following this pattern:

```
feature/short-description    # New features
fix/short-description        # Bug fixes
docs/short-description       # Documentation updates
refactor/short-description   # Code refactoring
test/short-description       # Test additions/fixes
```

**Examples**:
- `feature/add-rsi-strategy`
- `fix/websocket-reconnection`
- `docs/update-deployment-guide`
- `refactor/risk-manager-api`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, CI, etc.)
- `perf`: Performance improvements

**Examples**:

```bash
# Simple commit
git commit -m "feat: add RSI strategy indicator"

# Detailed commit
git commit -m "fix: prevent WebSocket reconnection deadlock

Implements reconnect queue pattern to avoid watchdog deadlock.

- Add asyncio.Queue for reconnection requests
- Process reconnections serially in background task
- Add tests for concurrent reconnection attempts

Fixes #42"
```

### Code Quality Standards

#### Type Safety (Strict)
- **All functions** must have type hints
- Run `mypy src/` before committing
- No `type: ignore` comments without justification

```python
# ✅ Good
def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Calculate Sharpe ratio from returns."""
    pass

# ❌ Bad
def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    pass
```

#### Testing Requirements
- **Minimum 80% code coverage** for new code
- **100% coverage for security-critical modules** (authentication, secrets, audit trail)
- All new features must include tests before PR approval

```bash
# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test
pytest tests/test_risk_manager.py::test_kill_switch_activation -v
```

#### Code Style
- **Formatting**: Black (line length 100)
- **Linting**: Ruff (strict mode)
- **Import sorting**: Ruff isort

```bash
# Format code (automatically)
make format

# Check linting
make lint

# Run pre-commit hooks manually
pre-commit run --all-files
```

---

## 🧪 Testing Guidelines

### Test Organization

```
tests/
├── test_*.py              # Unit tests (fast, isolated)
├── test_*_integration.py  # Integration tests (slower, dependencies)
└── benchmarks/            # Performance benchmarks
```

### Writing Tests

```python
import pytest
from src.risk.manager import RiskManager

def test_kill_switch_activation():
    """Test that kill-switch activates when daily loss exceeds threshold."""
    # Arrange
    risk_manager = RiskManager(max_daily_loss=20.0)

    # Act
    is_valid, reason = risk_manager.validate_trade(
        symbol="BTCUSDT",
        quote_qty=25.0,  # Exceeds max_daily_loss
        side="BUY"
    )

    # Assert
    assert not is_valid
    assert "kill-switch" in reason.lower()
    assert risk_manager.is_kill_switch_active()
```

### Test Fixtures

Use pytest fixtures for common setup:

```python
@pytest.fixture
def isolated_audit_trail(tmp_path, monkeypatch):
    """Provide isolated audit trail for each test."""
    audit_file = tmp_path / "audit_trail.jsonl"
    monkeypatch.setattr(
        "src.risk.audit_trail.AUDIT_TRAIL_FILE",
        str(audit_file)
    )
    return audit_file
```

### Test Coverage Requirements

| Module | Minimum Coverage | Rationale |
|--------|------------------|-----------|
| **src/risk/** | 100% | Security-critical (kill-switch, limits) |
| **src/filters/** | 95% | Prevents order rejections |
| **src/alerts/** | 90% | Notification reliability |
| **src/data/** | 85% | Data integrity |
| **Other modules** | 80% | General quality standard |

---

## 📝 Pull Request Process

### 1. Create PR

```bash
# Push your branch
git push origin feature/your-feature

# Create PR on GitHub
# Title format: "feat: add RSI strategy indicator"
# Use PR template (if available)
```

### 2. PR Description Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update

## Testing
- [ ] Tests added for new functionality
- [ ] All tests passing locally (`make test`)
- [ ] Coverage maintained/improved (`make test`)
- [ ] Linting passing (`make lint`)

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated (if applicable)
- [ ] No breaking changes (or documented)
- [ ] Ready for review

## Related Issues
Fixes #42
Closes #43
```

### 3. Code Review

All PRs require:
- ✅ At least one approval (can be self-approved for minor changes)
- ✅ All CI checks passing (lint, test, coverage)
- ✅ No merge conflicts
- ✅ Documentation updated (if applicable)

**Review Focus Areas**:
- Logic correctness
- Test coverage
- Performance implications
- Security considerations
- Documentation clarity

### 4. Merge

- **Small PRs (<400 lines)**: Direct merge after approval
- **Large PRs (>400 lines)**: Split into smaller PRs if possible
- **Squash merge**: Preferred for feature branches
- **Rebase**: For keeping history clean

---

## 🎯 Contribution Areas

### High-Priority Areas

1. **Phase 13 Validation** (Current Priority)
   - Test DR drill procedures
   - Validate configuration workflows
   - Document rodage results

2. **Test Coverage Improvements**
   - WebSocket concurrency tests (10 failing)
   - Circuit breaker chaos tests (7 failing)
   - Integration test expansion

3. **Documentation**
   - API documentation (docstrings)
   - Architecture diagrams
   - Tutorial content

4. **Performance Optimization**
   - GPU feature engineering (selective use)
   - Database query optimization
   - Memory profiling

### Medium-Priority Areas

5. **Prometheus Metrics** (Phase 11)
   - Metric definitions
   - Grafana dashboards
   - Alerting rules

6. **Strategy Development** (Phase 15+)
   - New indicators (RSI, MACD, Bollinger Bands)
   - ML/AI strategies
   - Multi-strategy ensemble

7. **Compliance & Security**
   - Audit trail enhancements
   - Regulatory compliance features
   - Security hardening

---

## 🐛 Bug Reports

### Before Filing

1. Check existing issues
2. Verify bug on latest main branch
3. Reproduce with minimal example

### Bug Report Template

```markdown
**Describe the bug**
Clear description of the issue.

**To Reproduce**
Steps to reproduce:
1. Run `make backtest`
2. Observe error in logs
3. See error

**Expected behavior**
What should happen instead.

**Environment**
- OS: Ubuntu 22.04
- Python: 3.12.0
- Branch: main (commit sha)

**Logs/Screenshots**
```
[Paste relevant logs]
```

**Additional context**
Any other relevant information.
```

---

## 💡 Feature Requests

### Before Requesting

1. Check roadmap (`docs/roadmap/`)
2. Review existing feature requests
3. Consider if it aligns with project goals

### Feature Request Template

```markdown
**Feature Description**
Clear description of the proposed feature.

**Problem it Solves**
What problem does this address?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other approaches you've thought about.

**Additional Context**
Any mockups, diagrams, or references.
```

---

## 🔒 Security

### Reporting Security Issues

**DO NOT** file public issues for security vulnerabilities.

Instead:
1. Email: (Add security contact email)
2. Provide detailed description
3. Allow reasonable time for fix before disclosure

### Security Best Practices

- ⚠️ Never commit secrets (`.env`, API keys, credentials)
- ⚠️ Use testnet for development (not mainnet)
- ⚠️ Disable withdrawal permissions on API keys
- ⚠️ Review security checklist before PR

---

## 📋 Style Guide

### Python

Follow [PEP 8](https://pep8.org/) with project-specific rules:

```python
# Line length: 100 characters
# String quotes: Double quotes preferred
# Imports: Sorted by ruff isort

from typing import Optional

import pandas as pd
from pydantic import BaseModel

from src.config import settings
from src.utils.logger import get_logger


class Position(BaseModel):
    """Trading position with risk management."""

    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: float
    entry_price: float
    stop_loss: Optional[float] = None

    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L."""
        if self.side == "BUY":
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity
```

### Documentation

- **Docstrings**: Google style
- **Comments**: Explain "why", not "what"
- **Type hints**: Always required

```python
def validate_trade(
    self,
    symbol: str,
    quote_qty: float,
    side: str,
    strategy_id: str = "unknown"
) -> tuple[bool, str]:
    """Validate if trade is allowed under current risk limits.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        quote_qty: Trade size in quote currency (USDT)
        side: Order side ("BUY" or "SELL")
        strategy_id: Strategy identifier for audit trail

    Returns:
        Tuple of (is_valid, reason):
            - is_valid: True if trade allowed, False otherwise
            - reason: Human-readable validation result

    Example:
        >>> is_valid, reason = risk_manager.validate_trade("BTCUSDT", 10.0, "BUY")
        >>> if not is_valid:
        ...     logger.error(f"Trade rejected: {reason}")
    """
    pass
```

---

## 🤝 Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the project
- Show empathy towards other community members

### Getting Help

- **Documentation**: `docs/README.md` (master index)
- **Quick Start**: `START-HERE.md` (Phase 13 deployment)
- **Development Guide**: `CLAUDE.md` (comprehensive)
- **Troubleshooting**: `docs/phase-13/CONFIGURATION_GUIDE.md`

### Communication

- **Issues**: For bugs, feature requests, questions
- **Pull Requests**: For code contributions
- **Discussions**: (Add if GitHub Discussions enabled)

---

## 📜 License

By contributing to THUNES, you agree that your contributions will be licensed under the same license as the project.

(Add LICENSE file reference if applicable)

---

## 🎓 Learning Resources

### Project-Specific
- `docs/research/REGULATORY-ML-LANDSCAPE-2025.md` - ML compliance
- `docs/research/GPU-INFRASTRUCTURE-FINDINGS.md` - GPU benchmarks
- `docs/roadmap/` - Future phases and sprints

### External Resources
- [Vectorbt Documentation](https://vectorbt.dev/) - Backtesting framework
- [Optuna Documentation](https://optuna.org/) - Hyperparameter optimization
- [Binance API Docs](https://binance-docs.github.io/apidocs/spot/en/) - Exchange API
- [Python Binance Library](https://python-binance.readthedocs.io/) - API wrapper

---

## 🙏 Thank You

Thank you for contributing to THUNES! Every contribution, whether it's code, documentation, bug reports, or feature requests, helps make this project better.

---

**Last Updated**: 2025-10-09
**Current Phase**: Phase 13 (Binance Spot Testnet Deployment)
**Version**: 0.13.0

For questions or clarifications, please open an issue or refer to the documentation.

