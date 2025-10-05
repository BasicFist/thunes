# THUNES Phase 19-22: Production Scaling

**Version**: 1.0
**Last Updated**: 2025-10-05
**Duration**: 12+ weeks (480 hours)
**Prerequisites**: Phase 18 complete ✅ (HFT validated)

---

## Overview

Phases 19-22 focus on **horizontal scaling**, **multi-venue expansion**, **advanced risk management**, and **full automation**:

- **Phase 19**: Multi-Venue (3 weeks, 120h)
- **Phase 20**: Capacity Scaling (3 weeks, 120h)
- **Phase 21**: Advanced Risk (3 weeks, 120h)
- **Phase 22**: Full Automation (3 weeks, 120h)

---

## Phase 19: Multi-Venue (3 weeks, 120h)

### Goals

1. **CCXT Pro WebSocket**: Binance, Kraken, Coinbase simultaneous connections
2. **Cross-Exchange Arbitrage**: Detect price discrepancies (>0.5%)
3. **Unified Portfolio**: Aggregate positions across venues
4. **Multi-Venue Risk**: Consolidated exposure limits

---

### Week 1: CCXT Pro WebSocket (40h)

**Deliverables**:
- CCXT Pro installation (requires license for some exchanges)
- WebSocket connections to 3 venues (Binance, Kraken, Coinbase)
- Unified ticker stream aggregation

**Installation**:

```bash
# Install CCXT Pro (requires license key from ccxt.pro)
pip install ccxt[pro]

# Verify license
python -c "import ccxtpro; print(ccxtpro.__version__)"
```

**Implementation** (`src/streaming/multi_venue_ws.py`):

```python
"""Multi-venue WebSocket aggregator using CCXT Pro."""

import asyncio
import ccxtpro
from typing import Dict
from src.utils.logger import setup_logger

log = setup_logger(__name__)


class MultiVenueWebSocket:
    """Aggregate WebSocket streams from multiple venues."""

    def __init__(self, venues: list[str] = ["binance", "kraken", "coinbase"]):
        """
        Initialize multi-venue WebSocket.

        Args:
            venues: List of exchange names (e.g., ['binance', 'kraken'])
        """
        self.venues = venues
        self.exchanges = {}
        self.tickers = {}  # venue -> symbol -> ticker

    async def connect(self, api_keys: Dict[str, Dict[str, str]]):
        """
        Connect to all venues.

        Args:
            api_keys: {
                "binance": {"apiKey": "...", "secret": "..."},
                "kraken": {"apiKey": "...", "secret": "..."},
                ...
            }
        """
        for venue in self.venues:
            exchange_class = getattr(ccxtpro, venue)
            self.exchanges[venue] = exchange_class(api_keys.get(venue, {}))
            log.info(f"Connected to {venue} WebSocket")

    async def watch_tickers(self, symbols: list[str]):
        """
        Watch tickers from all venues.

        Args:
            symbols: List of symbols (e.g., ['BTC/USDT', 'ETH/USDT'])
        """
        tasks = [
            self._watch_venue_ticker(venue, symbol)
            for venue in self.venues
            for symbol in symbols
        ]
        await asyncio.gather(*tasks)

    async def _watch_venue_ticker(self, venue: str, symbol: str):
        """Watch ticker for specific venue and symbol."""
        exchange = self.exchanges[venue]

        while True:
            try:
                ticker = await exchange.watch_ticker(symbol)
                self.tickers.setdefault(venue, {})[symbol] = ticker
                log.debug(f"[{venue}] {symbol}: {ticker['last']}")
            except Exception as e:
                log.error(f"Error watching {venue} {symbol}: {e}")
                await asyncio.sleep(5)

    def get_best_bid_ask(self, symbol: str) -> Dict[str, Dict]:
        """
        Get best bid/ask across all venues.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')

        Returns:
            {
                "best_bid": {"venue": "kraken", "price": 43010.0},
                "best_ask": {"venue": "binance", "price": 43005.0},
            }
        """
        bids = []
        asks = []

        for venue, symbols in self.tickers.items():
            if symbol in symbols:
                ticker = symbols[symbol]
                bids.append({"venue": venue, "price": ticker["bid"]})
                asks.append({"venue": venue, "price": ticker["ask"]})

        best_bid = max(bids, key=lambda x: x["price"]) if bids else None
        best_ask = min(asks, key=lambda x: x["price"]) if asks else None

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
        }
```

