"""
Slippage Tracking and Modeling for Order Execution Analysis.

Tracks the difference between expected and actual fill prices to:
1. Identify execution quality issues
2. Model realistic slippage for backtesting
3. Optimize order timing
4. Detect market impact

Critical for profitability: Even 0.1% slippage costs 20% of a 0.5% edge!
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class SlippageEvent:
    """Record of a single slippage event."""

    timestamp: datetime
    symbol: str
    side: str  # BUY or SELL
    expected_price: Decimal  # Signal/market price
    actual_price: Decimal  # Fill price
    quantity: Decimal
    slippage_bps: float  # Basis points (1bps = 0.01%)
    slippage_usdt: float  # Dollar value of slippage
    order_type: str  # MARKET, LIMIT, etc.
    volatility: Optional[float] = None  # Market volatility at time
    spread_bps: Optional[float] = None  # Bid-ask spread


class SlippageTracker:
    """
    Track and analyze order execution slippage.

    Slippage = (Actual Fill Price - Expected Price) / Expected Price
    - Positive slippage = worse than expected (cost)
    - Negative slippage = better than expected (improvement)
    """

    def __init__(self, history_file: Path = Path("logs/slippage_history.csv")):
        """
        Initialize slippage tracker.

        Args:
            history_file: Path to CSV file for persistent storage
        """
        self.history_file = history_file
        self.events: List[SlippageEvent] = []

        # Load existing history if available
        self._load_history()

        logger.info(f"SlippageTracker initialized: {len(self.events)} historical events")

    def _load_history(self) -> None:
        """Load slippage history from CSV."""
        if not self.history_file.exists():
            logger.info("No slippage history file found, starting fresh")
            return

        try:
            df = pd.read_csv(self.history_file)
            self.events = [
                SlippageEvent(
                    timestamp=pd.to_datetime(row["timestamp"]),
                    symbol=row["symbol"],
                    side=row["side"],
                    expected_price=Decimal(str(row["expected_price"])),
                    actual_price=Decimal(str(row["actual_price"])),
                    quantity=Decimal(str(row["quantity"])),
                    slippage_bps=row["slippage_bps"],
                    slippage_usdt=row["slippage_usdt"],
                    order_type=row.get("order_type", "MARKET"),
                    volatility=row.get("volatility"),
                    spread_bps=row.get("spread_bps"),
                )
                for _, row in df.iterrows()
            ]
            logger.info(f"Loaded {len(self.events)} slippage events from {self.history_file}")
        except Exception as e:
            logger.error(f"Failed to load slippage history: {e}")
            self.events = []

    def _save_history(self) -> None:
        """Save slippage history to CSV."""
        if not self.events:
            return

        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            df = pd.DataFrame([
                {
                    "timestamp": event.timestamp.isoformat(),
                    "symbol": event.symbol,
                    "side": event.side,
                    "expected_price": float(event.expected_price),
                    "actual_price": float(event.actual_price),
                    "quantity": float(event.quantity),
                    "slippage_bps": event.slippage_bps,
                    "slippage_usdt": event.slippage_usdt,
                    "order_type": event.order_type,
                    "volatility": event.volatility,
                    "spread_bps": event.spread_bps,
                }
                for event in self.events
            ])

            df.to_csv(self.history_file, index=False)
            logger.debug(f"Saved {len(self.events)} slippage events to {self.history_file}")
        except Exception as e:
            logger.error(f"Failed to save slippage history: {e}")

    def record_fill(
        self,
        symbol: str,
        side: str,
        expected_price: float,
        actual_price: float,
        quantity: float,
        order_type: str = "MARKET",
        volatility: Optional[float] = None,
        spread_bps: Optional[float] = None,
    ) -> SlippageEvent:
        """
        Record an order fill and calculate slippage.

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            expected_price: Expected fill price (e.g., mid-market price)
            actual_price: Actual fill price
            quantity: Order quantity
            order_type: Order type (MARKET, LIMIT, etc.)
            volatility: Market volatility at execution (optional)
            spread_bps: Bid-ask spread in basis points (optional)

        Returns:
            SlippageEvent with calculated slippage
        """
        expected = Decimal(str(expected_price))
        actual = Decimal(str(actual_price))
        qty = Decimal(str(quantity))

        # Calculate slippage
        # For BUY: positive slippage = paid more than expected (bad)
        # For SELL: positive slippage = received less than expected (bad)
        if side == "BUY":
            slippage = actual - expected
        else:  # SELL
            slippage = expected - actual

        # Convert to basis points (1bps = 0.01%)
        slippage_bps = float((slippage / expected) * 10000)

        # Convert to dollar value
        slippage_usdt = float(abs(slippage) * qty)

        event = SlippageEvent(
            timestamp=datetime.utcnow(),
            symbol=symbol,
            side=side,
            expected_price=expected,
            actual_price=actual,
            quantity=qty,
            slippage_bps=slippage_bps,
            slippage_usdt=slippage_usdt,
            order_type=order_type,
            volatility=volatility,
            spread_bps=spread_bps,
        )

        self.events.append(event)
        self._save_history()

        logger.info(
            f"Slippage recorded: {symbol} {side} | "
            f"Expected: {expected_price:.2f}, Actual: {actual_price:.2f} | "
            f"Slippage: {slippage_bps:+.2f} bps ({slippage_usdt:.4f} USDT)"
        )

        return event

    def get_average_slippage(
        self,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        lookback_hours: int = 24,
    ) -> float:
        """
        Calculate average slippage in basis points.

        Args:
            symbol: Filter by symbol (None = all symbols)
            side: Filter by side (None = both sides)
            lookback_hours: Hours to look back (default: 24)

        Returns:
            Average slippage in basis points
        """
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        filtered = [
            e for e in self.events
            if e.timestamp >= cutoff
            and (symbol is None or e.symbol == symbol)
            and (side is None or e.side == side)
        ]

        if not filtered:
            return 0.0

        avg_slippage = sum(e.slippage_bps for e in filtered) / len(filtered)
        return avg_slippage

    def get_slippage_stats(
        self,
        symbol: Optional[str] = None,
        lookback_hours: int = 168,  # 1 week
    ) -> dict:
        """
        Get comprehensive slippage statistics.

        Args:
            symbol: Filter by symbol (None = all symbols)
            lookback_hours: Hours to look back

        Returns:
            Dictionary with slippage statistics
        """
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        filtered = [
            e for e in self.events
            if e.timestamp >= cutoff
            and (symbol is None or e.symbol == symbol)
        ]

        if not filtered:
            return {
                "total_events": 0,
                "avg_slippage_bps": 0.0,
                "median_slippage_bps": 0.0,
                "std_slippage_bps": 0.0,
                "max_slippage_bps": 0.0,
                "total_cost_usdt": 0.0,
                "avg_cost_usdt": 0.0,
            }

        slippages = [e.slippage_bps for e in filtered]
        costs = [e.slippage_usdt for e in filtered]

        return {
            "total_events": len(filtered),
            "avg_slippage_bps": sum(slippages) / len(slippages),
            "median_slippage_bps": pd.Series(slippages).median(),
            "std_slippage_bps": pd.Series(slippages).std(),
            "max_slippage_bps": max(slippages),
            "min_slippage_bps": min(slippages),
            "total_cost_usdt": sum(costs),
            "avg_cost_usdt": sum(costs) / len(costs),
            "buy_events": len([e for e in filtered if e.side == "BUY"]),
            "sell_events": len([e for e in filtered if e.side == "SELL"]),
        }

    def estimate_slippage(
        self,
        symbol: str,
        side: str,
        quantity: float,
        current_volatility: Optional[float] = None,
    ) -> float:
        """
        Estimate expected slippage for upcoming order.

        Uses historical data to predict slippage based on:
        - Symbol
        - Side (BUY/SELL)
        - Quantity (larger orders = more slippage)
        - Volatility (higher vol = more slippage)

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Order quantity
            current_volatility: Current market volatility (optional)

        Returns:
            Estimated slippage in basis points
        """
        # Get recent similar orders
        recent = [
            e for e in self.events[-100:]  # Last 100 events
            if e.symbol == symbol and e.side == side
        ]

        if not recent:
            # Fallback: Conservative estimate based on order type
            # Market orders: ~5-10 bps slippage typical for crypto
            logger.warning(f"No historical data for {symbol} {side}, using default estimate")
            return 8.0  # 8 bps = 0.08% (conservative)

        # Base estimate from historical average
        base_slippage = sum(e.slippage_bps for e in recent) / len(recent)

        # Adjust for quantity (larger orders = more impact)
        avg_quantity = sum(float(e.quantity) for e in recent) / len(recent)
        quantity_multiplier = 1.0 + (quantity / avg_quantity - 1) * 0.3  # 30% impact factor

        # Adjust for volatility if available
        vol_multiplier = 1.0
        if current_volatility is not None and any(e.volatility for e in recent):
            vol_events = [e for e in recent if e.volatility is not None]
            if vol_events:
                avg_vol = sum(e.volatility for e in vol_events) / len(vol_events)
                vol_multiplier = 1.0 + (current_volatility / avg_vol - 1) * 0.5  # 50% vol impact

        estimated_slippage = base_slippage * quantity_multiplier * vol_multiplier

        logger.info(
            f"Slippage estimate for {symbol} {side}: {estimated_slippage:.2f} bps "
            f"(base: {base_slippage:.2f}, qty_mult: {quantity_multiplier:.2f}, "
            f"vol_mult: {vol_multiplier:.2f})"
        )

        return estimated_slippage

    def get_execution_quality_score(self, lookback_hours: int = 24) -> float:
        """
        Calculate execution quality score (0-100).

        100 = excellent (low slippage)
        0 = poor (high slippage)

        Args:
            lookback_hours: Hours to analyze

        Returns:
            Quality score (0-100)
        """
        stats = self.get_slippage_stats(lookback_hours=lookback_hours)

        if stats["total_events"] == 0:
            return 100.0  # No data = assume good (neutral)

        avg_slippage = abs(stats["avg_slippage_bps"])

        # Scoring:
        # 0-2 bps = 100 (excellent)
        # 2-5 bps = 90-100 (very good)
        # 5-10 bps = 70-90 (good)
        # 10-20 bps = 40-70 (fair)
        # 20+ bps = 0-40 (poor)

        if avg_slippage <= 2:
            score = 100
        elif avg_slippage <= 5:
            score = 100 - (avg_slippage - 2) * 3.33  # Linear from 100 to 90
        elif avg_slippage <= 10:
            score = 90 - (avg_slippage - 5) * 4  # Linear from 90 to 70
        elif avg_slippage <= 20:
            score = 70 - (avg_slippage - 10) * 3  # Linear from 70 to 40
        else:
            score = max(0, 40 - (avg_slippage - 20) * 2)  # Decay to 0

        return round(score, 1)
