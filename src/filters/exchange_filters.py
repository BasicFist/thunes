"""
Exchange order filters for Binance.

Critical module to prevent -1013 errors by validating orders against
exchange rules (tickSize, stepSize, minNotional, etc.)
"""

from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Any

from binance.client import Client
from binance.exceptions import BinanceAPIException

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Cache TTL to prevent stale filter data (Audit Recommendation #4)
CACHE_TTL_SECONDS = 3600  # 1 hour


class ExchangeFilters:
    """Validate and adjust orders according to Binance exchange filters."""

    def __init__(self, client: Client, cache_ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        """
        Initialize exchange filters.

        Args:
            client: Authenticated Binance client
            cache_ttl_seconds: Cache TTL in seconds (default: 3600 = 1 hour)
        """
        self.client = client
        self._symbol_info_cache: dict[str, tuple[dict[str, Any], datetime]] = {}
        self.cache_ttl_seconds = cache_ttl_seconds
        logger.info(f"ExchangeFilters initialized (cache_ttl={cache_ttl_seconds}s)")

    def _get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """
        Get symbol information from exchange (with TTL-based caching).

        Cache entries are invalidated after cache_ttl_seconds to prevent stale data.
        This addresses Audit Recommendation #4: Exchange filter cache staleness.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Returns:
            Dictionary with symbol filters and info
        """
        now = datetime.utcnow()

        # Check if cache exists and is still valid
        if symbol in self._symbol_info_cache:
            cached_data, cached_time = self._symbol_info_cache[symbol]
            cache_age = (now - cached_time).total_seconds()

            if cache_age < self.cache_ttl_seconds:
                logger.debug(f"Using cached exchange info for {symbol} (age: {cache_age:.0f}s)")
                return cached_data
            else:
                logger.debug(f"Cache expired for {symbol} (age: {cache_age:.0f}s, ttl: {self.cache_ttl_seconds}s)")

        # Fetch fresh data from exchange
        try:
            exchange_info = self.client.get_exchange_info()
            symbol_data = next(
                (s for s in exchange_info["symbols"] if s["symbol"] == symbol),
                None,
            )

            if not symbol_data:
                raise ValueError(f"Symbol {symbol} not found in exchange info")

            self._symbol_info_cache[symbol] = (symbol_data, now)
            logger.debug(f"Cached fresh exchange info for {symbol}")

        except BinanceAPIException as e:
            logger.error(f"Failed to fetch exchange info: {e}")
            raise

        return symbol_data

    def _get_filter(self, symbol: str, filter_type: str) -> dict[str, Any] | None:
        """
        Get specific filter for a symbol.

        Args:
            symbol: Trading pair symbol
            filter_type: Filter type (e.g., "PRICE_FILTER", "LOT_SIZE")

        Returns:
            Filter dictionary or None if not found
        """
        symbol_info = self._get_symbol_info(symbol)
        return next(
            (f for f in symbol_info["filters"] if f["filterType"] == filter_type),
            None,
        )

    def get_tick_size(self, symbol: str) -> Decimal:
        """
        Get tick size (minimum price increment) for symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Tick size as Decimal
        """
        price_filter = self._get_filter(symbol, "PRICE_FILTER")
        if not price_filter:
            raise ValueError(f"PRICE_FILTER not found for {symbol}")

        tick_size = Decimal(price_filter["tickSize"])
        logger.debug(f"{symbol} tick size: {tick_size}")
        return tick_size

    def get_step_size(self, symbol: str) -> Decimal:
        """
        Get step size (minimum quantity increment) for symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Step size as Decimal
        """
        lot_size_filter = self._get_filter(symbol, "LOT_SIZE")
        if not lot_size_filter:
            raise ValueError(f"LOT_SIZE filter not found for {symbol}")

        step_size = Decimal(lot_size_filter["stepSize"])
        logger.debug(f"{symbol} step size: {step_size}")
        return step_size

    def get_min_notional(self, symbol: str) -> Decimal:
        """
        Get minimum notional value for orders.

        Args:
            symbol: Trading pair symbol

        Returns:
            Minimum notional as Decimal
        """
        # Try NOTIONAL filter first (newer)
        notional_filter = self._get_filter(symbol, "NOTIONAL")
        if notional_filter:
            min_notional = Decimal(notional_filter["minNotional"])
            logger.debug(f"{symbol} min notional: {min_notional}")
            return min_notional

        # Fallback to MIN_NOTIONAL (older)
        min_notional_filter = self._get_filter(symbol, "MIN_NOTIONAL")
        if min_notional_filter:
            min_notional = Decimal(min_notional_filter["minNotional"])
            logger.debug(f"{symbol} min notional: {min_notional}")
            return min_notional

        raise ValueError(f"No notional filter found for {symbol}")

    def round_price(self, symbol: str, price: float) -> Decimal:
        """
        Round price to comply with tick size.

        Args:
            symbol: Trading pair symbol
            price: Raw price value

        Returns:
            Rounded price as Decimal
        """
        tick_size = self.get_tick_size(symbol)
        price_decimal = Decimal(str(price))

        # Round down to nearest tick
        rounded = (price_decimal / tick_size).quantize(Decimal("1"), rounding=ROUND_DOWN)
        result = rounded * tick_size

        logger.debug(f"Rounded price {price} -> {result} (tick={tick_size})")
        return result

    def round_quantity(self, symbol: str, quantity: float) -> Decimal:
        """
        Round quantity to comply with step size.

        Args:
            symbol: Trading pair symbol
            quantity: Raw quantity value

        Returns:
            Rounded quantity as Decimal
        """
        step_size = self.get_step_size(symbol)
        qty_decimal = Decimal(str(quantity))

        # Round down to nearest step
        rounded = (qty_decimal / step_size).quantize(Decimal("1"), rounding=ROUND_DOWN)
        result = rounded * step_size

        logger.debug(f"Rounded quantity {quantity} -> {result} (step={step_size})")
        return result

    def validate_order(
        self,
        symbol: str,
        price: float | None = None,
        quantity: float | None = None,
        quote_qty: float | None = None,
    ) -> tuple[bool, str]:
        """
        Validate order parameters against exchange filters.

        Args:
            symbol: Trading pair symbol
            price: Order price (optional for market orders)
            quantity: Base asset quantity (optional if quote_qty provided)
            quote_qty: Quote asset quantity (optional if quantity provided)

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check minimum notional
            min_notional = self.get_min_notional(symbol)

            if quote_qty:
                # Market order by quote quantity
                if Decimal(str(quote_qty)) < min_notional:
                    return False, f"Quote quantity {quote_qty} below min notional {min_notional}"

            elif price and quantity:
                # Limit order or market by base quantity
                notional = Decimal(str(price)) * Decimal(str(quantity))
                if notional < min_notional:
                    return False, f"Notional {notional} below min notional {min_notional}"

            else:
                return False, "Must provide either quote_qty or both price and quantity"

            return True, "Order valid"

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False, str(e)

    def prepare_market_order(
        self,
        symbol: str,
        side: str,
        quote_qty: float,
    ) -> dict[str, Any]:
        """
        Prepare a validated market order (quote quantity).

        Args:
            symbol: Trading pair symbol
            side: "BUY" or "SELL"
            quote_qty: Amount in quote currency (e.g., USDT)

        Returns:
            Dictionary with order parameters

        Raises:
            ValueError: If order cannot be validated
        """
        # Validate
        is_valid, msg = self.validate_order(symbol, quote_qty=quote_qty)
        if not is_valid:
            raise ValueError(f"Order validation failed: {msg}")

        order_params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quoteOrderQty": str(quote_qty),
        }

        logger.info(f"Prepared market order: {order_params}")
        return order_params

    def prepare_market_sell(
        self,
        symbol: str,
        quantity: float,
    ) -> dict[str, Any]:
        """
        Prepare validated SELL order with base quantity.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            quantity: Amount in base currency (e.g., BTC)

        Returns:
            Dictionary with order parameters

        Raises:
            ValueError: If quantity violates stepSize or minimum notional
        """
        # Round quantity to stepSize
        rounded_qty = self.round_quantity(symbol, quantity)

        # Validate minimum notional (price * qty > min)
        # Note: For SELL we need current price to check notional
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            price = Decimal(ticker["price"])
            notional = price * rounded_qty
            min_notional = self.get_min_notional(symbol)

            if notional < min_notional:
                raise ValueError(
                    f"Notional {notional:.2f} below minimum {min_notional:.2f} "
                    f"(price={price}, qty={rounded_qty})"
                )

        except BinanceAPIException as e:
            logger.error(f"Failed to validate SELL order: {e}")
            raise

        order_params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": str(rounded_qty),
        }

        logger.info(f"Prepared SELL order: {order_params}")
        return order_params

    def clear_cache(self, symbol: str | None = None) -> None:
        """
        Clear exchange filter cache.

        Useful for testing or forcing cache refresh after exchange filter updates.

        Args:
            symbol: Specific symbol to clear, or None to clear all cache
        """
        if symbol:
            if symbol in self._symbol_info_cache:
                del self._symbol_info_cache[symbol]
                logger.info(f"Cleared cache for {symbol}")
        else:
            cache_size = len(self._symbol_info_cache)
            self._symbol_info_cache.clear()
            logger.info(f"Cleared entire cache ({cache_size} symbols)")

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary with cache metrics
        """
        now = datetime.utcnow()
        stats = {
            "cache_size": len(self._symbol_info_cache),
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "symbols_cached": list(self._symbol_info_cache.keys()),
            "cache_ages_seconds": {},
        }

        for symbol, (_, cached_time) in self._symbol_info_cache.items():
            age = (now - cached_time).total_seconds()
            stats["cache_ages_seconds"][symbol] = round(age, 1)

        return stats
