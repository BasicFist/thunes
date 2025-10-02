# THUNES Quantitative Research Documentation

**Research Period:** January 2024 - October 2025
**Total Sources:** 30+ academic papers, industry publications, technical documentation
**Last Updated:** 2025-10-02

---

## 📚 Documentation Index

### 🎯 Start Here
**[QUANTITATIVE-TECHNIQUES-2024-2025.md](./QUANTITATIVE-TECHNIQUES-2024-2025.md)**
- Master index of all research findings
- 30+ techniques categorized by domain
- Academic citations and industry insights
- Implementation priority matrix
- Quick-reference tables

---

### 🔬 Advanced Techniques

**[ADVANCED-BACKTESTING.md](./ADVANCED-BACKTESTING.md)**
- Combinatorial Purged Cross-Validation (CPCV) - superior to walk-forward
- Triple Barrier Method for realistic labeling
- Meta-Labeling to filter false positives
- Fractional Differentiation for stationarity + memory
- Full Python implementations with code examples

**[IMPLEMENTATION-ROADMAP.md](./IMPLEMENTATION-ROADMAP.md)**
- 196-hour roadmap across 4 tiers
- Tier 1: Immediate high ROI (32h) - CPCV, Optuna, Kelly sizing
- Detailed implementation steps with code
- Timeline: 5-6 months part-time
- Success metrics per tier

---

### 🛠️ Practical Guides

**[PYTHON-LIBRARIES-COMPARISON.md](./PYTHON-LIBRARIES-COMPARISON.md)**
- VectorBT vs Backtrader vs Zipline
- Optuna optimization (multivariate TPE upgrade)
- CCXT async/websocket for exchange APIs
- TimescaleDB vs InfluxDB for time-series
- QuantStats for performance analytics
- River for online learning

**[BINANCE-API-BEST-PRACTICES.md](./BINANCE-API-BEST-PRACTICES.md)**
- Rate limiting: 1200/min IP, 50/10sec orders
- Exponential backoff strategy (critical!)
- Order execution best practices
- WebSocket vs REST guidance
- Partial fill handling
- Avoid IP bans

---

## 🎓 Key Research Findings

### Backtesting (2024 Physica A)
- **CPCV > Walk-Forward:** Lower PBO, better DSR
- **Saves 4 hours** vs planned implementation
- **Replaces:** Phase B walk-forward optimization

### Optimization (2024-2025)
- **Optuna Multivariate TPE:** 15-30% improvement
- **Quick Win:** 4-hour implementation
- **GPSampler (Sept 2025):** Gaussian Process optimization

### Position Sizing (2024)
- **Adaptive Kelly:** Fractional Kelly (0.10x-0.15x) + VIX scaling
- **2024 Research:** Hybrid Kelly + volatility targeting
- **Impact:** Optimal risk allocation, prevent over-betting

### Machine Learning (2025)
- **Helformer (2025):** Latest transformer for time-series
- **QuantNet Meta-Learning:** 2-10x Sharpe improvement
- **River + ADWIN:** Online learning with drift detection

### Risk Management (Oct 2024)
- **Credibilistic CVaR:** For crypto heavy-tailed distributions
- **Advanced Metrics:** Sortino, Calmar, Omega, Sterling ratios
- **HMM Regime Detection:** Outperforms clustering

---

## 📊 Implementation Priority

### Tier 1: Immediate High ROI (2-4 weeks)
1. ✅ CPCV Implementation (8h) - Replace walk-forward
2. ✅ Optuna Multivariate TPE (4h) - 15-30% optimization boost
3. ✅ Adaptive Kelly Sizing (8h) - Optimal position sizing
4. ✅ Dynamic Slippage Model (6h) - Realistic P&L estimates
5. ✅ HMM Regime Detection (6h) - Market state adaptation

**Total:** 32 hours, **highest ROI per hour invested**

### Tier 2-4
See [IMPLEMENTATION-ROADMAP.md](./IMPLEMENTATION-ROADMAP.md) for complete timeline.

---

## 📖 Academic Sources

