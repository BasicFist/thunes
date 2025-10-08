"""Prometheus metrics for THUNES trading system.

This module implements Sprint 2.3 metrics from Phase 13 observability plan.
Exposes trading state, risk management, and system health metrics.
"""

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, generate_latest

# Create separate registry to avoid conflicts with other Prometheus exporters
registry = CollectorRegistry()

# Kill-Switch State
kill_switch_active = Gauge(
    "thunes_kill_switch_active",
    "Kill-switch status (0=inactive, 1=active)",
    registry=registry,
)

# Circuit Breaker State
circuit_breaker_state = Gauge(
    "thunes_circuit_breaker_state",
    "Circuit breaker state (0=CLOSED, 1=OPEN, 0.5=HALF_OPEN)",
    ["breaker_name"],
    registry=registry,
)

# Risk Metrics
daily_pnl_used = Gauge(
    "thunes_daily_pnl_used",
    "Daily PnL used as fraction of limit (0.0-1.0+, >1.0 indicates exceeded)",
    registry=registry,
)

open_positions = Gauge(
    "thunes_open_positions",
    "Number of currently open trading positions",
    registry=registry,
)

# Order Metrics
orders_placed_total = Counter(
    "thunes_orders_placed_total",
    "Total orders placed by venue, type, and side",
    ["venue", "order_type", "side"],
    registry=registry,
)

order_latency_ms = Histogram(
    "thunes_order_latency_ms",
    "Order placement latency in milliseconds",
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000],  # milliseconds
    registry=registry,
)

# WebSocket Health
ws_gap_seconds = Histogram(
    "thunes_ws_gap_seconds",
    "Time gap between WebSocket messages in seconds",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],  # seconds
    registry=registry,
)

ws_connected = Gauge(
    "thunes_ws_connected",
    "WebSocket connection status (0=disconnected, 1=connected)",
    ["symbol"],
    registry=registry,
)


def metrics_handler() -> bytes:
    """HTTP handler for /metrics endpoint.

    Returns:
        bytes: Prometheus exposition format metrics

    Example:
        from flask import Flask, Response
        from src.monitoring.prometheus_metrics import metrics_handler

        app = Flask(__name__)

        @app.route("/metrics")
        def metrics():
            return Response(metrics_handler(), mimetype="text/plain")
    """
    return generate_latest(registry)


def update_kill_switch_metric(active: bool) -> None:
    """Update kill-switch metric (called from RiskManager)."""
    kill_switch_active.set(1 if active else 0)


def update_circuit_breaker_metric(breaker_name: str, state: str) -> None:
    """Update circuit breaker metric (called from CircuitBreaker).

    Args:
        breaker_name: Name of the circuit breaker (e.g., "BinanceAPI")
        state: Current state ("closed", "open", "half-open")
    """
    state_map = {"closed": 0.0, "open": 1.0, "half-open": 0.5}
    circuit_breaker_state.labels(breaker_name=breaker_name).set(
        state_map.get(state.lower(), 0.0)
    )


def update_risk_metrics(daily_pnl: float, max_daily_loss: float, position_count: int) -> None:
    """Update risk-related metrics (called from RiskManager).

    Args:
        daily_pnl: Current daily PnL in USDT
        max_daily_loss: Maximum allowed daily loss (positive number)
        position_count: Number of open positions
    """
    # Calculate fraction of daily loss limit used
    # Example: daily_pnl=-15, max_daily_loss=20 → 0.75 (75% of limit used)
    # Example: daily_pnl=-25, max_daily_loss=20 → 1.25 (125%, exceeded)
    pnl_fraction = abs(daily_pnl) / max_daily_loss if max_daily_loss > 0 else 0.0
    daily_pnl_used.set(pnl_fraction)
    open_positions.set(position_count)


def record_order_placed(venue: str, order_type: str, side: str, latency_ms: float) -> None:
    """Record order placement event (called from PaperTrader).

    Args:
        venue: Trading venue (e.g., "binance")
        order_type: Order type (e.g., "MARKET", "LIMIT")
        side: Order side ("BUY" or "SELL")
        latency_ms: Order placement latency in milliseconds
    """
    orders_placed_total.labels(venue=venue, order_type=order_type, side=side).inc()
    order_latency_ms.observe(latency_ms)


def record_ws_message_gap(symbol: str, gap_seconds: float) -> None:
    """Record WebSocket message gap (called from WebSocketStream).

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        gap_seconds: Time gap between messages in seconds
    """
    ws_gap_seconds.observe(gap_seconds)


def update_ws_connection(symbol: str, connected: bool) -> None:
    """Update WebSocket connection status (called from WebSocketStream).

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        connected: Connection status
    """
    ws_connected.labels(symbol=symbol).set(1 if connected else 0)


# ============================================================================
# LAB Infrastructure Metrics (TIER 3)
# ============================================================================

# MCP Server Health
lab_mcp_server_health = Gauge(
    "lab_mcp_server_health",
    "MCP server health status (0=down, 1=up, 2=not_configured)",
    ["server_name"],
    registry=registry,
)

# Worktree Status
lab_worktree_status = Gauge(
    "lab_worktree_status",
    "Worktree status (0=complete, 1=working, 2=testing, 3=blocked)",
    ["worktree_name"],
    registry=registry,
)

# Worktree Test Status
lab_worktree_test_status = Gauge(
    "lab_worktree_test_status",
    "Worktree test status (0=unknown, 1=passing, 2=failing)",
    ["worktree_name"],
    registry=registry,
)


def update_mcp_health(server_name: str, status: str) -> None:
    """Update MCP server health metric.

    Args:
        server_name: MCP server name (e.g., "rag-query", "context7")
        status: Health status ("up", "down", "not_configured")
    """
    status_map = {"down": 0.0, "up": 1.0, "not_configured": 2.0}
    lab_mcp_server_health.labels(server_name=server_name).set(
        status_map.get(status.lower(), 0.0)
    )


def update_worktree_status(worktree_name: str, status: str) -> None:
    """Update worktree status metric.

    Args:
        worktree_name: Worktree name (e.g., "main", "dev", "thunes")
        status: Work status ("complete", "working", "testing", "blocked")
    """
    status_map = {"complete": 0.0, "working": 1.0, "testing": 2.0, "blocked": 3.0}
    lab_worktree_status.labels(worktree_name=worktree_name).set(
        status_map.get(status.lower(), 1.0)
    )


def update_worktree_test_status(worktree_name: str, test_status: str) -> None:
    """Update worktree test status metric.

    Args:
        worktree_name: Worktree name (e.g., "main", "dev", "thunes")
        test_status: Test status ("unknown", "passing", "failing")
    """
    status_map = {"unknown": 0.0, "passing": 1.0, "failing": 2.0}
    lab_worktree_test_status.labels(worktree_name=worktree_name).set(
        status_map.get(test_status.lower(), 0.0)
    )