**Success Criteria**:
- ✅ WebSocket streams active for 3 venues (Binance, Kraken, Coinbase)
- ✅ Latency <100ms (per ticker update)
- ✅ No connection drops for 24h

---

### Week 2: Cross-Exchange Arbitrage (40h)

**Deliverables**:
- Arbitrage opportunity detection (>0.5% spread)
- Execution engine (simultaneous BUY/SELL across venues)
- PnL tracking (net of fees)

**File**: `src/arbitrage/detector.py`

```python
"""Cross-exchange arbitrage detector."""

from typing import Dict, Optional

class ArbitrageDetector:
    """Detect arbitrage opportunities across exchanges."""

    def __init__(self, min_spread_bps: float = 50):
        """
        Initialize arbitrage detector.

        Args:
            min_spread_bps: Minimum spread in basis points (default: 50 bps = 0.5%)
        """
        self.min_spread_bps = min_spread_bps

    def detect(self, best_bid_ask: Dict) -> Optional[Dict]:
        """
        Detect arbitrage opportunity.

        Args:
            best_bid_ask: {
                "best_bid": {"venue": "kraken", "price": 43010.0},
                "best_ask": {"venue": "binance", "price": 43005.0},
            }

        Returns:
            {
                "buy_venue": "binance",
                "sell_venue": "kraken",
                "spread_bps": 116.3,  # (43010 / 43005 - 1) * 10000
                "profit_bps": 66.3,  # After fees (0.1% each side)
            }
            or None if no arbitrage
        """
        best_bid = best_bid_ask["best_bid"]
        best_ask = best_bid_ask["best_ask"]

        if best_bid is None or best_ask is None:
            return None

        # Calculate spread
        spread_bps = (best_bid["price"] / best_ask["price"] - 1) * 10000

        # Check if profitable (after fees)
        # Assume 0.1% fee on each side (20 bps total)
        profit_bps = spread_bps - 20

        if profit_bps > self.min_spread_bps:
            return {
                "buy_venue": best_ask["venue"],
                "sell_venue": best_bid["venue"],
                "spread_bps": spread_bps,
                "profit_bps": profit_bps,
            }

        return None
```

**Success Criteria**:
- ✅ Arbitrage opportunities detected (>10/day if markets inefficient)
- ✅ Execution latency <2s (buy + sell)
- ✅ Net profit >0.5% after fees

---

### Week 3: Unified Portfolio Service (40h)

**Deliverables**:
- Aggregate positions across venues
- Cross-venue PnL calculation
- Consolidated risk metrics (exposure, VaR)

**File**: `src/portfolio/multi_venue_service.py`

```python
"""Multi-venue portfolio aggregation."""

from typing import Dict
from decimal import Decimal

class MultiVenuePortfolio:
    """Aggregate portfolio across multiple venues."""

    def __init__(self):
        self.positions = {}  # venue -> symbol -> position

    def add_position(self, venue: str, symbol: str, qty: Decimal, price: Decimal):
        """Add or update position."""
        self.positions.setdefault(venue, {})[symbol] = {
            "qty": qty,
            "entry_price": price,
        }

    def get_total_exposure(self, prices: Dict[str, float]) -> float:
        """
        Calculate total exposure across venues.

        Args:
            prices: {symbol: current_price}

        Returns:
            Total exposure in quote currency (USDT)
        """
        total_expo = 0.0

        for venue, symbols in self.positions.items():
            for symbol, pos in symbols.items():
                current_price = prices.get(symbol, float(pos["entry_price"]))
                expo = float(pos["qty"]) * current_price
                total_expo += expo

        return total_expo

    def get_unrealized_pnl(self, prices: Dict[str, float]) -> float:
        """
        Calculate unrealized PnL across venues.

        Args:
            prices: {symbol: current_price}

        Returns:
            Unrealized PnL (quote currency)
        """
        total_pnl = 0.0

        for venue, symbols in self.positions.items():
            for symbol, pos in symbols.items():
                current_price = prices.get(symbol, float(pos["entry_price"]))
                pnl = (current_price - float(pos["entry_price"])) * float(pos["qty"])
                total_pnl += pnl

        return total_pnl
```

