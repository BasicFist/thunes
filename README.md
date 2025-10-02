# THUNES - Quantitative Crypto Trading System

A quantitative cryptocurrency trading system implementing micro-transaction strategies (DCA, Grid, HFT) with comprehensive risk management and automated execution.

## 🎯 Project Status

**Phase**: MVP Development
**Environment**: Binance Spot Testnet
**Strategy**: SMA Crossover (baseline)

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
| 7 | WebSocket Streaming | 🚧 | Real-time bookTicker/aggTrade, reconnection logic |
| 8 | Risk Management | 🚧 | Kill-switch, max loss limits, cool-down |
| 9 | Alerts | 🚧 | Telegram notifications for trades/errors/PNL |
| 10 | Orchestration | 🚧 | APScheduler jobs, anti-overlap |
| 11 | Observability | 🚧 | Prometheus metrics, structured logs |
| 12 | CI/CD | ✅ | GitHub workflows, secrets management |
| 13 | Paper 24/7 | ⏳ | 7-day rodage without critical incidents |
| 14 | Micro-Live | ⏳ | 10-50€ live with strict limits |

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

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Telegram: [Optional community channel]

---

**Built with ❤️ for the quant community**
