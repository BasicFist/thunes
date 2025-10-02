"""Pydantic validation models for trading data structures."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderSide(str, Enum):
    """Order side enumeration."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class OrderStatus(str, Enum):
    """Order status enumeration."""

    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderRequest(BaseModel):
    """Represents an order request before submission."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    symbol: str = Field(..., min_length=1, description="Trading pair (e.g., BTCUSDT)")
    side: OrderSide = Field(..., description="Order side (BUY or SELL)")
    order_type: OrderType = Field(..., description="Order type")
    quantity: Optional[Decimal] = Field(None, gt=0, description="Order quantity in base currency")
    quote_quantity: Optional[Decimal] = Field(
        None, gt=0, description="Order quantity in quote currency"
    )
    price: Optional[Decimal] = Field(None, gt=0, description="Limit price")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="Stop trigger price")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format."""
        if not v.isupper():
            raise ValueError("Symbol must be uppercase")
        if len(v) < 6:
            raise ValueError("Symbol too short (min 6 chars)")
        return v

    @field_validator("quantity", "quote_quantity", "price", "stop_price", mode="before")
    @classmethod
    def validate_positive_decimal(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure decimal values are positive if provided."""
        if v is not None and v <= 0:
            raise ValueError("Value must be positive")
        return v

    def model_post_init(self, __context) -> None:
        """Post-initialization validation."""
        # Either quantity or quote_quantity must be specified for MARKET orders
        if self.order_type == OrderType.MARKET:
            if self.quantity is None and self.quote_quantity is None:
                raise ValueError("MARKET order requires quantity or quote_quantity")

        # LIMIT orders require price
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("LIMIT order requires price")


class OrderResponse(BaseModel):
    """Represents an order response from the exchange."""

    model_config = ConfigDict(frozen=True, validate_assignment=True)

    order_id: int = Field(..., description="Exchange order ID")
    symbol: str = Field(..., description="Trading pair")
    side: OrderSide = Field(..., description="Order side")
    order_type: OrderType = Field(..., description="Order type")
    status: OrderStatus = Field(..., description="Order status")
    quantity: Decimal = Field(..., gt=0, description="Ordered quantity")
    executed_qty: Decimal = Field(..., ge=0, description="Executed quantity")
    cumulative_quote_qty: Decimal = Field(..., ge=0, description="Cumulative quote quantity")
    price: Optional[Decimal] = Field(None, description="Order price")
    transact_time: datetime = Field(..., description="Transaction timestamp")

    @property
    def average_fill_price(self) -> Optional[Decimal]:
        """Calculate average fill price."""
        if self.executed_qty > 0 and self.cumulative_quote_qty > 0:
            return self.cumulative_quote_qty / self.executed_qty
        return None

    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.status == OrderStatus.FILLED

    @property
    def fill_ratio(self) -> Decimal:
        """Calculate fill ratio (0.0 to 1.0)."""
        if self.quantity > 0:
            return self.executed_qty / self.quantity
        return Decimal("0.0")


class PositionModel(BaseModel):
    """Represents a trading position (Pydantic validation)."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    symbol: str = Field(..., min_length=1, description="Trading pair")
    quantity: Decimal = Field(..., gt=0, description="Position size")
    entry_price: Decimal = Field(..., gt=0, description="Entry price")
    entry_time: datetime = Field(..., description="Entry timestamp")
    exit_price: Optional[Decimal] = Field(None, gt=0, description="Exit price")
    exit_time: Optional[datetime] = Field(None, description="Exit timestamp")
    pnl: Optional[Decimal] = Field(None, description="Realized PnL")
    status: str = Field(..., description="Position status (OPEN or CLOSED)")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate position status."""
        if v not in ("OPEN", "CLOSED"):
            raise ValueError("Status must be OPEN or CLOSED")
        return v

    @property
    def is_open(self) -> bool:
        """Check if position is open."""
        return self.status == "OPEN"

    @property
    def is_closed(self) -> bool:
        """Check if position is closed."""
        return self.status == "CLOSED"

    def calculate_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """
        Calculate unrealized PnL.

        Args:
            current_price: Current market price

        Returns:
            Unrealized PnL
        """
        if self.is_open:
            return (current_price - self.entry_price) * self.quantity
        return Decimal("0.0")


class TradeModel(BaseModel):
    """Represents a completed trade (entry + exit)."""

    model_config = ConfigDict(frozen=True, validate_assignment=True)

    symbol: str = Field(..., description="Trading pair")
    entry_order_id: int = Field(..., description="Entry order ID")
    exit_order_id: int = Field(..., description="Exit order ID")
    quantity: Decimal = Field(..., gt=0, description="Trade quantity")
    entry_price: Decimal = Field(..., gt=0, description="Entry price")
    exit_price: Decimal = Field(..., gt=0, description="Exit price")
    entry_time: datetime = Field(..., description="Entry timestamp")
    exit_time: datetime = Field(..., description="Exit timestamp")
    pnl: Decimal = Field(..., description="Realized PnL")
    pnl_percent: Decimal = Field(..., description="PnL percentage")
    fees: Decimal = Field(..., ge=0, description="Total fees paid")

    @property
    def duration_seconds(self) -> float:
        """Calculate trade duration in seconds."""
        return (self.exit_time - self.entry_time).total_seconds()

    @property
    def duration_hours(self) -> float:
        """Calculate trade duration in hours."""
        return self.duration_seconds / 3600

    @property
    def is_profitable(self) -> bool:
        """Check if trade was profitable."""
        return self.pnl > 0

    @property
    def net_pnl(self) -> Decimal:
        """Calculate net PnL after fees."""
        return self.pnl - self.fees

    @property
    def return_on_investment(self) -> Decimal:
        """Calculate ROI."""
        cost_basis = self.entry_price * self.quantity
        if cost_basis > 0:
            return (self.net_pnl / cost_basis) * Decimal("100")
        return Decimal("0.0")


class BalanceModel(BaseModel):
    """Represents account balance for an asset."""

    model_config = ConfigDict(frozen=True, validate_assignment=True)

    asset: str = Field(..., min_length=1, description="Asset symbol")
    free: Decimal = Field(..., ge=0, description="Available balance")
    locked: Decimal = Field(..., ge=0, description="Locked balance")

    @property
    def total(self) -> Decimal:
        """Calculate total balance."""
        return self.free + self.locked


class MarketDataSnapshot(BaseModel):
    """Represents a market data snapshot."""

    model_config = ConfigDict(frozen=True, validate_assignment=True)

    symbol: str = Field(..., description="Trading pair")
    timestamp: datetime = Field(..., description="Snapshot timestamp")
    bid_price: Decimal = Field(..., gt=0, description="Best bid price")
    ask_price: Decimal = Field(..., gt=0, description="Best ask price")
    last_price: Decimal = Field(..., gt=0, description="Last traded price")
    volume_24h: Decimal = Field(..., ge=0, description="24h volume")

    @property
    def spread(self) -> Decimal:
        """Calculate bid-ask spread."""
        return self.ask_price - self.bid_price

    @property
    def spread_bps(self) -> Decimal:
        """Calculate spread in basis points."""
        if self.bid_price > 0:
            return (self.spread / self.bid_price) * Decimal("10000")
        return Decimal("0.0")

    @property
    def mid_price(self) -> Decimal:
        """Calculate mid-price."""
        return (self.bid_price + self.ask_price) / Decimal("2")