**Success Criteria**:
- ✅ Portfolio aggregation accurate (verified vs exchange balances)
- ✅ PnL calculation matches exchange reports (<€0.10 discrepancy)

---

## Phase 20: Capacity Scaling (3 weeks, 120h)

### Goals

1. **Horizontal Scaling**: Multiple scheduler instances (Docker Swarm or Kubernetes)
2. **PostgreSQL**: Replace SQLite (shared database for all instances)
3. **Redis Caching**: Reference prices, order book snapshots

---

### Week 1: PostgreSQL Migration (40h)

**Deliverables**:
- Migrate position tracker from SQLite to PostgreSQL
- Database connection pooling (pgbouncer)
- Replication (primary-replica for read scaling)

**Schema** (`migrations/001_initial.sql`):

```sql
-- Positions table
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    entry_price DECIMAL(18, 8) NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    side VARCHAR(4) NOT NULL,  -- BUY or SELL
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    exit_price DECIMAL(18, 8),
    pnl DECIMAL(18, 8),
    status VARCHAR(10) NOT NULL,  -- OPEN or CLOSED
    order_id VARCHAR(100) NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_entry_time ON positions(entry_time);

-- Audit trail
CREATE TABLE audit_events (
    id SERIAL PRIMARY KEY,
    event VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20),
    side VARCHAR(4),
    reason VARCHAR(200),
    risk_snapshot JSONB,
    git_sha VARCHAR(40),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_event ON audit_events(event);
CREATE INDEX idx_audit_timestamp ON audit_events(timestamp DESC);
```

**Success Criteria**:
- ✅ Position tracker migrated (all data preserved)
- ✅ Query performance <50ms (p95)
- ✅ Connection pooling (100 connections max)

---

### Week 2: Redis Caching (40h)

**Deliverables**:
- Redis cluster setup (3 nodes)
- Cache reference prices (TTL: 1s)
- Cache order book snapshots (Level 2)

**Implementation** (`src/data/redis_cache.py`):

```python
"""Redis cache for reference prices and order books."""

import redis
import json
from decimal import Decimal

class RedisCache:
    """Redis-backed cache for market data."""

    def __init__(self, host="localhost", port=6379):
        self.client = redis.Redis(host=host, port=port, decode_responses=True)

    def set_reference_price(self, symbol: str, price: float, ttl: int = 1):
        """
        Cache reference price with TTL.

        Args:
            symbol: Trading pair
            price: Reference price (mid/last)
            ttl: Time-to-live (seconds)
        """
        self.client.setex(f"price:{symbol}", ttl, str(price))

    def get_reference_price(self, symbol: str) -> float | None:
        """Get cached reference price."""
        price = self.client.get(f"price:{symbol}")
        return float(price) if price else None

    def set_order_book(self, symbol: str, book: dict, ttl: int = 1):
        """
        Cache order book snapshot.

        Args:
            symbol: Trading pair
            book: {"bids": [[price, qty], ...], "asks": [[price, qty], ...]}
            ttl: Time-to-live (seconds)
        """
        self.client.setex(f"book:{symbol}", ttl, json.dumps(book))

    def get_order_book(self, symbol: str) -> dict | None:
        """Get cached order book."""
        book = self.client.get(f"book:{symbol}")
        return json.loads(book) if book else None
```

