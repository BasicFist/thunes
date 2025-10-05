# THUNES Phase 15: RL Integration Specification

**Version**: 1.0
**Last Updated**: 2025-10-05
**Duration**: 6 weeks (240 hours)
**Prerequisites**: Phase 14 complete ✅
**Goal**: Integrate RL agents (FinRL/TensorTrade/TradeMaster) via adapter, validate in shadow mode

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Week 1-2: Core Infrastructure](#week-1-2-core-infrastructure)
3. [Week 3-4: Data Pipeline](#week-3-4-data-pipeline)
4. [Week 5: Simulated Exchange](#week-5-simulated-exchange)
5. [Week 6: Shadow Mode CLI](#week-6-shadow-mode-cli)
6. [Success Criteria & Validation](#success-criteria--validation)

---

## Architecture Overview

### Design Principles

1. **Separation of Concerns**: RL agents generate `RLAction` objects, adapter validates and converts to normalized orders
2. **Defense in Depth**: Multiple gates (policy whitelist, confidence threshold, kill-switch, risk limits, exchange filters)
3. **Idempotence**: Deterministic `client_order_id` generation (hash of action payload) prevents duplicates
4. **Observability**: All decisions logged to audit trail with Git SHA and model version
5. **Multi-Agent Support**: Same adapter handles FinRL, TensorTrade, TradeMaster, custom agents

### Component Map

```
RL Agent (FinRL/TensorTrade) → RLAction
                                    ↓
                          RLAdapter (Validation)
                                    ↓
                    ┌───────────────┴────────────────┐
                    ↓                                ↓
              Pre-Trade Gates              Exchange Normalization
      (Kill-Switch, Circuit Breaker,      (Tick/Step/Notional Filters)
       Policy Whitelist, Confidence)
                    ↓                                ↓
              Decision (ACCEPTED/REJECTED)    Normalized Order
                    ↓                                ↓
              Audit Trail                   ExecClient (CCXT)
                                                    ↓
                                             Binance API
```

### Data Flow

1. **RL Agent** generates `RLAction` (timestamp, symbol, side, qty_mode, qty_value, confidence)
2. **RLAdapter** validates via gates:
   - Policy whitelist: `policy_id in allowed_policies`?
   - TTL check: `now - ts_ns < ttl_ms`?
   - Confidence: `confidence >= min_confidence`?
   - Kill-switch: `is_kill_switch() and side == "BUY"`? (reject)
   - Circuit breaker: `is_open("BinanceAPI")`? (reject)
3. **Sizing & Price Shaping**: Convert `qty_mode` to `qty_base`, apply price bands
4. **Exchange Filters**: Round price/qty, validate notional
5. **Risk Validation**: Pre-trade check (position limits, cool-down, daily loss)
6. **Order Submission**: Idempotent placement via `client_order_id`
7. **Decision Logging**: Audit trail with `action_id`, `client_order_id`, status, reason

---

## Week 1-2: Core Infrastructure

### Deliverables

1. RL Adapter (`src/rl/adapter.py`) - 40h
2. Pydantic Schemas (`src/rl/schemas.py`) - 16h
3. Execution Layer (`src/exec/ccxt_client.py`) - 24h

Total: 80 hours

---

### 1. RL Adapter Implementation (40h)

**File**: `src/rl/adapter.py`

**Dependencies**:
- `src/risk/manager.py` (pre-trade validation)
- `src/filters/exchange_filters.py` (tick/step/notional)
- `src/utils/circuit_breaker.py` (API resilience)
- `src/data/store.py` (reference price cache)

**Full Implementation**:

```python
"""RL adapter for THUNES - validates and executes RL agent actions."""

from time import time_ns
from decimal import Decimal
from typing import Tuple
import hashlib
import json

from src.rl.schemas import RLAction, Decision
from src.utils.logger import setup_logger
from src.utils.retry import transient_retry
from src.monitoring.prometheus_metrics import (
    rl_actions_received,
    rl_actions_rejected,
    orders_placed,
)
from src.filters.exchange_filters import round_price_qty, validate_notional
from src.risk.manager import RiskManager
from src.exec.ccxt_client import ExecClient
from src.data.store import reference_price
from src.utils.circuit_breaker import circuit_monitor

log = setup_logger(__name__)


class RLAdapter:
    """Validate and execute RL agent actions with defense-in-depth."""

    def __init__(
        self,
        risk_manager: RiskManager,
        exec_client: ExecClient,
        allowed_policies: set[str],
        min_confidence: float,
    ):
        """
        Initialize RL adapter.

        Args:
            risk_manager: Risk manager for pre-trade validation
            exec_client: Execution client for order placement
            allowed_policies: Set of whitelisted policy IDs
            min_confidence: Minimum confidence threshold (0.0-1.0)
        """
        self.risk = risk_manager
        self.exec = exec_client
        self.allow = allowed_policies
        self.min_conf = min_confidence

    def handle(self, action: RLAction) -> Decision:
        """
        Validate and execute RL action.

        Args:
            action: RL action to validate and execute

        Returns:
            Decision (ACCEPTED/REJECTED/NOOP) with metadata

        Gates (in order):
        1. Policy whitelist
        2. TTL (time-to-live)
        3. Confidence threshold
        4. Kill-switch (blocks BUY only)
        5. Circuit breaker
        6. Price bands (if limit order)
        7. Exchange filters (tick/step/notional)
        8. Risk validation (position limits, cool-down, daily loss)
        9. Idempotent order submission
        """
        now = time_ns()

        # Generate stable action ID (deterministic hash)
        action_id = self._make_action_id(action)
        client_id = f"rl-{action_id[:16]}"

        # Prometheus: Record action received
        rl_actions_received.labels(
            policy=action.policy_id, symbol=action.symbol
        ).inc()

        # GATE 1: Policy whitelist
        if action.policy_id not in self.allow:
            return self._reject(action, action_id, client_id, "POLICY_NOT_ALLOWED")

        # GATE 2: TTL check (stale action)
        age_ms = (now - action.ts_ns) / 1_000_000
        if age_ms > action.ttl_ms:
            return self._reject(action, action_id, client_id, "STALE_ACTION")

        # GATE 3: Confidence threshold
        if action.confidence < self.min_conf:
            return self._reject(action, action_id, client_id, "LOW_CONFIDENCE")

        # GATE 4: Kill-switch (blocks BUY, allows SELL to exit positions)
        if self.risk.is_kill_switch() and action.side == "BUY":
            return self._reject(action, action_id, client_id, "KILL_SWITCH")

        # GATE 5: Circuit breaker
        if circuit_monitor.is_open("BinanceAPI"):
            return self._reject(action, action_id, client_id, "CIRCUIT_OPEN")

        # Sizing & price shaping
        ref_price = reference_price(action.symbol)  # Mid/last from cache
        qty_base, limit_price = self._quantize(action, ref_price)

        # GATE 6: Price bands (if limit order with constraints)
        if action.order_type == "LIMIT" and not self._price_in_band(
            action, ref_price
        ):
            return self._reject(action, action_id, client_id, "PRICE_BAND_VIOLATED")

        # GATE 7: Exchange filters (tick/step/notional)
        price_q, qty_q = round_price_qty(action.symbol, limit_price, qty_base)
        ok, why = validate_notional(action.symbol, price_q, qty_q)
        if not ok:
            return self._reject(action, action_id, client_id, f"FILTERS_{why}")

        # Prepare normalized order
        norm = {
            "symbol": action.symbol,
            "side": action.side,
            "order_type": action.order_type,
            "price": price_q,
            "qty": qty_q,
            "tif": action.tif,
        }

        # GATE 8: Risk validation (position limits, cool-down, daily loss)
        ok, risk_meta = self.risk.pre_trade_check(norm)
        if not ok:
            return self._reject(action, action_id, client_id, "RISK_REJECTED")

        # GATE 9: Idempotent order submission
        try:
            self._place_idempotent(norm, client_id)
        except Exception as e:
            log.exception("Order submission failed", action_id=action_id, error=str(e))
            return self._reject(action, action_id, client_id, "SUBMIT_ERROR")

        # Success
        orders_placed.labels(venue=self.exec.venue, type=action.order_type).inc()

        return Decision(
            action_id=action_id,
            client_order_id=client_id,
            status="ACCEPTED",
            normalized=norm,
            risk_snapshot=risk_meta,
            ts_ns=time_ns(),
        )

    def _reject(
        self, action: RLAction, action_id: str, client_id: str, reason: str
    ) -> Decision:
        """Log rejection and return Decision."""
        rl_actions_rejected.labels(
            reason=reason, policy=action.policy_id, symbol=action.symbol
        ).inc()

        log.warning(
            f"RL action rejected: {reason}",
            action_id=action_id,
            policy=action.policy_id,
            symbol=action.symbol,
        )

        return Decision(
            action_id=action_id,
            client_order_id=client_id,
            status="REJECTED",
            reason=reason,
            ts_ns=time_ns(),
        )

    def _make_action_id(self, action: RLAction) -> str:
        """Generate deterministic action ID (SHA256 hash)."""
        payload = action.model_dump_json(sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _quantize(
        self, action: RLAction, ref_price: float
    ) -> Tuple[Decimal, Decimal | None]:
        """
        Convert qty_mode to base quantity and determine limit price.

        Args:
            action: RL action with qty_mode/qty_value
            ref_price: Reference price (mid/last)

        Returns:
            (qty_base, limit_price)

        Qty Modes:
        - BASE: qty_value is base asset quantity (e.g., 0.001 BTC)
        - QUOTE: qty_value is quote asset quantity (e.g., 10 USDT)
        - RISK: qty_value is % of equity to risk (e.g., 0.01 = 1%)
        """
        if action.qty_mode == "BASE":
            qty_base = Decimal(str(action.qty_value))
            limit_price = (
                Decimal(str(action.limit_price))
                if action.limit_price
                else Decimal(str(ref_price))
            )

        elif action.qty_mode == "QUOTE":
            # Convert quote to base: qty_base = quote / price
            qty_base = Decimal(str(action.qty_value)) / Decimal(str(ref_price))
            limit_price = (
                Decimal(str(action.limit_price))
                if action.limit_price
                else Decimal(str(ref_price))
            )

        elif action.qty_mode == "RISK":
            # Risk-based sizing:
            # budget = equity * qty_value
            # qty_base = budget / (stop_loss_pct * ref_price)
            # Example: 1% risk, 2% stop → budget = 10000 * 0.01 = 100,
            #          qty_base = 100 / (0.02 * 43000) = 0.116 BTC

            equity = self.risk.get_equity()  # Total equity in quote currency
            budget = Decimal(str(equity)) * Decimal(str(action.qty_value))

            # Stop loss from constraints or default 2%
            stop_pct = Decimal(
                str(action.constraints.get("stop_loss_pct", 0.02))
            )

            qty_base = budget / (stop_pct * Decimal(str(ref_price)))
            limit_price = (
                Decimal(str(action.limit_price))
                if action.limit_price
                else Decimal(str(ref_price))
            )

        else:
            raise ValueError(f"Unknown qty_mode: {action.qty_mode}")

        return qty_base, limit_price

    def _price_in_band(self, action: RLAction, ref_price: float) -> bool:
        """
        Check if limit price is within allowed band.

        Args:
            action: RL action with limit_price and constraints
            ref_price: Reference price (mid/last)

        Returns:
            True if price within band, False otherwise

        Constraint:
        - action.constraints["price_band_bps"]: max deviation in basis points
          Example: 50 bps → limit price within ±0.5% of ref_price
        """
        band_bps = action.constraints.get("price_band_bps")

        if band_bps is None or action.limit_price is None:
            return True  # No constraint

        # Calculate deviation in bps
        deviation_bps = abs(float(action.limit_price) / ref_price - 1.0) * 1e4

        if deviation_bps > band_bps:
            log.warning(
                f"Price band violated: {deviation_bps:.1f} bps > {band_bps} bps",
                symbol=action.symbol,
                limit_price=float(action.limit_price),
                ref_price=ref_price,
            )
            return False

        return True

    @transient_retry  # Exponential backoff + jitter (see utils/retry.py)
    def _place_idempotent(self, norm: dict, client_id: str) -> None:
        """
        Place order idempotently.

        Args:
            norm: Normalized order (symbol, side, type, price, qty, tif)
            client_id: Deterministic client order ID

        Idempotence:
        - Check if order with client_id already exists
        - If yes, skip placement (no duplicate)
        - If no, place order
        """
        # Check if order already exists
        if self.exec.exists_by_client_id(norm["symbol"], client_id):
            log.info(f"Order {client_id} already exists (idempotent skip)")
            return

        # Place order
        self.exec.place_order(norm, client_id)
        log.info(f"Order {client_id} placed successfully", order=norm)
```

**Testing** (`tests/test_rl_adapter.py`):

```python
import pytest
from src.rl.adapter import RLAdapter
from src.rl.schemas import RLAction
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
from src.exec.ccxt_client import ExecClient
from decimal import Decimal
from time import time_ns

class TestRLAdapter:
    """Test RL adapter validation gates."""

    def test_policy_whitelist_rejection(self):
        """Test rejection of non-whitelisted policy."""
        rm = RiskManager(position_tracker=PositionTracker())
        exec_mock = MagicMock(spec=ExecClient)
        adapter = RLAdapter(rm, exec_mock, allowed_policies={"finrl_ppo"}, min_confidence=0.5)

        action = RLAction(
            ts_ns=time_ns(),
            policy_id="tensorTrade_dqn",  # Not in whitelist
            model_version="v1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            qty_mode="QUOTE",
            qty_value=Decimal("10.0"),
        )

        decision = adapter.handle(action)

        assert decision.status == "REJECTED"
        assert decision.reason == "POLICY_NOT_ALLOWED"
        exec_mock.place_order.assert_not_called()

    def test_stale_action_rejection(self):
        """Test rejection of stale action (TTL exceeded)."""
        rm = RiskManager(position_tracker=PositionTracker())
        exec_mock = MagicMock(spec=ExecClient)
        adapter = RLAdapter(rm, exec_mock, allowed_policies={"finrl_ppo"}, min_confidence=0.5)

        # Action generated 5 seconds ago (ttl_ms=1500 → stale)
        action = RLAction(
            ts_ns=time_ns() - 5_000_000_000,  # 5 seconds old
            policy_id="finrl_ppo",
            model_version="v1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            qty_mode="QUOTE",
            qty_value=Decimal("10.0"),
            ttl_ms=1500,
        )

        decision = adapter.handle(action)

        assert decision.status == "REJECTED"
        assert decision.reason == "STALE_ACTION"

    def test_kill_switch_blocks_buy(self):
        """Test kill-switch blocks BUY, allows SELL."""
        rm = RiskManager(position_tracker=PositionTracker())
        rm._daily_pnl = Decimal("-25.0")  # Trigger kill-switch
        rm._check_kill_switch()

        exec_mock = MagicMock(spec=ExecClient)
        adapter = RLAdapter(rm, exec_mock, allowed_policies={"finrl_ppo"}, min_confidence=0.0)

        # BUY should be rejected
        buy_action = RLAction(
            ts_ns=time_ns(),
            policy_id="finrl_ppo",
            model_version="v1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            qty_mode="QUOTE",
            qty_value=Decimal("10.0"),
        )

        decision = adapter.handle(buy_action)
        assert decision.status == "REJECTED"
        assert decision.reason == "KILL_SWITCH"

        # SELL should be accepted (allow exit positions)
        sell_action = RLAction(
            ts_ns=time_ns(),
            policy_id="finrl_ppo",
            model_version="v1",
            symbol="BTCUSDT",
            side="SELL",
            order_type="MARKET",
            qty_mode="BASE",
            qty_value=Decimal("0.001"),
        )

        # Mock exchange filters and risk validation
        with patch("src.rl.adapter.round_price_qty", return_value=(Decimal("43000"), Decimal("0.001"))):
            with patch("src.rl.adapter.validate_notional", return_value=(True, None)):
                with patch.object(rm, "pre_trade_check", return_value=(True, {})):
                    decision = adapter.handle(sell_action)
                    assert decision.status == "ACCEPTED"

    # Additional 20+ tests:
    # - test_confidence_threshold_rejection
    # - test_circuit_breaker_open_rejection
    # - test_price_band_violation_rejection
    # - test_filter_validation_rejection
    # - test_risk_validation_rejection
    # - test_idempotent_order_placement
    # - test_qty_mode_base_conversion
    # - test_qty_mode_quote_conversion
    # - test_qty_mode_risk_conversion
    # - test_limit_order_price_shaping
    # - test_market_order_execution
    # - test_decision_audit_trail_logging
    # - test_action_id_determinism
    # - test_prometheus_metrics_increment
    # - ...
```

---

### 2. Pydantic Schemas (16h)

**File**: `src/rl/schemas.py`

**Full Implementation**:

```python
"""Pydantic schemas for RL integration."""

from pydantic import BaseModel, Field, conint
from decimal import Decimal
from typing import Optional, Literal

# Type Aliases
Side = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]
QtyMode = Literal["BASE", "QUOTE", "RISK"]
TIF = Literal["GTC", "IOC", "FOK"]


class RLAction(BaseModel):
    """RL agent action (input to adapter)."""

    ts_ns: int = Field(..., description="Timestamp (nanoseconds since epoch)")
    policy_id: str = Field(..., description="Policy identifier (e.g., 'finrl_ppo_v1')")
    model_version: str = Field(..., description="Model version (e.g., 'v1.2.3')")
    symbol: str = Field(..., description="Trading pair (e.g., 'BTCUSDT')")
    side: Side
    order_type: OrderType
    qty_mode: QtyMode
    qty_value: Decimal = Field(..., gt=0, description="Quantity value (interpretation depends on qty_mode)")

    # Optional fields
    limit_price: Optional[Decimal] = Field(None, description="Limit price (required if order_type=LIMIT)")
    tif: TIF = Field(default="GTC", description="Time in force (GTC, IOC, FOK)")
    ttl_ms: conint(gt=0) = Field(default=1500, description="Action TTL (milliseconds)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Model confidence (0.0-1.0)")
    constraints: dict = Field(default_factory=dict, description="Constraints (e.g., price_band_bps, stop_loss_pct)")
    metadata: dict = Field(default_factory=dict, description="Additional metadata (e.g., features, state)")

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
        }


class Decision(BaseModel):
    """Adapter decision (output from adapter)."""

    action_id: str = Field(..., description="Deterministic action ID (SHA256 hash)")
    client_order_id: str = Field(..., description="Client order ID for exchange")
    status: Literal["ACCEPTED", "REJECTED", "NOOP"]
    reason: Optional[str] = Field(None, description="Rejection reason (if status=REJECTED)")
    normalized: Optional[dict] = Field(None, description="Normalized order parameters (if status=ACCEPTED)")
    risk_snapshot: Optional[dict] = Field(None, description="Risk snapshot at decision time")
    ts_ns: int = Field(..., description="Decision timestamp (nanoseconds)")

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
        }


class ExecFill(BaseModel):
    """Execution fill event (output from exchange)."""

    client_order_id: str
    symbol: str
    event: Literal["NEW", "PARTIAL", "FILLED", "CANCELED", "REPLACED"]
    price: Decimal
    qty_base: Decimal
    commission_quote: Decimal
    ts_ns: int

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
        }
```

**Testing** (`tests/test_rl_schemas.py`):

```python
import pytest
from src.rl.schemas import RLAction, Decision, ExecFill
from decimal import Decimal
from time import time_ns
from pydantic import ValidationError

class TestRLSchemas:
    """Test Pydantic schema validation."""

    def test_rl_action_valid(self):
        """Test valid RL action."""
        action = RLAction(
            ts_ns=time_ns(),
            policy_id="finrl_ppo",
            model_version="v1",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            qty_mode="QUOTE",
            qty_value=Decimal("10.0"),
        )

        assert action.symbol == "BTCUSDT"
        assert action.confidence == 1.0  # Default
        assert action.ttl_ms == 1500  # Default

    def test_rl_action_invalid_qty(self):
        """Test RL action with invalid quantity (qty_value<=0)."""
        with pytest.raises(ValidationError):
            RLAction(
                ts_ns=time_ns(),
                policy_id="finrl_ppo",
                model_version="v1",
                symbol="BTCUSDT",
                side="BUY",
                order_type="MARKET",
                qty_mode="QUOTE",
                qty_value=Decimal("-10.0"),  # Invalid: qty must be >0
            )

    def test_decision_serialization(self):
        """Test Decision JSON serialization."""
        decision = Decision(
            action_id="abc123",
            client_order_id="rl-abc123",
            status="ACCEPTED",
            normalized={"symbol": "BTCUSDT", "qty": Decimal("0.001")},
            ts_ns=time_ns(),
        )

        json_str = decision.model_dump_json()
        assert "abc123" in json_str
        assert "ACCEPTED" in json_str

    # Additional 10+ tests for edge cases, serialization, validation
```

---

### 3. Execution Layer (24h)

**File**: `src/exec/ccxt_client.py`

**Full Implementation**:

```python
"""Generic execution client using CCXT."""

import ccxt
from typing import Optional
from src.utils.logger import setup_logger
from src.utils.retry import Transient, transient_retry

log = setup_logger(__name__)


class ExecClient:
    """Generic execution client for CCXT exchanges."""

    def __init__(
        self,
        venue: str = "binance",
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        testnet: bool = True,
    ):
        """
        Initialize execution client.

        Args:
            venue: Exchange name (e.g., 'binance', 'kraken')
            api_key: API key
            secret: API secret
            testnet: Use testnet mode (default: True)
        """
        self.venue = venue

        # Initialize CCXT exchange
        exchange_class = getattr(ccxt, venue)
        self.ex = exchange_class({
            "apiKey": api_key,
            "secret": secret,
            "options": {"defaultType": "spot"},
        })

        if testnet:
            self.ex.set_sandbox_mode(True)

        log.info(f"Initialized {venue} client (testnet={testnet})")

    def exists_by_client_id(self, symbol: str, client_id: str) -> bool:
        """
        Check if order with client_id exists.

        Args:
            symbol: Trading pair
            client_id: Client order ID

        Returns:
            True if order exists, False otherwise

        Implementation note:
        - Binance: Use GET /api/v3/openOrders with origClientOrderId filter
        - Kraken: Use GET /0/private/OpenOrders with userref filter
        - Generic: Fetch all open orders and search by clientOrderId
        """
        try:
            # Binance-specific query by clientOrderId
            if self.venue == "binance":
                orders = self.ex.fetch_open_orders(symbol)
                return any(o.get("clientOrderId") == client_id for o in orders)

            # Generic fallback: Fetch all open orders
            orders = self.ex.fetch_open_orders(symbol)
            return any(o.get("clientOrderId") == client_id for o in orders)

        except Exception as e:
            log.warning(f"Failed to check order existence: {e}")
            return False  # Assume doesn't exist (safer to re-submit)

    @transient_retry
    def place_order(self, norm: dict, client_id: str) -> dict:
        """
        Place order idempotently.

        Args:
            norm: Normalized order (symbol, side, type, price, qty, tif)
            client_id: Client order ID

        Returns:
            Exchange order response

        Raises:
            ccxt.RateLimitExceeded: Rate limit hit (retried via @transient_retry)
            ccxt.NetworkError: Network error (retried)
            ccxt.ExchangeError: Exchange error (not retried)
        """
        try:
            if norm["order_type"] == "MARKET":
                return self.ex.create_order(
                    symbol=norm["symbol"],
                    type="market",
                    side=norm["side"].lower(),
                    amount=float(norm["qty"]),
                    params={"newClientOrderId": client_id},
                )
            else:
                return self.ex.create_order(
                    symbol=norm["symbol"],
                    type="limit",
                    side=norm["side"].lower(),
                    amount=float(norm["qty"]),
                    price=float(norm["price"]),
                    params={
                        "timeInForce": norm["tif"],
                        "newClientOrderId": client_id,
                    },
                )

        except ccxt.RateLimitExceeded as e:
            log.warning(f"Rate limit exceeded: {e}")
            raise Transient() from e  # Retry

        except ccxt.NetworkError as e:
            log.warning(f"Network error: {e}")
            raise Transient() from e  # Retry

        except ccxt.ExchangeError as e:
            log.error(f"Exchange error: {e}", norm=norm, client_id=client_id)
            raise  # Don't retry (client error)

    def fetch_balance(self) -> dict:
        """Fetch account balance."""
        return self.ex.fetch_balance()

    def fetch_ticker(self, symbol: str) -> dict:
        """Fetch ticker (bid, ask, last)."""
        return self.ex.fetch_ticker(symbol)

    def fetch_order(self, order_id: str, symbol: str) -> dict:
        """Fetch order by ID."""
        return self.ex.fetch_order(order_id, symbol)
```

**Binance Keep-Priority Amend** (`src/exec/binance_keep_priority.py`):

```python
"""Binance keep-priority amend endpoint."""

import httpx
import hmac
import hashlib
import time
from src.utils.retry import transient_retry, Transient
from src.utils.logger import setup_logger

log = setup_logger(__name__)


class BinanceAmend:
    """Binance keep-priority order amend."""

    def __init__(self, base_url: str, api_key: str, secret: str):
        """
        Initialize Binance amend client.

        Args:
            base_url: API base URL (e.g., https://testnet.binance.vision)
            api_key: Binance API key
            secret: Binance API secret
        """
        self.client = httpx.Client(base_url=base_url, timeout=5.0)
        self.key = api_key
        self.secret = secret

    def _sign(self, params: dict) -> str:
        """Generate HMAC-SHA256 signature."""
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hmac.new(
            self.secret.encode(), query_string.encode(), hashlib.sha256
        ).hexdigest()
        return signature

    @transient_retry
    def amend_keep_priority(
        self, symbol: str, order_id: int, new_qty: float
    ) -> dict:
        """
        Amend order quantity while keeping queue priority.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            order_id: Exchange order ID
            new_qty: New quantity (base asset)

        Returns:
            Exchange response

        Raises:
            httpx.HTTPStatusError: HTTP error
            Transient: Retryable error (5xx, network)

        Endpoint: PUT /api/v3/order/amend/keepPriority
        Docs: https://binance-docs.github.io/apidocs/spot/en/#amend-order-with-queue-priority
        """
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "quantity": new_qty,
            "timestamp": int(time.time() * 1000),
        }

        params["signature"] = self._sign(params)

        try:
            response = self.client.put(
                "/api/v3/order/amend/keepPriority",
                params=params,
                headers={"X-MBX-APIKEY": self.key},
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                log.warning(f"Server error (5xx): {e}")
                raise Transient() from e  # Retry

            log.error(f"Client error (4xx): {e}")
            raise  # Don't retry

        except httpx.NetworkError as e:
            log.warning(f"Network error: {e}")
            raise Transient() from e  # Retry
```

---

## Week 3-4: Data Pipeline

**Deliverables**:
1. Parquet Store (`src/data/store.py`) - 32h
2. Feature Engineering (`src/data/pipeline.py`) - 24h
3. Reference Price Cache (`src/data/reference_price.py`) - 8h
4. Event Bus (`src/streaming/nats_bus.py`) - 16h

Total: 80 hours

---

**(Continued in next file due to length constraints - see PHASE_15_RL_SPEC_PART2.md for Weeks 3-6)**

---

## Success Criteria & Validation

**Shadow Mode Validation** (Week 6):
- ✅ Shadow mode runs 7 days (no ACCEPTED orders placed, only logged)
- ✅ Zero rejection reason=FILTERS (filter validation 100% correct)
- ✅ Decision latency p95 <15ms (measured via Prometheus)
- ✅ FinRL policy outputs >1000 actions/day, acceptance rate >60%
- ✅ Audit trail logs 100% of decisions (action_id, policy_id, model_version, reason)

**Performance Benchmarks**:
- Decision throughput: >100 actions/second (single-threaded)
- Memory usage: <200 MB RSS (stable over 7 days)
- Idempotency: 0 duplicate orders (test with 10,000 identical actions)

**Integration Tests**:
- Test all 9 validation gates (policy, TTL, confidence, kill-switch, circuit, price band, filters, risk, submission)
- Test all 3 qty_modes (BASE, QUOTE, RISK)
- Test all 2 order_types (MARKET, LIMIT)
- Test multi-agent support (FinRL, TensorTrade mock agents)

**Documentation**:
- API reference (`docs/api/RL_ADAPTER.md`)
- Shadow mode tutorial (`docs/tutorials/SHADOW_MODE.md`)
- RL integration guide (`docs/guides/RL_INTEGRATION.md`)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-05
**Author**: Claude Code (Automated RL Specification)
