# Quantitative Trading Techniques: 2024-2025 Research Findings

**Last Updated:** 2025-10-02
**Research Period:** January 2024 - October 2025
**Sources:** 30+ academic papers, industry publications, technical documentation

---

## Executive Summary

This document synthesizes cutting-edge quantitative trading research from 2024-2025, covering backtesting methodologies, machine learning strategies, risk management, market microstructure, and execution algorithms. Key findings include:

- **CPCV > Walk-Forward:** Combinatorial Purged Cross-Validation shows superior performance (2024 Physica A)
- **Optuna Multivariate TPE:** 15-30% improvement in hyperparameter optimization
- **Adaptive Kelly:** Hybrid Kelly + VIX scaling for optimal position sizing
- **HMM Regime Detection:** Outperforms clustering for market state identification
- **Transformer Models:** TFT and Helformer (2025) for time-series prediction

## Research Domains

### 1. Backtesting & Validation
- [Combinatorial Purged Cross-Validation (CPCV)](./ADVANCED-BACKTESTING.md#cpcv)
- [Triple Barrier Method](./ADVANCED-BACKTESTING.md#triple-barrier)
- [Meta-Labeling](./ADVANCED-BACKTESTING.md#meta-labeling)
- [Fractional Differentiation](./ADVANCED-BACKTESTING.md#fractional-differentiation)

### 2. Machine Learning
- [Online Learning with River + ADWIN](./MACHINE-LEARNING-STRATEGIES.md#online-learning)
- [Transformer Models (TFT, Helformer)](./MACHINE-LEARNING-STRATEGIES.md#transformers)
- [Reinforcement Learning (DQN, PPO, DDPG)](./MACHINE-LEARNING-STRATEGIES.md#reinforcement-learning)
- [Meta-Learning (QuantNet)](./MACHINE-LEARNING-STRATEGIES.md#meta-learning)
- [Graph Neural Networks](./MACHINE-LEARNING-STRATEGIES.md#gnn)

### 3. Risk & Position Management
- [Adaptive Kelly Criterion](./RISK-POSITION-MANAGEMENT.md#kelly-criterion)
- [CVaR / Expected Shortfall](./RISK-POSITION-MANAGEMENT.md#cvar)
- [HMM Regime Detection](./RISK-POSITION-MANAGEMENT.md#hmm)
- [Advanced Performance Metrics](./RISK-POSITION-MANAGEMENT.md#metrics)

### 4. Market Microstructure
- [Order Book Dynamics](./MARKET-MICROSTRUCTURE.md#order-book)
- [Bid-Ask Spread Analysis](./MARKET-MICROSTRUCTURE.md#bid-ask)
- [Slippage Modeling](./MARKET-MICROSTRUCTURE.md#slippage)
- [Execution Algorithms (TWAP/VWAP)](./MARKET-MICROSTRUCTURE.md#execution)

### 5. Statistical Arbitrage
- [Cointegration-Based Pairs Trading](./STATISTICAL-ARBITRAGE.md#cointegration)
- [Reinforcement Learning Pairs Trading](./STATISTICAL-ARBITRAGE.md#rl-pairs)
- [Copula-Based Trading](./STATISTICAL-ARBITRAGE.md#copula)

### 6. Volatility Forecasting
- [GARCH Models for Crypto](./VOLATILITY-FORECASTING.md#garch)
- [HAR Models](./VOLATILITY-FORECASTING.md#har)
- [Hybrid GARCH + LSTM](./VOLATILITY-FORECASTING.md#hybrid)
- [Evolving Multiscale GNN](./VOLATILITY-FORECASTING.md#gnn)

---

## Industry Leaders & Academic Sources

### Academia
- **Marcos López de Prado** - "Advances in Financial Machine Learning" (2018), 2024 Bernstein Fabozzi Award
- **arXiv Quantitative Finance** - 25+ papers from 2024-2025
- **Journals:** Physica A, Asia-Pacific Financial Markets, Financial Innovation, MDPI Mathematics

### Industry
- **Jane Street** - Deep learning in quantitative trading, petabyte-scale data processing
- **Two Sigma** - Machine learning approach to regime modeling (Feb 2024)
- **AQR Capital** - 2025 Capital Market Assumptions, Fusion Fund Series (June 2025)
- **Hudson & Thames** - mlfinlab library for financial ML

### Technical Resources
- **MLFinLab** - CPCV, purging, embargoing implementations
- **Optuna** - GPSampler (Sept 2025), multivariate TPE
- **River** - Online learning with ADWIN drift detection
- **QuantStats** - Performance analytics and reporting

---

## Implementation Priority Matrix

### Tier 1: Immediate High ROI (32 hours, 2-4 weeks)
| Enhancement | Hours | Impact | Dependencies |
|-------------|-------|--------|--------------|
| CPCV Implementation | 8 | ⭐⭐⭐⭐⭐ | scikit-learn, mlfinlab patterns |
| Optuna Multivariate TPE | 4 | ⭐⭐⭐⭐ | Existing Optuna setup |
| Adaptive Kelly Sizing | 8 | ⭐⭐⭐⭐⭐ | Position tracker |
| Dynamic Slippage Model | 6 | ⭐⭐⭐⭐ | Market data history |
| HMM Regime Detection | 6 | ⭐⭐⭐⭐ | hmmlearn library |

### Tier 2: Architecture Modernization (64 hours, 4-8 weeks)
- Async/await migration (20h) - *already planned*
- TimescaleDB migration (16h) - *already planned*
- Temporal Fusion Transformer (16h)
- River online learning + ADWIN (12h)

### Tier 3: Advanced Strategies (56 hours, 8-12 weeks)
- Statistical arbitrage: BTC-ETH pairs (12h)
- TWAP/VWAP execution algorithms (10h)
- Reinforcement learning (DQN baseline) (16h)
- Triple barrier + meta-labeling (10h)
- Fractional differentiation (8h)

### Tier 4: Production Hardening (44 hours, 12-16 weeks)
- Apache Kafka + Flink streaming (16h)
- CVaR risk management (8h)
- SHAP model interpretability (6h)
- Smart order routing (10h)
- MEV protection (4h)

---

## Key Research Findings by Topic

### Backtesting (2024-2025)

**CPCV vs Walk-Forward (Physica A, 2024)**
- CPCV shows lower Probability of Backtest Overfitting (PBO)
- Better Deflated Sharpe Ratio (DSR) across multiple studies
- Properly handles label overlaps through purging
- Embargo prevents leakage from serial correlation
- **Recommendation:** Replace planned walk-forward with CPCV (saves 4h, better results)

**Lopez de Prado Methods**
- **Triple Barrier:** Stop loss + profit take + expiration (2024 crypto pairs research)
- **Meta-Labeling:** Filter false positives from primary signals
- **Fractional Differentiation:** Sweet spot at 0 < d < 1 for stationarity + memory
- **Source:** "Advances in Financial Machine Learning" (2018), 2024 implementations

### Machine Learning (2024-2025)

**Transformer Models**
- **Temporal Fusion Transformer (TFT):** Attention mechanisms for time-series
- **Helformer (2025):** Latest transformer architecture for quantitative finance
- **Hybrid Transformer + GRU:** Combines long-range dependencies with sequential processing
- **Performance:** Outperforms LSTM on multi-horizon forecasting

**Reinforcement Learning**
- **DQN:** 12.3% ROI reported in 2024 research
- **PPO, DDPG, A2C:** Alternative algorithms for portfolio management
- **July 2024:** RL pairs trading on Binance BTC-fiat pairs (formation Oct-Nov 2023)

**Meta-Learning**
- **QuantNet:** 2-10x Sharpe ratio improvement (few-shot learning)
- **Transfer Learning:** Adapt models across different market regimes

**Online Learning**
- **River + ADWIN:** Concept drift detection for non-stationary markets
- **Continuous Adaptation:** No need for periodic retraining
- **Drift Detection:** ADWIN catches distribution shifts automatically

### Risk Management (2024)

**CVaR for Crypto Portfolios (Oct 2024)**
- Credibilistic CVaR framework for frequent extreme losses
- CVaR captures expected loss beyond VaR threshold
- Better for heavy-tailed distributions (crypto)
- **Source:** MDPI Mathematics, Oct 2024

**Advanced Metrics**
- **Sortino Ratio:** Penalizes only downside volatility (better than Sharpe for crypto)
- **Calmar Ratio:** Average return / max drawdown
- **Omega Ratio:** Probability-weighted profits/losses
- **Sterling Ratio:** Average annual drawdown focus
- **Deflated Sharpe Ratio (DSR):** Adjusts for multiple testing

**Kelly Criterion (2024)**
- **Fractional Kelly:** 0.10x-0.15x multiplier for safety
- **Hybrid Kelly + VIX:** Inverse volatility scaling
- **Risk Parity:** Allocate by risk contribution, not capital
- **Volatility Targeting:** Adjust position inversely to volatility

### Market Microstructure (2024)

**Order Book Dynamics (Dec 2024)**
- **arXiv Paper:** Chen-Shue, Li, Yong - Limit order book model with rough volatility
- **Hawkes Process:** Power-law tails for HFT dynamics
- **Quote Imbalance:** Top-of-book provides price movement signals

**Bid-Ask Spread (2024-2025)**
- **Barbon & Ranaldo (2024):** DEXs competitive for larger trades ($326B spot volume)
- **Adverse Selection:** 10% of effective spreads (vs <1% in equities)
- **Inventory Holding Costs:** 3x higher than equity markets

**Slippage Modeling**
- **Market Impact:** Proportional to sqrt(order volume)
- **Time-of-Day Effects:** Higher slippage during low liquidity hours
- **Dynamic Modeling:** Adjust by current volatility + volume

### Volatility Forecasting (2024)

**GARCH Models (Oct 2024)**
- **EGARCH & APARCH:** Best performers for Bitcoin (Business Analyst Journal)
- **ARIMA-GARCH:** (12,1,12)-GARCH(1,1) for BTC price analysis 2021-2023
- **HAR > GARCH:** HAR models on realized variance beat GARCH on daily data

**Hybrid Approaches**
- **GARCH + LSTM/GRU/BiLSTM:** Combine statistical + deep learning
- **Stochastic Volatility (SV):** Outperforms GARCH for extremely volatile crypto data
- **Longer Horizons:** SV forecasting errors more accurate for longer time frames

**Graph Neural Networks (2025)**
- **Evolving Multiscale GNN:** For cryptocurrency volatility forecasting
- **Financial Innovation Journal:** Recent publication on GNN approaches

### Statistical Arbitrage (2024)

**Cointegration Pairs Trading**
- **March 2024 arXiv:** RL for statistical arbitrage with cointegration
- **July 2024:** Optimal market-neutral multivariate pairs (post-COVID data to April 2024)
- **July 2024:** RL dynamic scaling for Binance BTC-fiat pairs
- **Tests:** Engle-Granger vs Johansen for cointegration detection

**BTC-ETH Pairs**
- High correlation makes them ideal for pairs trading
- Mean reversion strategies with z-score entry/exit
- Copula-based approaches for non-linear dependencies

---

## Python Libraries & Tools

### Backtesting Frameworks
- **VectorBT** - Fastest (fully vectorized), best for large-scale optimization
- **Backtrader** - Best documentation, live trading support, easier learning curve
- **Zipline** - Legacy Quantopian, good for factor-based equity research

### Optimization
- **Optuna** - GPSampler (Sept 2025), multivariate TPE (15-30% improvement)
- **Hyperband Pruning** - More efficient than MedianPruner

### Data & APIs
- **CCXT** - 100+ exchanges, async/await support, WebSocket via CCXT Pro
- **python-binance** - Current THUNES dependency
- **TimescaleDB** - 20x better insert performance vs PostgreSQL for time-series

### Analytics
- **QuantStats** - Tear sheets, Sharpe/Sortino/Calmar ratios, drawdown analysis
- **MLFinLab** - CPCV, triple barrier, meta-labeling (£100/month)
- **River** - Online learning with ADWIN drift detection

### ML Frameworks
- **scikit-learn** - TimeSeriesSplit, cross-validation
- **hmmlearn** - Hidden Markov Models for regime detection
- **XGBoost/LightGBM** - Ensemble methods, feature importance

---

## Binance API Best Practices (2024)

### Rate Limiting
- **IP Weight:** 1200 per minute (20 per second)
- **Order Limit:** 50 per 10 seconds (5 per second)
- **Monitor Headers:** `X-MBX-USED-WEIGHT-(intervalNum)(intervalLetter)`
- **Backoff Strategy:** Exponential decrease after HTTP 429
- **Consequences:** IP bans scale from 2 minutes to 3 days

### Order Execution
- **Partial Fills:** Monitor `executedQty` for completion tracking
- **Tick Size / Step Size:** Validate prices and quantities to avoid FILTER_FAILURE
- **Unfilled Count:** Filled orders decrement from your limit
- **WebSocket Streams:** Prefer over REST polling for real-time updates

### Best Practices
- Check `/api/v3/exchangeInfo` for current rate limits
- Use `retryAfter` field in rate-limited responses
- Maintain "conversion rate" (trades / total order ops) > threshold
- Avoid excessive order cancellations (impacts "weight" metric)

---

## Citations & References

### Academic Papers (arXiv 2024-2025)
1. "From Deep Learning to LLMs: A survey of AI in Quantitative Investment" (March 2025)
2. "FinXplore: An Adaptive Deep Reinforcement Learning Framework" (Sept 2024)
3. "Decision by Supervised Learning with Deep Ensembles" (March 2025)
4. "Advanced Statistical Arbitrage with Reinforcement Learning" (March 2024)
5. "Optimal market-neutral multivariate pair trading on cryptocurrency platform" (July 2024)
6. "Reinforcement Learning Pair Trading: A Dynamic Scaling approach" (July 2024)
7. "A Limit Order Book Model for High Frequency Trading with Rough Volatility" (Dec 2024)
8. "Attention-Based Reading, Highlighting, and Forecasting of the Limit Order Book" (Sept 2024)

### Journal Publications (2024)
1. Quang Phung Duy et al. - "Estimating and forecasting bitcoin daily prices using ARIMA-GARCH models" (Business Analyst Journal, Oct 2024)
2. Brauneis & Sahiner - "Crypto Volatility Forecasting: HAR, Sentiment, ML" (Asia-Pacific Financial Markets, 2024)
3. "Cryptocurrency Portfolio Allocation under Credibilistic CVaR Criterion" (MDPI, Oct 2024)
4. "Forecasting cryptocurrency volatility using evolving multiscale GNN" (Financial Innovation, 2025)
5. Barbon & Ranaldo - DEX competitiveness research (2024)

### Industry Publications
1. AQR Capital - "2025 Capital Market Assumptions for Major Asset Classes"
2. Two Sigma - "A Machine Learning Approach to Regime Modeling" (Feb 2024)
3. Jane Street - Quantitative Research Blog (2024)
4. Man Group - "Covering Your Tail: Expected Shortfall in Tail Risk Management" (2024)

### Books
1. Marcos López de Prado - "Advances in Financial Machine Learning" (2018)
   - 2024 Bernstein Fabozzi Award recipient
   - 2025 Knight Officer of Royal Order of Civil Merit (Spain)

### Technical Documentation
1. Optuna Documentation - GPSampler, Multivariate TPE (2025)
2. scikit-learn Documentation - TimeSeriesSplit, cross-validation
3. River Documentation - ADWIN drift detection
4. MLFinLab Documentation - CPCV, purging, embargoing
5. Binance API Documentation - Rate limits (2024)
6. CCXT Documentation - Async/WebSocket best practices

---

## Next Steps

### Immediate Actions (Week 1-2)
1. **Review Tier 1 Enhancements** - Validate priority order
2. **Quick Win:** Implement Optuna multivariate TPE (4h)
3. **High Impact:** Begin CPCV implementation (8h, replaces walk-forward)

### Short-Term (Month 1-2)
4. Adaptive Kelly position sizing (8h)
5. Dynamic slippage modeling (6h)
6. HMM regime detection (6h)

### Medium-Term (Month 3-4)
7. Evaluate Tier 2 architecture changes
8. TimescaleDB vs InfluxDB decision
9. Begin Temporal Fusion Transformer experimentation

### Long-Term (Month 5-6)
10. Statistical arbitrage BTC-ETH pairs
11. Reinforcement learning baseline
12. Production hardening (Tier 4)

---

## Appendix: Quick Reference Tables

### Cross-Validation Methods
| Method | Leakage Prevention | Time Complexity | Best For |
|--------|-------------------|-----------------|----------|
| Standard K-Fold | None | O(n) | IID data only |
| TimeSeriesSplit | Chronological | O(n) | Basic time-series |
| Walk-Forward | Embargo | O(n²) | Sequential validation |
| **CPCV** | Purging + Embargo | O(n³) | **Financial data** |

### Position Sizing Methods
| Method | Risk Adjustment | Complexity | THUNES Status |
|--------|----------------|------------|---------------|
| Fixed Dollar | None | Low | ✅ Implemented |
| Fixed % | Simple | Low | ❌ Not implemented |
| Volatility-Based | Vol scaling | Medium | ❌ Planned |
| **Adaptive Kelly** | Win rate + Vol | **High** | **⏳ Tier 1** |
| Risk Parity | Risk contribution | High | ⏳ Tier 3 |

### ML Algorithms Comparison
| Algorithm | Training Speed | Inference Speed | Drift Handling | Interpretability |
|-----------|---------------|-----------------|----------------|------------------|
| Linear Regression | Fast | Fast | None | High |
| XGBoost | Medium | Fast | Retrain | Medium (SHAP) |
| LSTM | Slow | Medium | Retrain | Low |
| **TFT** | **Slow** | **Medium** | **Retrain** | **Medium** |
| **River (Online)** | **Continuous** | **Fast** | **ADWIN** | **Medium** |
| DQN (RL) | Very Slow | Fast | Continuous | Low |

### Risk Metrics
| Metric | Formula | Interpretation | Threshold |
|--------|---------|---------------|-----------|
| Sharpe Ratio | (Return - RF) / σ | Risk-adjusted return | > 1.0 good, > 2.0 excellent |
| Sortino Ratio | (Return - RF) / Downside σ | Downside-only penalty | > 1.5 good, > 3.0 excellent |
| Calmar Ratio | Avg Return / Max DD | Return per unit drawdown | > 0.5 good, > 1.0 excellent |
| Max Drawdown | Peak to Trough | Worst loss | < 20% acceptable |
| **CVaR (95%)** | **E[Loss \| Loss > VaR]** | **Expected tail loss** | **< 5% portfolio** |

---

**Document Status:** Living document, updated as new research emerges
**Maintainer:** THUNES Quantitative Research
**Last Research Update:** 2025-10-02
**Next Review:** 2025-11-02 (monthly)