**Success Criteria**:
- ✅ Cache hit rate >95% (reference prices)
- ✅ Latency <1ms (p95)

---

### Week 3: Docker Swarm Orchestration (40h)

**Deliverables**:
- Docker Swarm cluster (3 nodes)
- Multiple scheduler instances (horizontal scaling)
- Load balancer (HAProxy or Nginx)

**Docker Compose** (`docker-compose.swarm.yml`):

```yaml
version: '3.8'

services:
  scheduler:
    image: thunes:latest
    deploy:
      replicas: 3
      placement:
        max_replicas_per_node: 1
    environment:
      - THUNES_ENVIRONMENT=live
      - DATABASE_URL=postgresql://thunes:password@postgres:5432/thunes
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=thunes
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=thunes
    volumes:
      - postgres-data:/var/lib/postgresql/data

  redis:
    image: redis:7
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data

volumes:
  postgres-data:
  redis-data:
```

**Success Criteria**:
- ✅ 3 scheduler instances running
- ✅ Requests distributed evenly (load balancer)
- ✅ Failover <30s (if 1 instance crashes)

---

## Phase 21: Advanced Risk (3 weeks, 120h)

### Goals

1. **VaR Calculation**: Monte Carlo simulation (99% confidence)
2. **Correlation Matrix**: Portfolio hedging (reduce correlated exposure)
3. **Margin Utilization**: Optimize capital efficiency

---

### Week 1: VaR Calculation (40h)

**Deliverables**:
- Monte Carlo VaR (10,000 simulations)
- Historical VaR (rolling 30-day window)
- Alert if VaR >€50

**File**: `src/risk/var.py`

```python
"""Value-at-Risk (VaR) calculation."""

import numpy as np

class VaRCalculator:
    """Calculate VaR using Monte Carlo and historical methods."""

    def monte_carlo_var(
        self,
        returns: np.ndarray,
        confidence: float = 0.99,
        n_simulations: int = 10000,
    ) -> float:
        """
        Calculate VaR using Monte Carlo simulation.

        Args:
            returns: Historical returns (1D array)
            confidence: Confidence level (e.g., 0.99 = 99%)
            n_simulations: Number of simulations

        Returns:
            VaR (worst-case loss at confidence level)
        """
        # Fit normal distribution to returns
        mean = np.mean(returns)
        std = np.std(returns)

        # Simulate
        simulated_returns = np.random.normal(mean, std, n_simulations)

        # Calculate VaR (percentile at 1 - confidence)
        var = np.percentile(simulated_returns, (1 - confidence) * 100)

        return abs(var)  # Return positive value

    def historical_var(
        self,
        returns: np.ndarray,
        confidence: float = 0.99,
    ) -> float:
        """
        Calculate VaR using historical method.

        Args:
            returns: Historical returns (1D array)
            confidence: Confidence level

        Returns:
            VaR (worst-case loss at confidence level)
        """
        var = np.percentile(returns, (1 - confidence) * 100)
        return abs(var)
```

**Success Criteria**:
- ✅ VaR calculated daily (via scheduler)
- ✅ Alert if VaR >€50 (Telegram notification)

---

### Week 2: Correlation Matrix (40h)

**Deliverables**:
- Pairwise correlation calculation (all pairs)
- Hedging recommendations (reduce correlated exposure)

**File**: `src/risk/correlation.py`

```python
"""Correlation matrix for portfolio hedging."""

import numpy as np
import pandas as pd

class CorrelationAnalyzer:
    """Analyze asset correlations for hedging."""

    def calculate_matrix(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate pairwise correlation matrix.

        Args:
            returns: DataFrame with columns = assets, rows = returns

        Returns:
            Correlation matrix
        """
        return returns.corr()

    def recommend_hedges(self, corr_matrix: pd.DataFrame, threshold: float = 0.7) -> list:
        """
        Recommend hedges for highly correlated pairs.

        Args:
            corr_matrix: Correlation matrix
            threshold: Correlation threshold (e.g., 0.7 = 70%)

        Returns:
            List of (asset1, asset2, correlation)
        """
        hedges = []

        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                corr = corr_matrix.iloc[i, j]
                if abs(corr) > threshold:
                    hedges.append((
                        corr_matrix.columns[i],
                        corr_matrix.columns[j],
                        corr,
                    ))

        return sorted(hedges, key=lambda x: abs(x[2]), reverse=True)
```

