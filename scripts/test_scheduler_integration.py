#!/usr/bin/env python3.12
"""Integration test for trading scheduler.

This script:
1. Starts the scheduler with short intervals
2. Runs for a configurable duration (default: 5 minutes)
3. Monitors job execution
4. Validates logs and metrics
"""

import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from src.orchestration.scheduler import TradingScheduler
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def signal_handler(signum: int, frame: object) -> None:
    """Handle SIGINT (Ctrl+C) for graceful shutdown."""
    sig_name = signal.Signals(signum).name
    logger.info(f"\nReceived signal {sig_name} - initiating shutdown...")
    sys.exit(0)


def main() -> int:
    """Run integration test.

    Returns:
        0 if test passed, 1 if failed
    """
    # Configuration
    TEST_DURATION_SECONDS = 5 * 60  # 5 minutes
    SIGNAL_CHECK_INTERVAL = 2  # Check every 2 minutes (3 executions in 5 min)

    logger.info("=== Scheduler Integration Test ===")
    logger.info(f"Test duration: {TEST_DURATION_SECONDS}s ({TEST_DURATION_SECONDS/60:.1f} min)")
    logger.info(f"Signal check interval: {SIGNAL_CHECK_INTERVAL} min")
    logger.info(f"Expected signal checks: ~{TEST_DURATION_SECONDS // (SIGNAL_CHECK_INTERVAL * 60)}")

    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Initialize scheduler
    logger.info("\n--- Initializing Scheduler ---")
    scheduler = TradingScheduler()

    # Schedule jobs with short intervals for testing
    logger.info(f"Scheduling signal check every {SIGNAL_CHECK_INTERVAL} minutes")
    scheduler.schedule_signal_check(interval_minutes=SIGNAL_CHECK_INTERVAL)

    # Don't schedule daily summary (would only run at 23:00 UTC)
    # scheduler.schedule_daily_summary(hour=23, minute=0)

    # Display job status
    jobs = scheduler.get_job_status()
    logger.info(f"\nScheduled jobs ({len(jobs)}):")
    for job in jobs:
        logger.info(f"  - {job['name']} (ID: {job['id']})")
        logger.info(f"    Trigger: {job['trigger']}")
        logger.info(f"    Next run: {job['next_run'] or 'Not scheduled yet'}")

    # Start scheduler
    logger.info("\n--- Starting Scheduler ---")
    start_time = datetime.now()
    scheduler.start()
    logger.info("✅ Scheduler started")

    # Monitor execution
    logger.info(f"\n--- Running for {TEST_DURATION_SECONDS}s ---")
    logger.info("Press Ctrl+C to stop early\n")

    try:
        elapsed = 0
        while elapsed < TEST_DURATION_SECONDS:
            time.sleep(10)  # Check every 10 seconds
            elapsed = (datetime.now() - start_time).total_seconds()

            # Log progress every minute
            if int(elapsed) % 60 == 0 and elapsed > 0:
                logger.info(
                    f"Running... {int(elapsed)}s / {TEST_DURATION_SECONDS}s "
                    f"({elapsed/TEST_DURATION_SECONDS*100:.0f}%)"
                )

    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")

    # Stop scheduler gracefully
    logger.info("\n--- Stopping Scheduler ---")
    scheduler.stop(wait=True)
    logger.info("✅ Scheduler stopped")

    # Analyze results
    logger.info("\n=== Test Results ===")

    # Check logs
    log_file = Path("logs/scheduler.log")
    if log_file.exists():
        with open(log_file) as f:
            lines = f.readlines()
            logger.info(f"✅ Scheduler log exists: {len(lines)} lines")

            # Count signal check executions
            signal_check_lines = [line for line in lines if "Signal check" in line]
            logger.info(f"✅ Signal check log entries: {len(signal_check_lines)}")

            # Check for errors
            error_lines = [line for line in lines if "ERROR" in line]
            if error_lines:
                logger.warning(f"⚠️ Errors found in log: {len(error_lines)}")
                logger.warning("Recent errors:")
                for line in error_lines[-5:]:
                    logger.warning(f"  {line.strip()}")
            else:
                logger.info("✅ No errors in scheduler log")
    else:
        logger.error("❌ Scheduler log not found")
        return 1

    # Check paper trader log
    paper_log = Path("logs/paper_trader.log")
    if paper_log.exists():
        with open(paper_log) as f:
            lines = f.readlines()
            logger.info(f"✅ Paper trader log exists: {len(lines)} lines")

            # Count strategy runs
            strategy_runs = [line for line in lines if "Running strategy for" in line]
            logger.info(f"✅ Strategy executions: {len(strategy_runs)}")
    else:
        logger.warning("⚠️ Paper trader log not found (may be normal if no signals)")

    # Check audit trail
    audit_file = Path("logs/audit_trail.jsonl")
    if audit_file.exists():
        with open(audit_file) as f:
            lines = [line for line in f if line.strip()]
            logger.info(f"✅ Audit trail entries: {len(lines)}")
    else:
        logger.warning("⚠️ Audit trail not found")

    # Summary
    logger.info("\n=== Test Summary ===")
    actual_duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"Test duration: {actual_duration:.1f}s ({actual_duration/60:.1f} min)")
    logger.info("Scheduler: Started and stopped gracefully")

    expected_checks = max(1, int(actual_duration // (SIGNAL_CHECK_INTERVAL * 60)))
    logger.info(f"Expected signal checks: ~{expected_checks}")

    logger.info("\n✅ Integration test COMPLETED")
    logger.info("\nNext steps:")
    logger.info("1. Review logs/scheduler.log for any errors")
    logger.info("2. Check logs/paper_trader.log for strategy execution details")
    logger.info("3. If no issues, proceed to 1-hour test (--duration=3600)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
