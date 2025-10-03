#!/usr/bin/env python3
"""CLI entry point for THUNES trading scheduler.

Usage:
    # Production (runs indefinitely)
    python src/orchestration/run_scheduler.py

    # Test mode (runs for 1 hour)
    python src/orchestration/run_scheduler.py --test-mode --duration=3600

    # Daemon mode (background process)
    nohup python src/orchestration/run_scheduler.py --daemon > logs/scheduler_daemon.log 2>&1 &
"""

import argparse
import signal
import sys
import time

from src.config import ensure_directories
from src.orchestration.scheduler import TradingScheduler
from src.utils.logger import setup_logger

# Ensure required directories exist (entrypoint responsibility)
ensure_directories()

logger = setup_logger(__name__)


def signal_handler(signum: int, frame: object, scheduler: TradingScheduler) -> None:
    """Handle shutdown signals gracefully.

    Args:
        signum: Signal number (SIGTERM=15, SIGINT=2)
        frame: Current stack frame (unused)
        scheduler: TradingScheduler instance to shutdown

    Performs graceful shutdown:
    1. Logs signal received
    2. Waits for running jobs to complete
    3. Shuts down scheduler
    4. Exits with code 0
    """
    sig_name = signal.Signals(signum).name
    logger.info(f"Received signal {sig_name} ({signum}), initiating graceful shutdown...")

    scheduler.stop(wait=True)
    logger.info("Scheduler shutdown complete")
    sys.exit(0)


def main() -> None:
    """Main entry point for scheduler CLI.

    Command-line arguments:
    --test-mode: Run for limited duration (useful for testing)
    --duration: Duration in seconds for test mode (default: 3600)
    --daemon: Daemon mode flag (informational, backgrounding handled by shell)

    Examples:
        # Production deployment
        $ python src/orchestration/run_scheduler.py

        # Test for 1 hour
        $ python src/orchestration/run_scheduler.py --test-mode --duration=3600

        # Background daemon (use nohup)
        $ nohup python src/orchestration/run_scheduler.py --daemon > logs/scheduler_daemon.log 2>&1 &
        $ echo $! > logs/scheduler.pid
    """
    parser = argparse.ArgumentParser(
        description="THUNES Trading Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Production:
    python src/orchestration/run_scheduler.py

  Test mode (1 hour):
    python src/orchestration/run_scheduler.py --test-mode --duration=3600

  Daemon mode (background):
    nohup python src/orchestration/run_scheduler.py --daemon > logs/scheduler_daemon.log 2>&1 &
    echo $! > logs/scheduler.pid
        """,
    )

    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Test mode (run for limited duration)",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=3600,
        help="Test mode duration in seconds (default: 3600 = 1 hour)",
    )

    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Daemon mode (informational flag, backgrounding via nohup)",
    )

    args = parser.parse_args()

    # Display banner
    logger.info("=" * 70)
    logger.info("THUNES Trading Scheduler")
    logger.info("=" * 70)

    if args.test_mode:
        logger.info(f"Mode: TEST (duration={args.duration}s)")
    elif args.daemon:
        logger.info("Mode: DAEMON (background)")
    else:
        logger.info("Mode: PRODUCTION (foreground)")

    # Initialize scheduler
    logger.info("Initializing scheduler...")
    scheduler = TradingScheduler()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, lambda signum, frame: signal_handler(signum, frame, scheduler))
    signal.signal(signal.SIGINT, lambda signum, frame: signal_handler(signum, frame, scheduler))

    # Schedule jobs
    logger.info("Scheduling jobs...")
    scheduler.schedule_signal_check(interval_minutes=10)
    scheduler.schedule_daily_summary(hour=23, minute=0)

    # Start scheduler
    scheduler.start()
    logger.info("Scheduler started successfully")

    # Display job status
    logger.info("Scheduled jobs:")
    for job in scheduler.get_job_status():
        logger.info(f"  - {job['name']} (id={job['id']}): next run at {job['next_run']}")

    # Keep running
    try:
        if args.test_mode:
            logger.info(f"Running in test mode for {args.duration} seconds...")
            logger.info("Press Ctrl+C to stop early")
            time.sleep(args.duration)
            logger.info("Test duration completed")
            scheduler.stop(wait=True)
        else:
            logger.info("Running indefinitely (press Ctrl+C to stop)")
            # Sleep in 60-second intervals to allow Ctrl+C responsiveness
            while True:
                time.sleep(60)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        scheduler.stop(wait=True)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        scheduler.stop(wait=False)  # Force stop on error
        sys.exit(1)

    logger.info("Scheduler stopped cleanly")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
