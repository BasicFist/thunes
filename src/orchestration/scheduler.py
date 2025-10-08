"""Trading scheduler for autonomous operation.

This module provides automated scheduling of trading operations using APScheduler.
Features:
- Signal checks at configurable intervals
- Daily performance summaries
- Anti-overlap protection (max 1 job at a time)
- SQLite job persistence (jobs survive restarts)
- Graceful shutdown

Implementation:
- Uses standalone job functions (src.orchestration.jobs) for serialization
- Binds parameters as kwargs when scheduling (textual references)
- Jobs persist across scheduler restarts via SQLite
"""

from pathlib import Path
from typing import Any

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from src.config import settings
from src.live.paper_trader import PaperTrader
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
        """Initialize scheduler with configurable job store.

        IMPORTANT: SQLite persistence is disabled by default due to serialization
        limitations with complex objects (PaperTrader contains unpicklable dependencies
        like database connections, locks, weak references).

        **Recommended Pattern**: Application code should re-schedule jobs on each start:
        ```python
        scheduler = TradingScheduler()
        scheduler.schedule_signal_check(interval_minutes=10)
        scheduler.schedule_daily_summary(hour=23, minute=0)
        scheduler.start()
        ```

        Args:
            use_persistent_store: If True, use SQLite for job persistence (experimental).
                                  If False (default), use in-memory store (jobs re-created on start).

        Job store location: logs/jobs.db (if persistent)
        Executor: Single-threaded (serial execution)
        """
        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)

        # Configure job store
        if use_persistent_store:
            # Experimental: Only works for jobs with simple parameters
            # Complex objects (PaperTrader) cannot be pickled
            jobstores = {"default": SQLAlchemyJobStore(url="sqlite:///logs/jobs.db")}
            logger.warning(
                "Using SQLite job store (experimental - may fail with complex parameters)"
            )
        else:
            # Use in-memory store (jobs re-scheduled on each start - recommended)
            jobstores = {}
            logger.info("Using in-memory job store (jobs re-created on start)")

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

    def schedule_signal_check(self, interval_minutes: int = 10) -> None:
        """Schedule periodic signal checks.

        Args:
            interval_minutes: How often to check for signals (default: 10)

        The job will:
        - Run every N minutes
        - Skip if circuit breaker is open
        - Execute strategy for default symbol
        - Log results
        - Persist in SQLite (survives scheduler restarts)
        """
        # Use textual reference for SQLite serialization
        # Pass parameters as kwargs (will be serialized in SQLite)
        self.scheduler.add_job(
            func="src.orchestration.jobs:check_trading_signals",
            trigger="interval",
            minutes=interval_minutes,
            kwargs={
                "paper_trader": self.paper_trader,
                "symbol": settings.default_symbol,
                "timeframe": settings.default_timeframe,
                "quote_amount": settings.default_quote_amount,
            },
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
        - Persist in SQLite (survives scheduler restarts)
        """
        # Use textual reference for SQLite serialization
        # Pass parameters as kwargs (will be serialized in SQLite)
        self.scheduler.add_job(
            func="src.orchestration.jobs:send_daily_performance_summary",
            trigger="cron",
            hour=hour,
            minute=minute,
            kwargs={
                "paper_trader": self.paper_trader,
                "telegram_bot": self.telegram_bot,
            },
            id="daily_summary",
            replace_existing=True,
            name="Daily Summary",
        )
        logger.info(f"Scheduled daily summary at {hour:02d}:{minute:02d} UTC")

    def schedule_lab_metrics_update(self, interval_seconds: int = 30) -> None:
        """Schedule periodic LAB infrastructure metrics updates.

        Args:
            interval_seconds: How often to update metrics (default: 30)

        The job will:
        - Run every N seconds
        - Check MCP server health (18 servers)
        - Read worktree metadata (5 worktrees)
        - Update Prometheus metrics for Grafana
        - No parameters needed (uses LAB workspace configuration)
        """
        # Use textual reference for SQLite serialization
        # No parameters needed - script reads LAB workspace directly
        self.scheduler.add_job(
            func="src.orchestration.jobs:update_lab_infrastructure_metrics",
            trigger="interval",
            seconds=interval_seconds,
            kwargs={},
            id="lab_metrics_update",
            replace_existing=True,
            name="LAB Metrics Update",
        )
        logger.info(f"Scheduled LAB metrics updates every {interval_seconds} seconds")

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
