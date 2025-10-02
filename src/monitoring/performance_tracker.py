"""Performance monitoring and parameter decay detection.

Tracks rolling performance metrics to detect when strategy parameters decay.
Triggers alerts and re-optimization when performance drops below thresholds.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from src.config import ARTIFACTS_DIR
from src.models.position import Position, PositionTracker
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class PerformanceTracker:
    """
    Track trading performance and detect parameter decay.

    Monitors rolling Sharpe ratio and other metrics to determine when
    strategy parameters need re-optimization.
    """

    def __init__(
        self,
        position_tracker: PositionTracker,
        sharpe_threshold: float = 1.0,
        critical_threshold: float = 0.5,
        rolling_window_days: int = 7,
    ):
        """
        Initialize performance tracker.

        Args:
            position_tracker: Position tracker instance
            sharpe_threshold: Sharpe below this triggers decay warning (default: 1.0)
            critical_threshold: Sharpe below this triggers immediate re-opt (default: 0.5)
            rolling_window_days: Window for rolling metrics (default: 7)
        """
        self.position_tracker = position_tracker
        self.sharpe_threshold = sharpe_threshold
        self.critical_threshold = critical_threshold
        self.rolling_window_days = rolling_window_days

        # Performance history file
        self.performance_file = ARTIFACTS_DIR / "monitoring" / "performance_history.csv"
        self.performance_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"PerformanceTracker initialized: "
            f"sharpe_threshold={sharpe_threshold}, "
            f"critical_threshold={critical_threshold}, "
            f"window={rolling_window_days}d"
        )

    def calculate_rolling_sharpe(self, window_days: Optional[int] = None) -> float:
        """
        Calculate rolling Sharpe ratio from recent closed positions.

        Args:
            window_days: Days to look back (defaults to rolling_window_days)

        Returns:
            Rolling Sharpe ratio (annualized), or 0.0 if insufficient data
        """
        window = window_days or self.rolling_window_days
        cutoff_date = datetime.utcnow() - timedelta(days=window)

        # Get recent closed positions
        positions = self.position_tracker.get_position_history(limit=1000)

        # Filter to window
        recent_positions = [
            p for p in positions if p.exit_time and p.exit_time >= cutoff_date
        ]

        if len(recent_positions) < 2:
            logger.debug(
                f"Insufficient data for Sharpe calculation ({len(recent_positions)} positions)"
            )
            return 0.0

        # Calculate returns
        returns = [float(p.pnl or 0) for p in recent_positions]
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return == 0 or np.isnan(std_return):
            logger.debug("Zero or NaN standard deviation, cannot calculate Sharpe")
            return 0.0

        # Annualize (assuming ~2 trades/day avg for crypto)
        trades_per_year = 365 * 2
        sharpe = (mean_return / std_return) * np.sqrt(trades_per_year)

        logger.debug(
            f"Rolling Sharpe ({window}d): {sharpe:.3f} "
            f"(mean={mean_return:.2f}, std={std_return:.2f}, n={len(recent_positions)})"
        )

        return float(sharpe)

    def calculate_win_rate(self, window_days: Optional[int] = None) -> float:
        """
        Calculate win rate from recent positions.

        Args:
            window_days: Days to look back

        Returns:
            Win rate percentage (0-100)
        """
        window = window_days or self.rolling_window_days
        cutoff_date = datetime.utcnow() - timedelta(days=window)

        positions = self.position_tracker.get_position_history(limit=1000)
        recent_positions = [
            p for p in positions if p.exit_time and p.exit_time >= cutoff_date
        ]

        if not recent_positions:
            return 0.0

        wins = sum(1 for p in recent_positions if (p.pnl or 0) > 0)
        win_rate = (wins / len(recent_positions)) * 100

        return win_rate

    def calculate_average_pnl(self, window_days: Optional[int] = None) -> Decimal:
        """
        Calculate average PnL per trade.

        Args:
            window_days: Days to look back

        Returns:
            Average PnL per trade
        """
        window = window_days or self.rolling_window_days
        cutoff_date = datetime.utcnow() - timedelta(days=window)

        positions = self.position_tracker.get_position_history(limit=1000)
        recent_positions = [
            p for p in positions if p.exit_time and p.exit_time >= cutoff_date
        ]

        if not recent_positions:
            return Decimal("0.00")

        total_pnl = sum(p.pnl or Decimal("0") for p in recent_positions)
        avg_pnl = total_pnl / len(recent_positions)

        return avg_pnl

    def detect_decay(self) -> tuple[bool, str, float]:
        """
        Detect if parameters are decaying based on performance metrics.

        Returns:
            Tuple of (is_decaying, severity, current_sharpe)
            - is_decaying: True if decay detected
            - severity: "WARNING" (< threshold) or "CRITICAL" (< critical)
            - current_sharpe: Current rolling Sharpe ratio
        """
        sharpe = self.calculate_rolling_sharpe()

        if sharpe < self.critical_threshold:
            logger.warning(
                f"🚨 CRITICAL decay detected: Sharpe {sharpe:.3f} < {self.critical_threshold}"
            )
            return True, "CRITICAL", sharpe

        if sharpe < self.sharpe_threshold:
            logger.warning(
                f"⚠️ Parameter decay detected: Sharpe {sharpe:.3f} < {self.sharpe_threshold}"
            )
            return True, "WARNING", sharpe

        logger.debug(f"✓ Performance healthy: Sharpe {sharpe:.3f} >= {self.sharpe_threshold}")
        return False, "OK", sharpe

    def get_performance_metrics(self) -> dict[str, Any]:
        """
        Get comprehensive performance metrics.

        Returns:
            Dictionary with all performance metrics
        """
        sharpe_7d = self.calculate_rolling_sharpe(window_days=7)
        sharpe_3d = self.calculate_rolling_sharpe(window_days=3)
        sharpe_1d = self.calculate_rolling_sharpe(window_days=1)

        win_rate_7d = self.calculate_win_rate(window_days=7)
        avg_pnl_7d = self.calculate_average_pnl(window_days=7)

        # Get total stats
        all_positions = self.position_tracker.get_position_history(limit=1000)
        total_closed = len([p for p in all_positions if p.status == "CLOSED"])
        total_pnl = self.position_tracker.get_total_pnl()

        # Decay detection
        is_decaying, severity, _ = self.detect_decay()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "rolling_sharpe": {
                "1d": round(sharpe_1d, 3),
                "3d": round(sharpe_3d, 3),
                "7d": round(sharpe_7d, 3),
            },
            "win_rate_7d": round(win_rate_7d, 1),
            "avg_pnl_7d": float(avg_pnl_7d),
            "total_trades": total_closed,
            "total_pnl": float(total_pnl),
            "decay_detected": is_decaying,
            "decay_severity": severity,
            "requires_reoptimization": severity == "CRITICAL",
        }

    def log_performance_snapshot(self) -> None:
        """
        Log current performance snapshot to CSV file.

        Appends metrics to performance history for tracking over time.
        """
        metrics = self.get_performance_metrics()

        # Create DataFrame row
        row = pd.DataFrame(
            [
                {
                    "timestamp": metrics["timestamp"],
                    "sharpe_1d": metrics["rolling_sharpe"]["1d"],
                    "sharpe_3d": metrics["rolling_sharpe"]["3d"],
                    "sharpe_7d": metrics["rolling_sharpe"]["7d"],
                    "win_rate_7d": metrics["win_rate_7d"],
                    "avg_pnl_7d": metrics["avg_pnl_7d"],
                    "total_trades": metrics["total_trades"],
                    "total_pnl": metrics["total_pnl"],
                    "decay_severity": metrics["decay_severity"],
                }
            ]
        )

        # Append to history
        if self.performance_file.exists():
            history = pd.read_csv(self.performance_file)
            history = pd.concat([history, row], ignore_index=True)
        else:
            history = row

        history.to_csv(self.performance_file, index=False)
        logger.info(f"Performance snapshot logged to {self.performance_file}")

    def get_decay_trend(self, days: int = 14) -> dict[str, Any]:
        """
        Analyze performance trend to predict decay.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with trend analysis
        """
        if not self.performance_file.exists():
            return {
                "trend": "UNKNOWN",
                "slope": 0.0,
                "days_to_threshold": None,
                "recommendation": "Insufficient data",
            }

        history = pd.read_csv(self.performance_file)

        # Filter to recent days
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        recent = history[history["timestamp"] >= cutoff]

        if len(recent) < 3:
            return {
                "trend": "UNKNOWN",
                "slope": 0.0,
                "days_to_threshold": None,
                "recommendation": "Insufficient data points",
            }

        # Linear regression on Sharpe 7d
        x = np.arange(len(recent))
        y = recent["sharpe_7d"].values
        slope, intercept = np.polyfit(x, y, 1)

        # Predict days until threshold
        current_sharpe = y[-1]
        if slope < 0:
            days_to_threshold = (self.sharpe_threshold - current_sharpe) / abs(slope)
            days_to_critical = (self.critical_threshold - current_sharpe) / abs(slope)
        else:
            days_to_threshold = None
            days_to_critical = None

        # Trend classification
        if slope < -0.1:
            trend = "DECLINING"
            recommendation = "Monitor closely, decay accelerating"
        elif slope < 0:
            trend = "DEGRADING"
            recommendation = "Normal decay, weekly re-opt should handle"
        elif slope > 0.1:
            trend = "IMPROVING"
            recommendation = "Parameters performing well"
        else:
            trend = "STABLE"
            recommendation = "Performance stable"

        return {
            "trend": trend,
            "slope": round(float(slope), 4),
            "current_sharpe": round(float(current_sharpe), 3),
            "days_to_warning": round(days_to_threshold, 1) if days_to_threshold else None,
            "days_to_critical": round(days_to_critical, 1) if days_to_critical else None,
            "recommendation": recommendation,
        }

    def should_trigger_reoptimization(self) -> tuple[bool, str]:
        """
        Determine if immediate re-optimization should be triggered.

        Returns:
            Tuple of (should_trigger, reason)
        """
        is_decaying, severity, sharpe = self.detect_decay()

        if severity == "CRITICAL":
            return True, f"Critical performance decay (Sharpe {sharpe:.3f} < {self.critical_threshold})"

        # Check trend
        trend = self.get_decay_trend()
        if trend["trend"] == "DECLINING" and trend.get("days_to_critical", 999) < 3:
            return (
                True,
                f"Rapid decline detected (Sharpe will reach critical in {trend['days_to_critical']:.1f} days)",
            )

        return False, "Performance acceptable"
