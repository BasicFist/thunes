#!/usr/bin/env python3.12
"""Validate audit trail functionality.

This script:
1. Executes a few paper trades to generate audit log entries
2. Validates JSONL format
3. Checks for expected event types
4. Verifies all required fields are present
"""

import json
import sys
from pathlib import Path

from src.config import settings
from src.live.paper_trader import PaperTrader
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def validate_jsonl_format(audit_file: Path) -> bool:
    """Validate that audit trail is valid JSONL format.

    Args:
        audit_file: Path to audit_trail.jsonl

    Returns:
        True if valid JSONL, False otherwise
    """
    if not audit_file.exists():
        logger.error(f"Audit trail file not found: {audit_file}")
        return False

    try:
        with open(audit_file) as f:
            for line_num, line in enumerate(f, start=1):
                if line.strip():  # Skip empty lines
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON on line {line_num}: {e}")
                        return False
        logger.info("✅ Audit trail is valid JSONL format")
        return True
    except Exception as e:
        logger.error(f"Error reading audit trail: {e}")
        return False


def check_event_types(audit_file: Path) -> dict[str, int]:
    """Count events by type.

    Args:
        audit_file: Path to audit_trail.jsonl

    Returns:
        Dictionary mapping event type to count
    """
    event_counts: dict[str, int] = {}

    with open(audit_file) as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                event = entry.get("event", "UNKNOWN")
                event_counts[event] = event_counts.get(event, 0) + 1

    logger.info("Event type distribution:")
    for event, count in sorted(event_counts.items()):
        logger.info(f"  {event}: {count}")

    return event_counts


def verify_required_fields(audit_file: Path) -> bool:
    """Verify all entries have required fields.

    Required fields (flat schema):
    - timestamp
    - event

    Args:
        audit_file: Path to audit_trail.jsonl

    Returns:
        True if all entries have required fields
    """
    required_fields = {"timestamp", "event"}

    with open(audit_file) as f:
        for line_num, line in enumerate(f, start=1):
            if line.strip():
                entry = json.loads(line)
                missing_fields = required_fields - set(entry.keys())
                if missing_fields:
                    logger.error(f"Line {line_num} missing required fields: {missing_fields}")
                    return False

    logger.info("✅ All entries have required fields (timestamp, event)")
    return True


def execute_sample_trades(trader: PaperTrader, num_trades: int = 3) -> None:
    """Execute a few sample trades to generate audit log entries.

    Args:
        trader: PaperTrader instance
        num_trades: Number of trade attempts to execute
    """
    logger.info(f"Executing {num_trades} sample trade attempts...")

    for i in range(num_trades):
        logger.info(f"Trade attempt {i+1}/{num_trades}")
        try:
            # Use smaller quote amount to pass risk check (MAX_LOSS_PER_TRADE=5.0)
            trader.run_strategy(
                symbol=settings.default_symbol,
                timeframe=settings.default_timeframe,
                quote_amount=4.0,  # Below MAX_LOSS_PER_TRADE limit
            )
        except Exception as e:
            logger.warning(f"Trade attempt {i+1} failed: {e}")
            # Continue anyway - failures also generate audit log entries

    logger.info("Sample trade execution complete")


def main() -> int:
    """Main validation workflow.

    Returns:
        0 if validation passed, 1 if failed
    """
    logger.info("=== Audit Trail Validation ===")

    # Initialize paper trader (testnet)
    logger.info(f"Initializing PaperTrader (testnet={settings.environment != 'live'})")
    trader = PaperTrader(testnet=(settings.environment != "live"))

    # Execute sample trades to generate audit log
    execute_sample_trades(trader, num_trades=3)

    # Validate audit trail
    audit_file = Path("logs/audit_trail.jsonl")

    # 1. Check JSONL format
    if not validate_jsonl_format(audit_file):
        logger.error("❌ JSONL format validation failed")
        return 1

    # 2. Verify required fields
    if not verify_required_fields(audit_file):
        logger.error("❌ Required fields validation failed")
        return 1

    # 3. Check event types
    event_counts = check_event_types(audit_file)

    # Verify we have at least one entry
    if not event_counts:
        logger.error("❌ No audit log entries found")
        return 1

    # Summary
    logger.info("\n=== Validation Summary ===")
    logger.info("✅ JSONL format: VALID")
    logger.info("✅ Required fields: PRESENT")
    logger.info(f"✅ Total entries: {sum(event_counts.values())}")
    logger.info(f"✅ Event types: {len(event_counts)}")

    # Display sample entries
    logger.info("\n=== Sample Entries ===")
    with open(audit_file) as f:
        lines = f.readlines()
        sample_size = min(3, len(lines))
        for i, line in enumerate(lines[-sample_size:], start=1):
            if line.strip():
                entry = json.loads(line)
                logger.info(f"\nEntry {i}:")
                logger.info(f"  Event: {entry['event']}")
                logger.info(f"  Timestamp: {entry['timestamp']}")
                # Display all other fields (flat schema)
                other_fields = {k: v for k, v in entry.items() if k not in ["event", "timestamp"]}
                logger.info(f"  Fields: {json.dumps(other_fields, indent=4)}")

    logger.info("\n✅ Audit trail validation PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
