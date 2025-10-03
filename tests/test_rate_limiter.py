"""Tests for rate limiter functionality."""

import time

import pytest

from src.utils.rate_limiter import (
    BinanceRateLimiter,
    RateLimitConfig,
    TokenBucket,
    with_rate_limit,
)


class TestTokenBucket:
    """Tests for TokenBucket implementation."""

    def test_initialization(self) -> None:
        """Test token bucket initialization."""
        config = RateLimitConfig(max_tokens=100, refill_rate=10, name="test")
        bucket = TokenBucket(config)

        assert bucket.tokens == 100
        assert bucket.config.max_tokens == 100
        assert bucket.config.refill_rate == 10

    def test_consume_tokens_success(self) -> None:
        """Test successful token consumption."""
        config = RateLimitConfig(max_tokens=100, refill_rate=10, name="test")
        bucket = TokenBucket(config)

        result = bucket.consume(tokens=50, blocking=False)

        assert result is True
        assert bucket.tokens == 50

    def test_consume_tokens_insufficient_nonblocking(self) -> None:
        """Test token consumption fails when insufficient (non-blocking)."""
        config = RateLimitConfig(max_tokens=100, refill_rate=10, name="test")
        bucket = TokenBucket(config)

        # Consume most tokens
        bucket.consume(tokens=90, blocking=False)

        # Try to consume more than available
        result = bucket.consume(tokens=20, blocking=False)

        assert result is False
        # Allow for small floating-point drift from time-based refill (~0.001 tokens)
        assert pytest.approx(bucket.tokens, abs=0.01) == 10

    def test_consume_tokens_blocking_waits(self) -> None:
        """Test that blocking mode waits for tokens."""
        config = RateLimitConfig(max_tokens=10, refill_rate=10, name="test")
        bucket = TokenBucket(config)

        # Consume all tokens
        bucket.consume(tokens=10, blocking=False)
        assert bucket.tokens == 0

        # Consume 5 more tokens (blocking) - should wait ~0.5 seconds
        start = time.monotonic()
        result = bucket.consume(tokens=5, blocking=True)
        elapsed = time.monotonic() - start

        assert result is True
        assert elapsed >= 0.4  # Allow some tolerance
        assert elapsed < 0.7

    def test_token_refill(self) -> None:
        """Test that tokens refill over time."""
        config = RateLimitConfig(max_tokens=100, refill_rate=100, name="test")
        bucket = TokenBucket(config)

        # Consume tokens
        bucket.consume(tokens=50, blocking=False)
        assert bucket.tokens == 50

        # Wait for refill (0.3 seconds = 30 tokens at 100/sec)
        time.sleep(0.3)

        # Check available tokens
        available = bucket.get_available_tokens()
        assert available >= 79  # 50 + 30 = 80, allow some tolerance
        assert available <= 100  # Capped at max

    def test_refill_capped_at_max(self) -> None:
        """Test that refill doesn't exceed max capacity."""
        config = RateLimitConfig(max_tokens=100, refill_rate=100, name="test")
        bucket = TokenBucket(config)

        # Wait for potential refill
        time.sleep(0.5)

        # Should be capped at 100
        available = bucket.get_available_tokens()
        assert available == 100

    def test_consume_exceeds_capacity_raises_error(self) -> None:
        """Test that requesting more than capacity raises error."""
        config = RateLimitConfig(max_tokens=100, refill_rate=10, name="test")
        bucket = TokenBucket(config)

        with pytest.raises(ValueError, match="exceeds bucket capacity"):
            bucket.consume(tokens=200, blocking=False)

    def test_reset(self) -> None:
        """Test bucket reset."""
        config = RateLimitConfig(max_tokens=100, refill_rate=10, name="test")
        bucket = TokenBucket(config)

        # Consume tokens
        bucket.consume(tokens=80, blocking=False)
        assert bucket.tokens == 20

        # Reset
        bucket.reset()

        assert bucket.tokens == 100