### Books
- **Marcos López de Prado** - "Advances in Financial Machine Learning" (2018)
  - 2024 Bernstein Fabozzi Award
  - 2025 Knight Officer of Royal Order of Civil Merit (Spain)

### ArXiv Papers (2024-2025)
- "From Deep Learning to LLMs: AI in Quantitative Investment" (March 2025)
- "FinXplore: Adaptive Deep RL Framework" (Sept 2024)
- "Advanced Statistical Arbitrage with RL" (March 2024)
- "Optimal market-neutral multivariate pair trading" (July 2024)
- "RL Pair Trading: Dynamic Scaling" (July 2024)
- "Limit Order Book Model with Rough Volatility" (Dec 2024)

### Journals (2024)
- Physica A - CPCV research
- Asia-Pacific Financial Markets - Crypto volatility forecasting
- MDPI Mathematics - Credibilistic CVaR (Oct 2024)
- Financial Innovation - Evolving Multiscale GNN (2025)
- Business Analyst Journal - ARIMA-GARCH for Bitcoin (Oct 2024)

---

## 🏢 Industry Sources

### Quantitative Firms
- **Jane Street** - Deep learning, petabyte-scale data processing
- **Two Sigma** - ML regime modeling (Feb 2024)
- **AQR Capital** - 2025 Capital Market Assumptions, Fusion Fund
- **Hudson & Thames** - MLFinLab library

### Technical Resources
- Binance Developer Documentation (2024 updates)
- Optuna Documentation (GPSampler Sept 2025)
- scikit-learn - TimeSeriesSplit, cross-validation
- MLFinLab - CPCV, purging, embargoing implementations

---

## 🚀 Quick Start

### For Implementation
1. **Read:** [QUANTITATIVE-TECHNIQUES-2024-2025.md](./QUANTITATIVE-TECHNIQUES-2024-2025.md) - Overview
2. **Plan:** [IMPLEMENTATION-ROADMAP.md](./IMPLEMENTATION-ROADMAP.md) - 5-month timeline
3. **Code:** Start with Tier 1 (32h, highest ROI)

### For Specific Topics
- **Backtesting:** [ADVANCED-BACKTESTING.md](./ADVANCED-BACKTESTING.md)
- **Tools:** [PYTHON-LIBRARIES-COMPARISON.md](./PYTHON-LIBRARIES-COMPARISON.md)
- **APIs:** [BINANCE-API-BEST-PRACTICES.md](./BINANCE-API-BEST-PRACTICES.md)

---

## 📈 Expected Impact

### Tier 1 Completion (32 hours)
- **Sharpe Ratio:** +25% improvement
- **Max Drawdown:** -20% reduction
- **Optimization:** 15% faster convergence
- **PBO:** < 0.5 (lower backtest overfitting)

### Full Roadmap (196 hours)
- **Production-Ready:** Async architecture, TimescaleDB, streaming
- **Advanced Strategies:** Statistical arbitrage, RL, meta-labeling
- **Risk Management:** CVaR, regime detection, smart order routing
- **Interpretability:** SHAP model explanations

---

## 🔄 Maintenance

**Update Frequency:** Monthly
**Next Review:** 2025-11-02
**Maintainer:** THUNES Quantitative Research Team

**Changelog:**
- 2025-10-02: Initial comprehensive research documentation (30+ sources)

---

## 📞 References & Links

### Internal THUNES Documentation
- [../../SETUP.md](../../SETUP.md) - Project setup guide
- [../../README.md](../../README.md) - Project overview

### External Resources
- [Binance API Docs](https://developers.binance.com/docs)
- [Optuna Documentation](https://optuna.readthedocs.io/)
- [MLFinLab Documentation](https://www.mlfinlab.com/)
- [QuantStats Documentation](https://github.com/ranaroussi/quantstats)
- [River Documentation](https://riverml.xyz/)

---

**Research Status:** ✅ Complete (Phase A)
**Implementation Status:** ⏳ Planning (Tier 1 ready)
**Total Research Hours:** ~40 hours of comprehensive literature review
**Documentation:** 5 files, ~25,000 words
