"""Trading scheduler for autonomous operation.

This module provides automated scheduling of trading operations using APScheduler.
Features:
- Signal checks at configurable intervals
- Daily performance summaries
- Anti-overlap protection (max 1 job at a time)
- In-memory job store (NOTE: jobs re-created on restart)
- Graceful shutdown

KNOWN LIMITATION: SQLite job persistence disabled due to APScheduler serialization
issues with instance methods. Jobs will be re-scheduled on each restart.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from src.config import settings
from src.live.paper_trader import PaperTrader
from src.utils.circuit_breaker import circuit_monitor
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TradingScheduler:
    """Orchestrate trading operations with fault tolerance and persistence.

    Features:
    - SQLite-backed job persistence
    - Anti-overlap protection (max 1 concurrent job)
    - Graceful shutdown (waits for running jobs)
    - Timezone-aware scheduling (UTC)
    - Automatic error recovery
    """

    def __init__(self, use_persistent_store: bool = False) -> None:
        """Initialize scheduler with optional persistent job store.

        IMPORTANT: SQLite job persistence is currently disabled due to APScheduler
        serialization limitations with instance methods. Jobs will be re-created
        on each scheduler restart.

        TODO (Phase 13): Refactor to use standalone functions for job persistence.

        Args:
            use_persistent_store: If True, use SQLite (experimental, may fail).
                                  If False (default), use in-memory store.

        Job store location: logs/jobs.db (if persistent)
        Executor: Single-threaded (serial execution)
        """
        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)

        # Configure job store (memory by default to avoid serialization issues)
        if use_persistent_store:
            # EXPERIMENTAL: May fail with "Schedulers cannot be serialized" error
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

            jobstores = {"default": SQLAlchemyJobStore(url="sqlite:///logs/jobs.db")}
        else:
            # Use in-memory store (jobs won't persist across restarts)
            jobstores = {}

        # Configure executors (single thread for serial execution)
        executors = {"default": ThreadPoolExecutor(max_workers=1)}

        # Configure job defaults
        job_defaults = {
            "coalesce": True,  # Combine missed runs into one
            "max_instances": 1,  # Anti-overlap protection
            "misfire_grace_time": 60,  # Allow 60s delay before considering misfire
        }

        # Initialize scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="UTC",
        )

        # Initialize trading components
        self.paper_trader = PaperTrader(testnet=(settings.environment != "live"))

        # Initialize Telegram bot if configured
        self.telegram_bot: Any = None
        if settings.telegram_bot_token and settings.telegram_chat_id:
            try:
                from src.alerts.telegram import TelegramBot

                self.telegram_bot = TelegramBot()
                logger.info("Telegram bot initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Telegram bot: {e}")

        logger.info(
            f"TradingScheduler initialized (environment={settings.environment}, "
            f"testnet={settings.environment != 'live'})"
        )

    def _check_signals(self) -> None:
        """Job: Check for trading signals and execute strategy.

        This job runs periodically (default: every 10 minutes) to:
        1. Check if circuit breaker is open (skip if open)
        2. Run strategy for default symbol
        3. Handle errors gracefully (logged but don't crash scheduler)
        """
        try:
            # Check circuit breaker before executing
            if circuit_monitor.is_open("BinanceAPI"):
                logger.warning("Circuit breaker open - skipping signal check")
                return

            logger.info("Signal check started")
            self.paper_trader.run_strategy(
                symbol=settings.default_symbol,
                timeframe=settings.default_timeframe,
                quote_amount=settings.default_quote_amount,
            )
            logger.info("Signal check completed")

        except Exception as e:
            logger.error(f"Signal check failed: {e}", exc_info=True)
            # Don't re-raise - let scheduler continue

    def _send_daily_summary(self) -> None:
        """Job: Send daily performance summary via Telegram.

        Generates and sends a comprehensive daily report including:
        - Daily PnL
        - Number of trades
        - Win rate
        - Open positions
        - Risk status (kill-switch, daily loss)
        - System health (WebSocket, circuit breaker)
        """
        try:
            if not self.telegram_bot:
                logger.warning("Telegram not configured - skipping daily summary")
                return

            logger.info("Generating daily summary")

            # Get position tracker
            tracker = self.paper_trader.position_tracker

            # Calculate daily stats using position_history (includes closed positions)
            all_positions = tracker.get_position_history(symbol=None, limit=100)

            # Filter to closed positions from last 24 hours
            from datetime import timedelta

            yesterday = datetime.now() - timedelta(days=1)
            today_trades = [
                p
                for p in all_positions
                if p.status == "CLOSED" and p.exit_time and p.exit_time > yesterday
            ]

            if today_trades:
                daily_pnl = sum(p.pnl for p in today_trades)
                wins = [p for p in today_trades if p.pnl > 0]
                win_rate = len(wins) / len(today_trades) * 100 if today_trades else 0
            else:
                daily_pnl = 0.0
                win_rate = 0.0

            # Get risk status
            risk_status = self.paper_trader.risk_manager.get_risk_status()

            # Get open positions (for future use in detailed summary)
            # open_positions = tracker.get_open_positions()

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
            self.telegram_bot.send_message_sync(message.strip())
            logger.info("Daily summary sent")

        except Exception as e:
            logger.error(f"Daily summary failed: {e}", exc_info=True)
            # Don't re-raise - let scheduler continue

    def schedule_signal_check(self, interval_minutes: int = 10) -> None:
        """Schedule periodic signal checks.

        Args:
            interval_minutes: How often to check for signals (default: 10)

        The job will:
        - Run every N minutes
        - Skip if circuit breaker is open
        - Execute strategy for default symbol
        - Log results
        """
        self.scheduler.add_job(
            func=self._check_signals,
            trigger="interval",
            minutes=interval_minutes,
            id="signal_check",
            replace_existing=True,
            name="Signal Check",
        )
        logger.info(f"Scheduled signal checks every {interval_minutes} minutes")

    def schedule_daily_summary(self, hour: int = 23, minute: int = 0) -> None:
        """Schedule daily performance summary.

        Args:
            hour: Hour of day (0-23, UTC) to send summary (default: 23)
            minute: Minute of hour (0-59) to send summary (default: 0)

        The summary includes:
        - Daily trading performance
        - Risk status
        - System health
        """
        self.scheduler.add_job(
            func=self._send_daily_summary,
            trigger="cron",
            hour=hour,
            minute=minute,
            id="daily_summary",
            replace_existing=True,
            name="Daily Summary",
        )
        logger.info(f"Scheduled daily summary at {hour:02d}:{minute:02d} UTC")

    def start(self) -> None:
        """Start the scheduler.

        Raises:
            RuntimeError: If scheduler is already running
        """
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
        else:
            logger.warning("Scheduler already running")

    def stop(self, wait: bool = True) -> None:
        """Stop the scheduler.

        Args:
            wait: If True, wait for running jobs to complete before stopping.
                  If False, stop immediately (may interrupt running jobs).

        Graceful shutdown (wait=True) recommended for production to avoid
        partial trade execution.
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info(f"Scheduler stopped (wait={wait})")
        else:
            logger.warning("Scheduler not running")

    def get_job_status(self) -> list[dict[str, Any]]:
        """Get status of all scheduled jobs.

        Returns:
            List of job status dictionaries containing:
            - id: Job identifier
            - name: Human-readable job name
            - next_run: Next scheduled run time (ISO format)
            - trigger: Trigger configuration string

        Example:
            >>> scheduler.get_job_status()
            [
                {
                    'id': 'signal_check',
                    'name': 'Signal Check',
                    'next_run': '2025-10-03T12:50:00',
                    'trigger': 'interval[0:10:00]'
                },
                {
                    'id': 'daily_summary',
                    'name': 'Daily Summary',
                    'next_run': '2025-10-03T23:00:00',
                    'trigger': 'cron[hour=23, minute=0]'
                }
            ]
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            # Get next_run_time safely (may be None if scheduler not started)
            next_run = None
            if hasattr(job, "next_run_time") and job.next_run_time:
                next_run = job.next_run_time.isoformat()

            jobs.append(
                {
                    "id": job.id,
                    "name": job.name if hasattr(job, "name") else job.id,
                    "next_run": next_run,
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    def __repr__(self) -> str:
        """String representation of scheduler."""
        status = "running" if self.scheduler.running else "stopped"
        job_count = len(self.scheduler.get_jobs())
        return f"TradingScheduler(status={status}, jobs={job_count})"
