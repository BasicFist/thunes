"""Standalone job functions for APScheduler SQLite persistence.

This module contains standalone functions that can be serialized by APScheduler's
SQLite job store. Instance methods cannot be pickled, so all job logic is extracted
into these standalone functions.

Design Pattern:
- Functions accept all dependencies as parameters (no self references)
- Scheduler binds parameters using functools.partial when scheduling
- Functions are fully testable in isolation
- All functions handle errors gracefully (log but don't crash scheduler)
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.optimize.auto_reopt import WeeklyReoptimizer
from src.utils.circuit_breaker import circuit_monitor
from src.utils.logger import setup_logger

if TYPE_CHECKING:
    from src.alerts.telegram import TelegramBot
    from src.live.paper_trader import PaperTrader

logger = setup_logger(__name__)


def check_trading_signals(
    paper_trader: "PaperTrader",
    symbol: str,
    timeframe: str,
    quote_amount: float,
) -> None:
    """Check for trading signals and execute strategy.

    This job runs periodically (default: every 10 minutes) to:
    1. Check if circuit breaker is open (skip if open)
    2. Run strategy for specified symbol
    3. Handle errors gracefully (logged but don't crash scheduler)

    Args:
        paper_trader: PaperTrader instance for trade execution
        symbol: Trading pair (e.g., "BTCUSDT")
        timeframe: Candle timeframe (e.g., "1h", "15m")
        quote_amount: Amount to trade in quote currency (e.g., 10.0 USDT)

    Returns:
        None (logs results)

    Raises:
        No exceptions (all errors caught and logged)
    """
    try:
        # Check circuit breaker before executing
        if circuit_monitor.is_open("BinanceAPI"):
            logger.warning("Circuit breaker open - skipping signal check")
            return

        logger.info(f"Signal check started for {symbol}")
        paper_trader.run_strategy(
            symbol=symbol,
            timeframe=timeframe,
            quote_amount=quote_amount,
        )
        logger.info(f"Signal check completed for {symbol}")

    except Exception as e:
        logger.error(f"Signal check failed for {symbol}: {e}", exc_info=True)
        # Don't re-raise - let scheduler continue


def send_daily_performance_summary(
    paper_trader: "PaperTrader",
    telegram_bot: "TelegramBot | None",
) -> None:
    """Send daily performance summary via Telegram.

    Generates and sends a comprehensive daily report including:
    - Daily PnL
    - Number of trades
    - Win rate
    - Open positions
    - Risk status (kill-switch, daily loss)
    - System health (WebSocket, circuit breaker)

    Args:
        paper_trader: PaperTrader instance for accessing position tracker
        telegram_bot: TelegramBot instance for sending messages (None to skip)

    Returns:
        None (sends Telegram message)

    Raises:
        No exceptions (all errors caught and logged)
    """
    try:
        if not telegram_bot:
            logger.warning("Telegram not configured - skipping daily summary")
            return

        logger.info("Generating daily summary")

        # Get position tracker
        tracker = paper_trader.position_tracker

        # Calculate daily stats using position_history (includes closed positions)
        all_positions = tracker.get_position_history(symbol=None, limit=100)

        # Filter to closed positions from last 24 hours
        yesterday = datetime.now() - timedelta(days=1)
        today_trades = [
            p
            for p in all_positions
            if p.status == "CLOSED" and p.exit_time and p.exit_time > yesterday
        ]

        if today_trades:
            # Filter out positions with None pnl and calculate total
            valid_trades = [p for p in today_trades if p.pnl is not None]
            if valid_trades:
                # At this point, all positions have non-None pnl
                daily_pnl = float(sum(float(p.pnl) for p in valid_trades))  # type: ignore[arg-type,misc]
                wins = [p for p in valid_trades if float(p.pnl) > 0]  # type: ignore[arg-type]
                win_rate = len(wins) / len(valid_trades) * 100
            else:
                daily_pnl = 0.0
                win_rate = 0.0
        else:
            daily_pnl = 0.0
            win_rate = 0.0

        # Get risk status
        risk_status = paper_trader.risk_manager.get_risk_status()

        # Format message
        message = f"""📊 **THUNES Daily Summary**
📅 Date: {datetime.now().strftime('%Y-%m-%d')}

💰 **Performance**
Daily PnL: {daily_pnl:.2f} USDT
Trades Today: {len(today_trades)}
Win Rate: {win_rate:.1f}%

🎯 **Risk Status**
Open Positions: {risk_status['open_positions']}/{risk_status['max_positions']}
Daily PnL: {risk_status['daily_pnl']:.2f} USDT (Limit: {risk_status['daily_loss_limit']:.2f})
Kill-Switch: {'🔴 ACTIVE' if risk_status['kill_switch_active'] else '🟢 OK'}

🔌 **System Health**
Circuit Breaker: {'🟢 Closed' if not circuit_monitor.is_open('BinanceAPI') else '🔴 Open'}
"""

        # Send via Telegram
        telegram_bot.send_message_sync(message.strip())
        logger.info("Daily summary sent")

    except Exception as e:
        logger.error(f"Daily summary failed: {e}", exc_info=True)
        # Don't re-raise - let scheduler continue


def update_lab_infrastructure_metrics() -> None:
    """Update LAB infrastructure metrics (MCP health, worktree status).

    This job runs periodically (default: every 30 seconds) to:
    1. Check health of all 18 MCP servers
    2. Read worktree metadata from 5 worktrees
    3. Update Prometheus metrics for Grafana visualization

    No arguments needed - uses LAB workspace configuration.

    Returns:
        None (updates Prometheus metrics)

    Raises:
        No exceptions (all errors caught and logged)
    """
    try:
        import subprocess
        from pathlib import Path

        script_path = Path(__file__).parent.parent.parent / "scripts" / "update-lab-metrics.py"

        logger.debug("Updating LAB infrastructure metrics")

        # Run update script
        result = subprocess.run(
            ["python3", str(script_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode == 0:
            logger.debug("LAB metrics updated successfully")
        else:
            logger.warning(f"LAB metrics update had issues: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.warning("LAB metrics update timed out (>30s)")


def run_weekly_reoptimization(
    symbol: str,
    timeframe: str,
    strategy: str,
    lookback_days: int = 30,
    n_trials: int = 25,
    params_filename: str = "current_parameters.json",
) -> None:
    """Run weekly re-optimization for the specified strategy."""

    try:
        reoptimizer = WeeklyReoptimizer(
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=lookback_days,
            n_trials=n_trials,
            strategy=strategy,
            params_filename=params_filename,
        )

        if not reoptimizer.should_reoptimize():
            logger.info("Re-optimization skipped (fresh parameters for %s)", strategy)
            return

        results = reoptimizer.run()
        params = results.get("parameters") or results.get("best_params")
        sharpe = results.get("sharpe_ratio") or results.get("best_value")
        logger.info(
            "Re-optimization complete: strategy=%s sharpe=%.3f params=%s",
            reoptimizer.metadata.name,
            sharpe or 0.0,
            params,
        )

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Weekly re-optimization failed: %s", exc, exc_info=True)
        # Don't re-raise - let scheduler continue
