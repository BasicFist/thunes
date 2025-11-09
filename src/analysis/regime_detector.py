"""
Market Regime Detection for Adaptive Trading.

Classifies market conditions into regimes:
- TRENDING (directional moves)
- RANGING (sideways consolidation)
- VOLATILE (high uncertainty)
- QUIET (low volatility)

Different strategies perform better in different regimes.
Regime-aware trading significantly improves risk-adjusted returns.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class MarketRegime(Enum):
    """Market regime classification."""

    TRENDING_UP = "TRENDING_UP"  # Strong uptrend
    TRENDING_DOWN = "TRENDING_DOWN"  # Strong downtrend
    RANGING = "RANGING"  # Sideways/choppy
    VOLATILE = "VOLATILE"  # High volatility, no clear direction
    QUIET = "QUIET"  # Low volatility, low volume
    UNKNOWN = "UNKNOWN"  # Insufficient data


@dataclass
class RegimeAnalysis:
    """Results of regime detection."""

    regime: MarketRegime
    confidence: float  # 0-1
    trend_strength: float  # -1 to +1 (negative = down, positive = up)
    volatility_percentile: float  # 0-100
    adx: Optional[float] = None  # Average Directional Index
    recommended_strategy: str = "NONE"
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class RegimeDetector:
    """
    Detect market regimes using multiple technical indicators.

    Combines:
    - ADX (Average Directional Index) for trend strength
    - ATR (Average True Range) for volatility
    - Price action patterns
    - Volume analysis
    """

    def __init__(
        self,
        adx_period: int = 14,
        atr_period: int = 14,
        vol_lookback: int = 20,
        trending_threshold: float = 25,  # ADX > 25 = trending
        ranging_threshold: float = 20,  # ADX < 20 = ranging
    ):
        """
        Initialize regime detector.

        Args:
            adx_period: Period for ADX calculation
            atr_period: Period for ATR calculation
            vol_lookback: Lookback for volatility percentile
            trending_threshold: ADX threshold for trending market
            ranging_threshold: ADX threshold for ranging market
        """
        self.adx_period = adx_period
        self.atr_period = atr_period
        self.vol_lookback = vol_lookback
        self.trending_threshold = trending_threshold
        self.ranging_threshold = ranging_threshold

        logger.info(f"RegimeDetector initialized: ADX={adx_period}, ATR={atr_period}")

    def calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """
        Calculate Average Directional Index (ADX).

        ADX measures trend strength:
        - 0-20: Weak trend (ranging)
        - 20-40: Moderate trend
        - 40+: Strong trend

        Args:
            high: High prices
            low: Low prices
            close: Close prices

        Returns:
            ADX values (Series)
        """
        period = self.adx_period

        # Calculate +DM and -DM
        high_diff = high.diff()
        low_diff = -low.diff()

        plus_dm = pd.Series(0.0, index=high.index)
        minus_dm = pd.Series(0.0, index=high.index)

        plus_dm[high_diff > low_diff] = high_diff[high_diff > low_diff]
        minus_dm[low_diff > high_diff] = low_diff[low_diff > high_diff]

        # Calculate True Range (TR)
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Smooth with Wilder's smoothing
        atr = tr.ewm(alpha=1 / period, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr

        # Calculate DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(alpha=1 / period, adjust=False).mean()

        return adx

    def calculate_trend_strength(self, close: pd.Series) -> float:
        """
        Calculate trend strength using linear regression slope.

        Args:
            close: Close prices

        Returns:
            Trend strength (-1 to +1)
        """
        if len(close) < 20:
            return 0.0

        # Use recent 20 periods
        recent_close = close.tail(20).values
        x = np.arange(len(recent_close))

        # Linear regression
        slope, _ = np.polyfit(x, recent_close, 1)

        # Normalize by average price
        avg_price = recent_close.mean()
        normalized_slope = slope / avg_price if avg_price > 0 else 0

        # Clip to -1, +1
        trend_strength = max(-1, min(1, normalized_slope * 100))

        return trend_strength

    def calculate_volatility_percentile(
        self,
        close: pd.Series,
        lookback: Optional[int] = None,
    ) -> float:
        """
        Calculate current volatility percentile.

        Args:
            close: Close prices
            lookback: Lookback period (defaults to self.vol_lookback)

        Returns:
            Volatility percentile (0-100)
        """
        if lookback is None:
            lookback = self.vol_lookback

        if len(close) < lookback:
            return 50.0  # Neutral if insufficient data

        # Calculate rolling volatility
        returns = close.pct_change()
        vol = returns.rolling(window=14).std()

        # Get current volatility
        current_vol = vol.iloc[-1]

        # Calculate percentile
        recent_vol = vol.tail(lookback)
        percentile = (recent_vol < current_vol).sum() / len(recent_vol) * 100

        return percentile

    def detect_regime(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: Optional[pd.Series] = None,
    ) -> RegimeAnalysis:
        """
        Detect current market regime.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume data (optional)

        Returns:
            RegimeAnalysis with detected regime and metrics
        """
        if len(close) < 50:
            logger.warning("Insufficient data for regime detection (<50 bars)")
            return RegimeAnalysis(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                trend_strength=0.0,
                volatility_percentile=50.0,
                recommended_strategy="NONE",
            )

        # Calculate indicators
        adx = self.calculate_adx(high, low, close)
        current_adx = adx.iloc[-1]

        trend_strength = self.calculate_trend_strength(close)
        vol_percentile = self.calculate_volatility_percentile(close)

        # Determine regime
        regime = MarketRegime.UNKNOWN
        confidence = 0.0
        recommended_strategy = "NONE"

        # High volatility regime
        if vol_percentile > 80:
            regime = MarketRegime.VOLATILE
            confidence = (vol_percentile - 80) / 20  # 0-1
            recommended_strategy = "AVOID"  # Too risky

        # Low volatility regime
        elif vol_percentile < 20:
            regime = MarketRegime.QUIET
            confidence = (20 - vol_percentile) / 20  # 0-1
            recommended_strategy = "BREAKOUT"  # Wait for expansion

        # Trending regime
        elif current_adx > self.trending_threshold:
            if trend_strength > 0.3:
                regime = MarketRegime.TRENDING_UP
                recommended_strategy = "TREND_FOLLOWING"
            elif trend_strength < -0.3:
                regime = MarketRegime.TRENDING_DOWN
                recommended_strategy = "TREND_FOLLOWING"
            else:
                regime = MarketRegime.VOLATILE
                recommended_strategy = "AVOID"

            confidence = min(1.0, (current_adx - self.trending_threshold) / 20)

        # Ranging regime
        elif current_adx < self.ranging_threshold:
            regime = MarketRegime.RANGING
            confidence = (self.ranging_threshold - current_adx) / self.ranging_threshold
            recommended_strategy = "MEAN_REVERSION"

        # Transitional regime (between trending and ranging)
        else:
            regime = MarketRegime.RANGING
            confidence = 0.5
            recommended_strategy = "CAUTIOUS"

        result = RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility_percentile=vol_percentile,
            adx=current_adx,
            recommended_strategy=recommended_strategy,
        )

        logger.info(
            f"Regime detected: {regime.value} (confidence={confidence:.2f}) | "
            f"ADX={current_adx:.1f}, Trend={trend_strength:+.2f}, "
            f"Vol Percentile={vol_percentile:.0f}% | "
            f"Strategy: {recommended_strategy}"
        )

        return result

    def should_trade(
        self,
        regime_analysis: RegimeAnalysis,
        strategy_type: str = "TREND_FOLLOWING",
        min_confidence: float = 0.5,
    ) -> tuple[bool, str]:
        """
        Determine if trading is recommended given regime and strategy.

        Args:
            regime_analysis: Current regime analysis
            strategy_type: Strategy being used
            min_confidence: Minimum confidence threshold

        Returns:
            (should_trade, reason)
        """
        # Never trade in volatile or quiet regimes with low confidence
        if regime_analysis.regime in [MarketRegime.VOLATILE, MarketRegime.UNKNOWN]:
            return False, "Market regime is too volatile or unknown"

        if regime_analysis.regime == MarketRegime.QUIET and regime_analysis.confidence > 0.7:
            return False, "Market is too quiet (low volatility)"

        # Check confidence threshold
        if regime_analysis.confidence < min_confidence:
            return False, f"Regime confidence {regime_analysis.confidence:.2f} < {min_confidence}"

        # Match strategy to regime
        if strategy_type == "TREND_FOLLOWING":
            if regime_analysis.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
                return True, f"Trending market suitable for trend following"
            else:
                return False, "Non-trending market, trend following not recommended"

        elif strategy_type == "MEAN_REVERSION":
            if regime_analysis.regime == MarketRegime.RANGING:
                return True, "Ranging market suitable for mean reversion"
            else:
                return False, "Trending market, mean reversion risky"

        # Default: Conservative approach
        if regime_analysis.recommended_strategy == "AVOID":
            return False, "Current regime not suitable for trading"

        return True, "Market regime acceptable for trading"
