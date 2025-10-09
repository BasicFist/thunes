# THUNES - Quantitative Crypto Trading System

A quantitative cryptocurrency trading system implementing micro-transaction strategies (DCA, Grid, HFT) with comprehensive risk management and automated execution.

## 🎯 Project Status

**Phase**: Phase 13 - Binance Spot Testnet Deployment (Ready for Configuration + DR Drill)
**Environment**: Binance Spot Testnet
**Strategy**: SMA Crossover (baseline)
**Readiness**: 51% current → 72% post-drill → 81% post-rodage
**Test Coverage**: 203/225 tests passing (90.2%)

### 🚀 **Quick Links**
- **[START-HERE.md](START-HERE.md)** ⭐ - Complete Phase 13 deployment guide (2.5-3 hours to deployment authorization)
- **[docs/README.md](docs/README.md)** 📚 - Master documentation index (~78 files, 100% coverage)
- **[CLAUDE.md](CLAUDE.md)** 🤖 - AI development guidelines (comprehensive)
- **[CHANGELOG.md](CHANGELOG.md)** 📝 - Version history (v0.13.0)
- **[.github/CONTRIBUTING.md](.github/CONTRIBUTING.md)** 🤝 - Contribution guide

### 🧭 **Where to Go Next?**

**👤 I'm new to the project**
→ Read [README.md](#readme) (this page, 5 min) → Then [START-HERE.md](START-HERE.md) (deployment guide)

**🚀 I want to deploy Phase 13 to testnet**
→ Go to [START-HERE.md](START-HERE.md) → Follow 6-step execution plan (2.5-3 hours)

**🔍 I want to explore the documentation**
→ Go to [docs/README.md](docs/README.md) → Navigate by topic, date, or task

**💻 I want to contribute code**
→ Read [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) → Follow development workflow

**📊 I want to understand the architecture**
→ Read [CLAUDE.md](CLAUDE.md) → Review code organization and critical files

**🔬 I want to research ML/AI strategies**
→ Go to [docs/research/](docs/research/) → Start with [REGULATORY-ML-LANDSCAPE-2025.md](docs/research/REGULATORY-ML-LANDSCAPE-2025.md)

**🐛 I found a bug**
→ Check [.github/CONTRIBUTING.md#bug-reports](.github/CONTRIBUTING.md#bug-reports) → File issue with template

**❓ I have a question**
→ Check [docs/phase-13/CONFIGURATION_GUIDE.md](docs/phase-13/CONFIGURATION_GUIDE.md) (troubleshooting) → Or file issue

## 🏗️ Architecture

```
THUNES/
├── src/
│   ├── backtest/      # Vectorbt backtesting
│   ├── optimize/      # Optuna hyperparameter optimization
│   ├── live/          # Paper & live trading
│   ├── filters/       # Exchange order filters (critical)
│   ├── data/          # Data fetching & WebSocket streaming
│   ├── alerts/        # Telegram notifications
│   ├── risk/          # Risk management (kill-switch, limits)
│   └── utils/         # Logging, config
├── tests/             # Pytest test suite
├── artifacts/         # Backtest results, optimization studies
├── logs/              # Application logs
└── .github/workflows/ # CI/CD pipelines
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Binance Spot Testnet account with API keys
- (Optional) Telegram bot for alerts

### Installation

```bash
# Clone repository
git clone <your-repo-url>
cd THUNES

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
make install

# Configure environment
cp .env.template .env
# Edit .env with your API keys
```

### Configuration

Edit `.env` with your credentials:

```bash
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_API_SECRET=your_testnet_secret
TELEGRAM_BOT_TOKEN=your_telegram_bot_token  # Optional
TELEGRAM_CHAT_ID=your_chat_id  # Optional
```

### Run Backtest (Phase 3)

```bash
make backtest
# Output: artifacts/backtest/stats_BTCUSDT_1h.csv
```

### Run Optimization (Phase 4)

```bash
make optimize
# Output: artifacts/optuna/study.csv
```

### Run Paper Trading (Phase 5)

```bash
make paper
# Executes trades on Binance Testnet if signal detected
```

## 📊 Development Phases

| Phase | Description | Status | DoD |
|-------|-------------|--------|-----|
| 0 | Prerequisites & Setup | ✅ | `.env` configured, testnet account ready |
| 1 | Import & Setup | ✅ | Dependencies installed, pre-commit active |
| 2 | Smoke Tests | ✅ | `pytest` passes, linting clean |
| 3 | Backtest MVP | ✅ | SMA strategy backtested, stats generated |
| 4 | Optimization | ✅ | Optuna study completed, best params identified |
| 5 | Paper Trading | ✅ | Market orders executed on testnet |
| 6 | Order Filters | ✅ | Tick/step/minNotional validation, no -1013 errors |
| 7 | WebSocket Streaming | ✅ | Real-time bookTicker/aggTrade, reconnection logic |
| 8 | Risk Management | ✅ | Kill-switch, max loss limits, cool-down, audit trail |
| 9 | Alerts | ✅ | Telegram notifications for trades/errors/kill-switch |
| 10 | Orchestration | ✅ | APScheduler jobs, anti-overlap, monitoring |
| 11 | Observability | 🚧 | Prometheus metrics prepared, deployment pending |
| 12 | CI/CD | ✅ | GitHub workflows, quality gates enforced |
| 13 | Paper 24/7 | 🚧 | Code complete, ready for configuration + DR drill |
| 14 | Micro-Live | ⏳ | Pending Phase 13 completion (7-day rodage) |

**Legend**: ✅ Complete | 🚧 In Progress | ⏳ Pending

## 🛡️ Risk Management

**Hard Limits (Non-Negotiable)**:
- Max loss per trade: 5 USDT
- Max daily loss: 20 USDT
- Max concurrent positions: 3
- Cool-down after loss: 60 minutes

**Kill-Switch**: Automatically stops trading if daily loss exceeds threshold.

## 🧪 Testing

```bash
# Run all tests
make test

# Run linters
make lint

# Format code
make format

# Run pre-commit hooks
make pre-commit
```

## 🐳 Docker

```bash
# Build image
make docker-build

# Run container
make docker-run

# Stop container
make docker-stop
```

## 📈 CI/CD Workflows

- **CI**: Runs on push/PR (lint, test, type-check)
- **Backtest**: Weekly or on-demand
- **Optimize**: Manual trigger only
- **Paper Trading**: Every 10 minutes (requires approval)

## 🔐 Security

- **Secrets**: Stored in GitHub Secrets (never committed)
- **Testnet First**: Always test on testnet before production
- **API Permissions**: Trading only, no withdrawals
- **Environment Guards**: Production mode requires explicit confirmation

## 📚 Key Technologies

- **Backtesting**: [vectorbt](https://vectorbt.dev/)
- **Optimization**: [Optuna](https://optuna.org/)
- **Exchange**: [python-binance](https://github.com/sammchardy/python-binance)
- **ML**: [River](https://riverml.xyz/) (for drift detection)
- **Monitoring**: Prometheus + Loki
- **Scheduling**: APScheduler

## 🎓 Educational Insights

This project implements concepts from quantitative finance and algorithmic trading:

1. **Vectorized Backtesting**: Faster than event-driven for strategy validation
2. **Bayesian Optimization**: TPE sampler finds optimal parameters efficiently
3. **Exchange Filters**: Critical for preventing order rejections (tick/step/notional)
4. **Slippage Modeling**: Realistic backtest includes fees + slippage
5. **Kill-Switch Pattern**: Prevents runaway losses in production

## ⚠️ Disclaimer

**This software is for educational purposes only. Trading cryptocurrencies carries significant risk. Never trade with money you cannot afford to lose. Always start with testnet/paper trading.**

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](.github/CONTRIBUTING.md) for details.

**Quick Contributor Setup**:
```bash
# 1. Fork & clone
git clone https://github.com/YOUR_USERNAME/THUNES.git
cd THUNES

# 2. Setup environment
make install-dev
pre-commit install

# 3. Create feature branch
git checkout -b feature/amazing-feature

# 4. Make changes, test, commit
make test && make lint
git commit -m "feat: add amazing feature"

# 5. Push and create PR
git push origin feature/amazing-feature
```

**Read Before Contributing**:
- [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) - Complete contribution guide
- [AGENTS.md](AGENTS.md) - Repository guidelines
- [docs/TESTING.md](docs/TESTING.md) - Testing requirements

## 📚 Documentation

- **[START-HERE.md](START-HERE.md)** - Phase 13 deployment guide (ultimate entry point)
- **[docs/README.md](docs/README.md)** - Master documentation index (~78 files)
- **[CLAUDE.md](CLAUDE.md)** - Comprehensive development guide
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[.github/CONTRIBUTING.md](.github/CONTRIBUTING.md)** - Contribution guidelines

**Explore by Category**:
- **Phase 13**: [docs/phase-13/](docs/phase-13/) - Current deployment preparation
- **Archives**: [docs/archive/](docs/archive/) - Historical session records
- **Research**: [docs/research/](docs/research/) - Technical analysis & ML strategies
- **Roadmap**: [docs/roadmap/](docs/roadmap/) - Future phases (14-22)

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/THUNES/issues)
- **Documentation**: [docs/README.md](docs/README.md)
- **Troubleshooting**: [docs/phase-13/CONFIGURATION_GUIDE.md](docs/phase-13/CONFIGURATION_GUIDE.md)
- **Contributing**: [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md)

## 📈 Project Metrics

| Metric | Value |
|--------|-------|
| **Version** | 0.13.0 (Phase 13 pre-deployment complete) |
| **Test Coverage** | 203/225 tests passing (90.2%) |
| **Documentation** | ~78 files, ~35,000 words |
| **Code Quality** | 85% (excellent) |
| **Deployment Readiness** | 51% → 72% (post-drill) → 81% (post-rodage) |
| **CI/CD** | ✅ All quality gates enforced |

---

**Built with ❤️ for the quant community | Version 0.13.0 | Last Updated: 2025-10-09**