**Success Criteria**:
- ✅ Correlation matrix calculated weekly
- ✅ Hedge recommendations sent via Telegram (if correlation >0.7)

---

### Week 3: Margin Utilization (40h)

**Deliverables**:
- Margin utilization calculation (used / available)
- Auto-deleveraging (if utilization >80%)

**File**: `src/risk/margin.py`

```python
"""Margin utilization optimization."""

class MarginManager:
    """Manage margin utilization."""

    def calculate_utilization(self, positions: list, margin_available: float) -> float:
        """
        Calculate margin utilization.

        Args:
            positions: List of open positions
            margin_available: Available margin (quote currency)

        Returns:
            Utilization ratio (0.0-1.0+)
        """
        margin_used = sum(pos.quantity * pos.entry_price for pos in positions)
        return margin_used / margin_available

    def recommend_deleverage(
        self, positions: list, utilization: float, threshold: float = 0.8
    ) -> list:
        """
        Recommend positions to close if over-leveraged.

        Args:
            positions: List of open positions
            utilization: Current utilization ratio
            threshold: Threshold for deleveraging (default: 0.8 = 80%)

        Returns:
            List of positions to close (sorted by largest first)
        """
        if utilization < threshold:
            return []

        # Sort by position size (largest first)
        sorted_positions = sorted(
            positions, key=lambda p: p.quantity * p.entry_price, reverse=True
        )

        return sorted_positions[:3]  # Close top 3 largest
```

**Success Criteria**:
- ✅ Margin utilization monitored real-time
- ✅ Auto-deleveraging if utilization >80%

---

## Phase 22: Full Automation (3 weeks, 120h)

### Goals

1. **Auto-Rebalancing**: Daily portfolio rebalancing
2. **Dynamic Position Sizing**: Kelly criterion
3. **Multi-Strategy Ensemble**: Combine SMA, RL, HFT
4. **Zero-Touch Operation**: No manual intervention for 30 days

---

### Week 1: Auto-Rebalancing (40h)

**Deliverables**:
- Daily rebalancing (target: equal-weight portfolio)
- Rebalance trigger (if drift >5%)

**File**: `src/portfolio/rebalancer.py`

```python
"""Automated portfolio rebalancing."""

from typing import Dict

class PortfolioRebalancer:
    """Rebalance portfolio to target weights."""

    def __init__(self, target_weights: Dict[str, float]):
        """
        Initialize rebalancer.

        Args:
            target_weights: {symbol: weight} (e.g., {"BTCUSDT": 0.5, "ETHUSDT": 0.5})
        """
        self.target_weights = target_weights

    def calculate_rebalance(
        self, current_holdings: Dict[str, float], total_value: float
    ) -> Dict[str, float]:
        """
        Calculate rebalance trades.

        Args:
            current_holdings: {symbol: value}
            total_value: Total portfolio value

        Returns:
            {symbol: trade_value} (positive=buy, negative=sell)
        """
        trades = {}

        for symbol, target_weight in self.target_weights.items():
            target_value = total_value * target_weight
            current_value = current_holdings.get(symbol, 0.0)
            trade_value = target_value - current_value

            if abs(trade_value) / total_value > 0.05:  # >5% drift
                trades[symbol] = trade_value

        return trades
```

**Success Criteria**:
- ✅ Portfolio rebalances daily (if drift >5%)
- ✅ Target weights maintained (<2% deviation)

---

### Week 2: Kelly Criterion Sizing (40h)

**Deliverables**:
- Kelly criterion calculation (optimal bet size)
- Dynamic position sizing (replaces fixed `quote_amount`)