class TestBinanceRateLimiter:
    """Tests for BinanceRateLimiter."""

    def test_initialization(self) -> None:
        """Test rate limiter initialization."""
        limiter = BinanceRateLimiter()

        assert limiter.ip_limiter.config.max_tokens == 1200
        assert limiter.ip_limiter.config.refill_rate == 20.0
        assert limiter.order_limiter.config.max_tokens == 50
        assert limiter.order_limiter.config.refill_rate == 5.0

    def test_acquire_ip_weight(self) -> None:
        """Test acquiring IP weight permission."""
        limiter = BinanceRateLimiter()

        # Acquire with weight=5
        result = limiter.acquire(weight=5, is_order=False, blocking=False)

        assert result is True
        available = limiter.ip_limiter.get_available_tokens()
        # Should be ~1195 (1200 - 5), allow small drift from refill
        assert 1194 <= available <= 1196

    def test_acquire_order_permission(self) -> None:
        """Test acquiring order permission."""
        limiter = BinanceRateLimiter()

        # Acquire order permission
        result = limiter.acquire(weight=1, is_order=True, blocking=False)

        assert result is True

        # Check both limiters consumed tokens (allow drift from refill)
        ip_tokens = limiter.ip_limiter.get_available_tokens()
        order_tokens = limiter.order_limiter.get_available_tokens()

        assert 1198 <= ip_tokens <= 1200  # ~1199 (1200 - 1)
        assert 48.5 <= order_tokens <= 49.5  # ~49 (50 - 1)

    def test_update_server_weight(self) -> None:
        """Test updating server-reported weight."""
        limiter = BinanceRateLimiter()

        limiter.update_server_weight(500)
        assert limiter.server_weight == 500

        limiter.update_server_weight(800)
        assert limiter.server_weight == 800

    def test_get_status(self) -> None:
        """Test getting rate limiter status."""
        limiter = BinanceRateLimiter()

        status = limiter.get_status()

        assert "ip_tokens_available" in status
        assert "ip_tokens_max" in status
        assert "order_tokens_available" in status
        assert "order_tokens_max" in status
        assert "server_weight" in status

        assert status["ip_tokens_max"] == 1200
        assert status["order_tokens_max"] == 50

    def test_reset(self) -> None:
        """Test resetting rate limiter."""
        limiter = BinanceRateLimiter()

        # Consume some tokens
        limiter.acquire(weight=100, is_order=False, blocking=False)
        limiter.update_server_weight(500)

        # Reset
        limiter.reset()

        # Should be back to full capacity (with small tolerance for time drift)
        status = limiter.get_status()
        assert pytest.approx(status["ip_tokens_available"], abs=1) == 1200
        assert pytest.approx(status["order_tokens_available"], abs=0.1) == 50
        assert status["server_weight"] == 0


class TestRateLimitDecorator:
    """Tests for rate limit decorator."""

    def test_decorator_basic_usage(self) -> None:
        """Test basic decorator usage."""
        call_count = {"value": 0}

        @with_rate_limit(weight=1, is_order=False)
        def api_call() -> str:
            call_count["value"] += 1
            return "success"

        result = api_call()

        assert result == "success"
        assert call_count["value"] == 1

    def test_decorator_multiple_calls(self) -> None:
        """Test decorator with multiple calls."""
        from src.utils.rate_limiter import binance_rate_limiter

        binance_rate_limiter.reset()  # Start fresh

        @with_rate_limit(weight=10, is_order=False)
        def api_call() -> str:
            return "success"

        # Make 5 calls (50 weight total)
        for _ in range(5):
            result = api_call()
            assert result == "success"

        # Check weight consumed from GLOBAL limiter (used by decorator)
        status = binance_rate_limiter.get_status()
        # Should have consumed 50 tokens (5 calls × 10 weight), allow drift
        assert 1145 <= status["ip_tokens_available"] <= 1155  # ~1150 (1200 - 50)


class TestRateLimitIntegration:
    """Integration tests for rate limiting."""

    def test_burst_then_throttle(self) -> None:
        """Test burst traffic followed by throttling."""
        config = RateLimitConfig(max_tokens=10, refill_rate=5, name="burst_test")
        bucket = TokenBucket(config)

        # Burst: consume 10 tokens rapidly
        for _i in range(10):
            result = bucket.consume(tokens=1, blocking=False)
            assert result is True

        # Should be out of tokens
        result = bucket.consume(tokens=1, blocking=False)
        assert result is False

        # Wait for refill (0.4 sec = 2 tokens at 5/sec)
        time.sleep(0.4)

        # Should be able to consume again
        result = bucket.consume(tokens=2, blocking=False)
        assert result is True

    def test_sustained_rate(self) -> None:
        """Test sustained request rate."""
        config = RateLimitConfig(max_tokens=10, refill_rate=10, name="sustained_test")
        bucket = TokenBucket(config)

        # Consume more than buffer capacity to force waiting (blocking mode)
        start = time.monotonic()

        # 6 requests * 2 tokens = 12 tokens
        # Initial buffer: 10 tokens (first 5 requests)
        # 6th request needs 2 more tokens → wait 2/10 = 0.2 seconds
        for _ in range(6):
            bucket.consume(tokens=2, blocking=True)

        elapsed = time.monotonic() - start

        # Should wait ~0.2 seconds for final 2 tokens
        assert elapsed >= 0.15  # Allow tolerance for scheduling
        assert elapsed < 0.4  # Should not take too long
