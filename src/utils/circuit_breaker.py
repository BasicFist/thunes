"""Circuit breaker pattern for API resilience."""

import functools
from collections.abc import Callable
from typing import TypeVar

import pybreaker
from binance.exceptions import BinanceAPIException

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Type variable for generic function return type
T = TypeVar("T")


# Custom listener for circuit breaker events
class CircuitBreakerListener(pybreaker.CircuitBreakerListener):
    """Log circuit breaker state transitions."""

    def state_change(self, cb: pybreaker.CircuitBreaker, old_state, new_state) -> None:
        """Log state changes."""
        logger.warning(
            f"Circuit breaker '{cb.name}' state changed: {old_state.name} -> {new_state.name}"
        )

    def failure(self, cb: pybreaker.CircuitBreaker, exc: Exception) -> None:
        """Log failures."""
        logger.error(
            f"Circuit breaker '{cb.name}' recorded failure: {exc.__class__.__name__}: {exc}"
        )

    def success(self, cb: pybreaker.CircuitBreaker) -> None:
        """Log successful calls."""
        logger.debug(f"Circuit breaker '{cb.name}' recorded success")


# Define exceptions that should trigger the circuit breaker
# HTTP 5xx errors and connection errors should trip the breaker
# HTTP 4xx errors (client errors) should not trip the breaker
def is_server_error(exception: Exception) -> bool:
    """
    Determine if exception is a server error that should trip the circuit breaker.

    Args:
        exception: Exception to check

    Returns:
        True if exception should trip the breaker
    """
    # Binance API exceptions
    if isinstance(exception, BinanceAPIException):
        status_code = exception.status_code
        # 5xx server errors should trip the breaker
        # 429 (rate limit) should trip the breaker
        # 418 (IP ban) should trip the breaker
        return status_code >= 500 or status_code in (429, 418)

    # Connection errors, timeout errors
    if isinstance(exception, ConnectionError | TimeoutError | OSError):
        return True

    # By default, don't trip the breaker for unknown exceptions
    return False


# Create circuit breakers for different services
# Note: Trips on all exceptions for maximum safety
# TODO: Add selective exception handling with exclude parameter
binance_api_breaker = pybreaker.CircuitBreaker(
    fail_max=5,  # Open circuit after 5 consecutive failures
    reset_timeout=60,  # Keep circuit open for 60 seconds
    name="BinanceAPI",
    listeners=[CircuitBreakerListener()],
)


def with_circuit_breaker(
    circuit_breaker: pybreaker.CircuitBreaker = binance_api_breaker,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to apply circuit breaker pattern to a function.

    Args:
        circuit_breaker: CircuitBreaker instance to use

    Returns:
        Decorated function

    Usage:
        @with_circuit_breaker()
        def api_call():
            return client.get_account()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return circuit_breaker.call(func, *args, **kwargs)
            except pybreaker.CircuitBreakerError as e:
                logger.error(
                    f"Circuit breaker '{circuit_breaker.name}' is OPEN - rejecting call to {func.__name__}"
                )
                raise RuntimeError(
                    f"Service unavailable: {circuit_breaker.name} circuit is open"
                ) from e

        return wrapper

    return decorator


class CircuitBreakerMonitor:
    """Monitor circuit breaker states and metrics."""

    def __init__(self, breakers: list[pybreaker.CircuitBreaker]) -> None:
        """
        Initialize monitor.

        Args:
            breakers: List of circuit breakers to monitor
        """
        self.breakers = breakers

    def get_status(self) -> dict[str, dict]:
        """
        Get status of all circuit breakers.

        Returns:
            Dictionary with breaker name -> status info
        """
        status = {}
        for breaker in self.breakers:
            # current_state is a string in pybreaker v1.4.1, not an enum
            state = (
                breaker.current_state
                if isinstance(breaker.current_state, str)
                else str(breaker.current_state)
            )
            status[breaker.name] = {
                "state": state,
                "fail_counter": breaker.fail_counter,
                "fail_max": breaker.fail_max,
                "reset_timeout": getattr(
                    breaker, "reset_timeout", 60
                ),  # timeout_duration -> reset_timeout
            }
        return status

    def log_status(self) -> None:
        """Log current status of all breakers."""
        status = self.get_status()
        for name, info in status.items():
            logger.info(
                f"Circuit Breaker '{name}': state={info['state']}, "
                f"failures={info['fail_counter']}/{info['fail_max']}"
            )

    def is_any_open(self) -> bool:
        """Check if any circuit breaker is open."""
        return any(breaker.current_state == pybreaker.STATE_OPEN for breaker in self.breakers)

    def reset_all(self) -> None:
        """Reset all circuit breakers to closed state."""
        for breaker in self.breakers:
            try:
                breaker.close()
                logger.info(f"Reset circuit breaker: {breaker.name}")
            except Exception as e:
                logger.error(f"Failed to reset breaker {breaker.name}: {e}")


# Global monitor instance
circuit_monitor = CircuitBreakerMonitor([binance_api_breaker])