**File**: `src/strategy/kelly.py`

```python
"""Kelly criterion position sizing."""

class KellyCriterion:
    """Calculate optimal position size using Kelly criterion."""

    def calculate_kelly(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Calculate Kelly fraction.

        Args:
            win_rate: Win rate (0.0-1.0)
            avg_win: Average win size (e.g., 0.05 = 5%)
            avg_loss: Average loss size (e.g., -0.02 = -2%)

        Returns:
            Kelly fraction (0.0-1.0)

        Formula: f = (p * b - q) / b
        Where:
        - p = win rate
        - q = 1 - p (loss rate)
        - b = avg_win / abs(avg_loss)
        """
        if avg_loss >= 0:
            return 0.0  # No losses → no sizing

        b = avg_win / abs(avg_loss)
        kelly = (win_rate * b - (1 - win_rate)) / b

        # Clamp to [0, 1]
        return max(0.0, min(1.0, kelly))
```

**Success Criteria**:
- ✅ Position sizes adjusted dynamically (Kelly fraction)
- ✅ Improved Sharpe vs fixed sizing (+0.2)

---

### Week 3: Multi-Strategy Ensemble (40h)

**Deliverables**:
- Combine SMA, RL, HFT strategies
- Ensemble voting (majority vote or weighted)
- Performance tracking (per-strategy attribution)

**File**: `src/strategy/ensemble.py`

```python
"""Multi-strategy ensemble."""

from typing import List, Literal

class StrategyEnsemble:
    """Combine multiple strategies via voting."""

    def __init__(self, strategies: List[object], weights: List[float] | None = None):
        """
        Initialize ensemble.

        Args:
            strategies: List of strategy objects
            weights: Optional weights (default: equal-weighted)
        """
        self.strategies = strategies
        self.weights = weights or [1.0 / len(strategies)] * len(strategies)

    def vote(self, **kwargs) -> Literal["BUY", "SELL", "HOLD"]:
        """
        Vote on action.

        Args:
            **kwargs: Strategy-specific parameters

        Returns:
            "BUY", "SELL", or "HOLD"
        """
        votes = []
        for strategy, weight in zip(self.strategies, self.weights):
            signal = strategy.get_signal(**kwargs)
            votes.append((signal, weight))

        # Weighted voting
        buy_weight = sum(w for sig, w in votes if sig == "BUY")
        sell_weight = sum(w for sig, w in votes if sig == "SELL")
        hold_weight = sum(w for sig, w in votes if sig == "HOLD")

        if buy_weight > max(sell_weight, hold_weight):
            return "BUY"
        elif sell_weight > max(buy_weight, hold_weight):
            return "SELL"
        else:
            return "HOLD"
```

**Success Criteria**:
- ✅ Ensemble outperforms individual strategies (Sharpe +0.3)
- ✅ Zero-touch operation for 30 days (no manual intervention)

---

## Summary Checklist

**Phase 19**:
- [ ] Deploy CCXT Pro WebSocket (3 venues)
- [ ] Implement arbitrage detection (>0.5% spread)
- [ ] Create unified portfolio service (cross-venue aggregation)

**Phase 20**:
- [ ] Migrate to PostgreSQL (shared database)
- [ ] Deploy Redis caching (reference prices, order books)
- [ ] Setup Docker Swarm (3 scheduler instances)

**Phase 21**:
- [ ] Implement VaR calculation (Monte Carlo + historical)
- [ ] Create correlation matrix (hedging recommendations)
- [ ] Add margin utilization monitoring (auto-deleveraging)

**Phase 22**:
- [ ] Deploy auto-rebalancing (daily, >5% drift trigger)
- [ ] Implement Kelly criterion sizing (dynamic position sizing)
- [ ] Create multi-strategy ensemble (SMA + RL + HFT)
- [ ] Validate zero-touch operation (30 days, no manual intervention)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-05
**Author**: Claude Code (Automated Scaling Roadmap)
