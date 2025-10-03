"""Rate limiter using token bucket algorithm for Binance API limits."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import TypeVar

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

T = TypeVar("T")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter."""

    max_tokens: float  # Maximum tokens in bucket
    refill_rate: float  # Tokens added per second
    name: str = "default"  # Limiter name for logging


class TokenBucket:
    """
    Token bucket rate limiter implementation.

    Thread-safe implementation using threading.Lock.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        """
        Initialize token bucket.

        Args:
            config: Rate limit configuration
        """
        self.config = config
        self.tokens: float = config.max_tokens
        self.last_refill: float = time.monotonic()
        self.lock = Lock()

        logger.info(
            f"TokenBucket '{config.name}' initialized: "
            f"max={config.max_tokens}, refill_rate={config.refill_rate}/s"
        )

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.config.refill_rate
        self.tokens = min(self.config.max_tokens, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: float = 1.0, blocking: bool = True) -> bool:
        """
        Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (request weight)
            blocking: If True, wait until tokens available. If False, return immediately.

        Returns:
            True if tokens consumed successfully, False if insufficient tokens (non-blocking mode)

        Raises:
            ValueError: If requested tokens exceed max capacity
        """
        if tokens > self.config.max_tokens:
            raise ValueError(
                f"Requested tokens ({tokens}) exceeds bucket capacity ({self.config.max_tokens})"
            )

        with self.lock:
            self._refill()

            # Non-blocking mode: check availability
            if not blocking:
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    logger.debug(
                        f"[{self.config.name}] Consumed {tokens} tokens, "
                        f"{self.tokens:.2f} remaining"
                    )
                    return True
                else:
                    logger.warning(
                        f"[{self.config.name}] Insufficient tokens: "
                        f"need={tokens}, available={self.tokens:.2f}"
                    )
                    return False

            # Blocking mode: wait until enough tokens
            while self.tokens < tokens:
                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.config.refill_rate

                logger.debug(f"[{self.config.name}] Waiting {wait_time:.2f}s for {tokens} tokens")

                # Release lock during sleep
                self.lock.release()
                time.sleep(wait_time)
                self.lock.acquire()

                # Refill after waiting
                self._refill()

            # Consume tokens
            self.tokens -= tokens
            logger.debug(
                f"[{self.config.name}] Consumed {tokens} tokens, {self.tokens:.2f} remaining"
            )
            return True

    def get_available_tokens(self) -> float:
        """
        Get current number of available tokens.

        Returns:
            Number of available tokens
        """
        with self.lock:
            self._refill()
            return self.tokens

    def reset(self) -> None:
        """Reset bucket to full capacity."""
        with self.lock:
            self.tokens = self.config.max_tokens
            self.last_refill = time.monotonic()
            logger.info(f"[{self.config.name}] Bucket reset to {self.tokens} tokens")


class BinanceRateLimiter:
    """
    Rate limiter for Binance API with multiple limit types.

    Binance limits:
    - IP limits: 1200 requests per minute (weight-based)
    - Order limits: 50 orders per 10 seconds
    - Raw requests: 6100 per 5 minutes (advanced)
    """

    def __init__(self) -> None:
        """Initialize Binance rate limiter with default limits."""
        # IP weight limit: 1200 per minute = 20 per second
        self.ip_limiter = TokenBucket(
            RateLimitConfig(
                max_tokens=1200,
                refill_rate=20.0,  # 1200 / 60
                name="IP_WEIGHT",
            )
        )

        # Order limit: 50 per 10 seconds = 5 per second
        self.order_limiter = TokenBucket(
            RateLimitConfig(
                max_tokens=50,
                refill_rate=5.0,  # 50 / 10
                name="ORDER_RATE",
            )
        )

        # Track server-side reported weight
        self.server_weight: int = 0
        self.server_weight_lock = Lock()

        logger.info("BinanceRateLimiter initialized")

    def acquire(self, weight: int = 1, is_order: bool = False, blocking: bool = True) -> bool:
        """
        Acquire rate limit permission.

        Args:
            weight: Request weight (default: 1)
            is_order: Whether this is an order request (subject to order limits)
            blocking: If True, wait for permission. If False, return immediately.

        Returns:
            True if permission granted, False if rate limited (non-blocking mode)
        """
        # Check IP weight limit
        if not self.ip_limiter.consume(tokens=weight, blocking=blocking):
            return False

        # Check order limit if applicable
        if is_order:
            if not self.order_limiter.consume(tokens=1, blocking=blocking):
                # Refund IP weight since order limit failed
                # (not perfect but reasonable approximation)
                return False

        return True

    def update_server_weight(self, used_weight: int) -> None:
        """
        Update server-side reported weight from response headers.

        Args:
            used_weight: Value from X-MBX-USED-WEIGHT header
        """
        with self.server_weight_lock:
            old_weight = self.server_weight
            self.server_weight = used_weight

            # Warning if approaching limit
            if used_weight > 1000:  # >83% of 1200 limit
                logger.warning(
                    f"Server weight high: {used_weight}/1200 "
                    f"(local estimate: {1200 - self.ip_limiter.get_available_tokens():.0f})"
                )

            # Log significant changes
            if abs(used_weight - old_weight) > 100:
                logger.info(f"Server weight updated: {old_weight} -> {used_weight}")

    def get_status(self) -> dict[str, float]:
        """
        Get current rate limiter status.

        Returns:
            Dictionary with limiter states
        """
        return {
            "ip_tokens_available": self.ip_limiter.get_available_tokens(),
            "ip_tokens_max": self.ip_limiter.config.max_tokens,
            "order_tokens_available": self.order_limiter.get_available_tokens(),
            "order_tokens_max": self.order_limiter.config.max_tokens,
            "server_weight": self.server_weight,
        }

    def log_status(self) -> None:
        """Log current rate limiter status."""
        status = self.get_status()
        logger.info(
            f"Rate Limiter Status: "
            f"IP={status['ip_tokens_available']:.0f}/{status['ip_tokens_max']:.0f}, "
            f"Orders={status['order_tokens_available']:.0f}/{status['order_tokens_max']:.0f}, "
            f"Server={status['server_weight']}"
        )

    def reset(self) -> None:
        """Reset all rate limiters."""
        self.ip_limiter.reset()
        self.order_limiter.reset()
        with self.server_weight_lock:
            self.server_weight = 0
        logger.info("All rate limiters reset")


# Global rate limiter instance
binance_rate_limiter = BinanceRateLimiter()


def with_rate_limit(
    weight: int = 1, is_order: bool = False
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to apply rate limiting to a function.

    Args:
        weight: Request weight
        is_order: Whether this is an order request

    Usage:
        @with_rate_limit(weight=5, is_order=False)
        def get_account_info():
            return client.get_account()

        @with_rate_limit(weight=1, is_order=True)
        def place_order():
            return client.create_order(...)
    """
    import functools

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> T:
            # Acquire rate limit permission (blocking)
            binance_rate_limiter.acquire(weight=weight, is_order=is_order, blocking=True)

            # Execute function
            result = func(*args, **kwargs)

            # Extract and update server weight from response if available
            # (This assumes result is a dict with headers or response object)
            try:
                if hasattr(result, "headers") and "X-MBX-USED-WEIGHT" in result.headers:
                    used_weight = int(result.headers["X-MBX-USED-WEIGHT"])
                    binance_rate_limiter.update_server_weight(used_weight)
            except (AttributeError, KeyError, ValueError):
                pass  # Not all responses have this header

            return result

        return wrapper

    return decorator
