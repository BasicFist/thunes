#!/usr/bin/env python3
"""
Comprehensive System Health Check Script

Validates all critical components of the THUNES trading system.
Implements audit recommendations for improved monitoring and validation.

Usage:
    python scripts/system_health_check.py
    python scripts/system_health_check.py --verbose
    python scripts/system_health_check.py --json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.models.position import PositionTracker
from src.risk.manager import RiskManager
from src.utils.circuit_breaker import circuit_monitor
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class SystemHealthChecker:
    """Comprehensive system health validator."""

    def __init__(self, verbose: bool = False):
        """Initialize health checker."""
        self.verbose = verbose
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = 0
        self.results = {}

    def check(self, name: str, condition: bool, details: str = "") -> bool:
        """
        Execute a health check.

        Args:
            name: Check name
            condition: True if check passed
            details: Additional details

        Returns:
            condition value
        """
        if condition:
            self.checks_passed += 1
            status = "✅ PASS"
        else:
            self.checks_failed += 1
            status = "❌ FAIL"

        self.results[name] = {
            "status": "PASS" if condition else "FAIL",
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self.verbose or not condition:
            print(f"{status}: {name}")
            if details and (self.verbose or not condition):
                print(f"  → {details}")

        return condition

    def warn(self, name: str, details: str = "") -> None:
        """Record a warning (non-blocking)."""
        self.warnings += 1
        self.results[name] = {
            "status": "WARNING",
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self.verbose:
            print(f"⚠️  WARN: {name}")
            if details:
                print(f"  → {details}")

    def check_environment_config(self) -> bool:
        """Check environment configuration."""
        print("\n=== Environment Configuration ===")

        # Check required settings
        self.check(
            "Environment set",
            settings.environment in ["testnet", "paper", "live"],
            f"Environment: {settings.environment}",
        )

        self.check(
            "Default symbol configured",
            bool(settings.default_symbol),
            f"Symbol: {settings.default_symbol}",
        )

        self.check(
            "Default timeframe configured",
            bool(settings.default_timeframe),
            f"Timeframe: {settings.default_timeframe}",
        )

        # Warn if production environment
        if settings.environment == "live":
            self.warn(
                "Production environment detected",
                "Using LIVE trading - ensure this is intentional!",
            )

        return True

    def check_risk_configuration(self) -> bool:
        """Check risk management configuration."""
        print("\n=== Risk Management Configuration ===")

        self.check(
            "Max loss per trade configured",
            settings.max_loss_per_trade > 0,
            f"Max loss/trade: {settings.max_loss_per_trade} USDT",
        )

        self.check(
            "Max daily loss configured",
            settings.max_daily_loss > 0,
            f"Max daily loss: {settings.max_daily_loss} USDT",
        )

        self.check(
            "Max positions configured",
            settings.max_positions > 0,
            f"Max positions: {settings.max_positions}",
        )

        self.check(
            "Cool-down period configured",
            settings.cool_down_minutes > 0,
            f"Cool-down: {settings.cool_down_minutes} minutes",
        )

        # Check risk limits are sensible
        if settings.max_loss_per_trade >= settings.max_daily_loss:
            self.warn(
                "Per-trade loss >= daily loss",
                f"Single trade can trigger kill-switch ({settings.max_loss_per_trade} >= {settings.max_daily_loss})",
            )

        return True

    def check_risk_manager_status(self) -> bool:
        """Check RiskManager operational status."""
        print("\n=== Risk Manager Status ===")

        try:
            position_tracker = PositionTracker()
            risk_manager = RiskManager(
                position_tracker=position_tracker,
                enable_telegram=False,  # Don't send alerts during health check
            )

            status = risk_manager.get_risk_status()

            self.check(
                "RiskManager initialized",
                True,
                f"Kill-switch: {'ACTIVE' if status['kill_switch_active'] else 'Inactive'}",
            )

            self.check(
                "Position tracking operational",
                status["open_positions"] >= 0,
                f"Open positions: {status['open_positions']}/{status['max_positions']}",
            )

            # Check daily PnL is reasonable
            daily_pnl = status["daily_pnl"]
            self.check(
                "Daily PnL within limits",
                daily_pnl > -settings.max_daily_loss,
                f"Daily PnL: {daily_pnl:.2f} / Limit: {-settings.max_daily_loss:.2f}",
            )

            # Warn if kill-switch active
            if status["kill_switch_active"]:
                self.warn(
                    "Kill-switch is ACTIVE",
                    f"Trading halted. Daily loss: {daily_pnl:.2f} USDT",
                )

            # Warn if cool-down active
            if status["cool_down_active"]:
                remaining = status["cool_down_remaining_minutes"]
                self.warn(
                    "Cool-down period active",
                    f"{remaining:.1f} minutes remaining after loss",
                )

            # Warn if near daily loss limit
            if daily_pnl < 0:
                utilization = abs(daily_pnl / settings.max_daily_loss * 100)
                if utilization > 75:
                    self.warn(
                        "Near daily loss limit",
                        f"Daily loss utilization: {utilization:.1f}%",
                    )

        except Exception as e:
            self.check("RiskManager initialized", False, f"Error: {e}")
            return False

        return True

    def check_circuit_breaker_status(self) -> bool:
        """Check circuit breaker status."""
        print("\n=== Circuit Breaker Status ===")

        try:
            status = circuit_monitor.get_status()

            self.check(
                "Circuit breaker monitor operational",
                len(status) > 0,
                f"Monitoring {len(status)} breaker(s)",
            )

            for name, info in status.items():
                state = info["state"]
                fail_count = info["fail_counter"]
                fail_max = info["fail_max"]

                self.check(
                    f"Circuit breaker '{name}' state",
                    state != "open",
                    f"State: {state}, Failures: {fail_count}/{fail_max}",
                )

                # Warn if approaching failure threshold
                if state == "closed" and fail_count > 0:
                    utilization = (fail_count / fail_max) * 100
                    if utilization > 60:
                        self.warn(
                            f"Circuit breaker '{name}' under stress",
                            f"Failure rate: {utilization:.0f}% ({fail_count}/{fail_max})",
                        )

        except Exception as e:
            self.check("Circuit breaker monitor operational", False, f"Error: {e}")
            return False

        return True

    def check_database_health(self) -> bool:
        """Check database health."""
        print("\n=== Database Health ===")

        try:
            position_tracker = PositionTracker()

            # Check if we can query positions
            positions = position_tracker.get_all_open_positions()
            self.check(
                "Position database accessible",
                True,
                f"Open positions: {len(positions)}",
            )

            # Check if we can query history
            history = position_tracker.get_position_history(limit=10)
            self.check(
                "Position history queryable",
                True,
                f"Recent positions: {len(history)}",
            )

            # Atomic count test
            count = position_tracker.count_open_positions()
            self.check(
                "Atomic position count operational",
                count == len(positions),
                f"Count: {count} (verified)",
            )

        except Exception as e:
            self.check("Position database accessible", False, f"Error: {e}")
            return False

        return True

    def check_audit_trail(self) -> bool:
        """Check audit trail integrity."""
        print("\n=== Audit Trail ===")

        audit_trail_path = Path("logs/audit_trail.jsonl")

        if audit_trail_path.exists():
            self.check(
                "Audit trail file exists",
                True,
                f"Path: {audit_trail_path}",
            )

            # Check if file is readable
            try:
                with open(audit_trail_path, "r") as f:
                    lines = f.readlines()
                    self.check(
                        "Audit trail readable",
                        True,
                        f"Events logged: {len(lines)}",
                    )

                    # Validate JSON format
                    if lines:
                        try:
                            last_event = json.loads(lines[-1])
                            self.check(
                                "Audit trail format valid",
                                "timestamp" in last_event and "event" in last_event,
                                f"Last event: {last_event.get('event', 'unknown')}",
                            )
                        except json.JSONDecodeError as e:
                            self.check(
                                "Audit trail format valid",
                                False,
                                f"JSON parse error: {e}",
                            )
            except Exception as e:
                self.check("Audit trail readable", False, f"Error: {e}")
        else:
            self.warn(
                "Audit trail not initialized",
                "File will be created on first risk event",
            )

        return True

    def check_file_permissions(self) -> bool:
        """Check critical file permissions."""
        print("\n=== File Permissions ===")

        # Check scripts are executable
        script_dir = Path("scripts")
        if script_dir.exists():
            critical_scripts = [
                "dr_drill_preflight.sh",
                "post_deployment_verification.sh",
                "setup_testnet_credentials.py",
                "validate_telegram.py",
                "validate_binance.py",
            ]

            for script_name in critical_scripts:
                script_path = script_dir / script_name
                if script_path.exists():
                    is_executable = script_path.stat().st_mode & 0o111 != 0
                    self.check(
                        f"Script '{script_name}' executable",
                        is_executable,
                        f"Permissions: {oct(script_path.stat().st_mode)[-3:]}",
                    )
                else:
                    self.warn(f"Script '{script_name}' not found", "Expected in scripts/")

        return True

    def run_all_checks(self) -> bool:
        """
        Run all health checks.

        Returns:
            True if all checks passed
        """
        print("=" * 60)
        print("THUNES System Health Check")
        print("=" * 60)
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        print(f"Environment: {settings.environment}")

        self.check_environment_config()
        self.check_risk_configuration()
        self.check_risk_manager_status()
        self.check_circuit_breaker_status()
        self.check_database_health()
        self.check_audit_trail()
        self.check_file_permissions()

        # Summary
        print("\n" + "=" * 60)
        print("HEALTH CHECK SUMMARY")
        print("=" * 60)
        print(f"✅ Passed:   {self.checks_passed}")
        print(f"❌ Failed:   {self.checks_failed}")
        print(f"⚠️  Warnings: {self.warnings}")
        print("=" * 60)

        if self.checks_failed == 0:
            print("✅ SYSTEM HEALTH: GOOD")
            return True
        else:
            print("❌ SYSTEM HEALTH: DEGRADED")
            print(f"\n{self.checks_failed} critical check(s) failed. Review failures above.")
            return False

    def get_results_json(self) -> str:
        """Get results in JSON format."""
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.environment,
            "summary": {
                "checks_passed": self.checks_passed,
                "checks_failed": self.checks_failed,
                "warnings": self.warnings,
                "overall_status": "HEALTHY" if self.checks_failed == 0 else "DEGRADED",
            },
            "checks": self.results,
        }
        return json.dumps(summary, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="THUNES System Health Check")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output (show all checks)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    checker = SystemHealthChecker(verbose=args.verbose)
    success = checker.run_all_checks()

    if args.json:
        print("\n" + "=" * 60)
        print("JSON OUTPUT")
        print("=" * 60)
        print(checker.get_results_json())

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
