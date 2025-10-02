"""Market regime detection using Hidden Markov Models.

Based on IMPLEMENTATION-ROADMAP.md Tier 1 recommendation (6 hours, ⭐⭐⭐⭐).
HMM outperforms clustering for regime detection (2024-2025 research).
"""


import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class MarketRegimeDetector:
    """
    Hidden Markov Model for market regime detection.

    States:
        0 = Bear/High-Volatility regime
        1 = Bull/Low-Volatility regime

    Features:
        - 1-day returns (momentum)
        - 5-day returns (short-term trend)
        - 20-day rolling volatility (risk)

    Based on 2024-2025 research showing HMM superiority over K-means clustering.
    """

    def __init__(self, n_states: int = 2, random_state: int = 42):
        """
        Initialize HMM regime detector.

        Args:
            n_states: Number of market regimes (default: 2)
            random_state: Random seed for reproducibility
        """
        self.n_states = n_states
        self.model = GaussianHMM(
            n_components=n_states,
            covariance_type="full",
            n_iter=100,
            random_state=random_state,
        )
        self.is_fitted = False
        self.feature_names = ["return_1d", "return_5d", "volatility_20d"]

        logger.info(f"MarketRegimeDetector initialized with {n_states} states")

    def _prepare_features(self, returns: pd.Series, volatility: pd.Series = None) -> pd.DataFrame:
        """
        Prepare feature matrix for HMM.

        Args:
            returns: Daily returns series
            volatility: Pre-calculated volatility (optional)

        Returns:
            DataFrame with regime detection features
        """
        # Calculate features
        features = pd.DataFrame(index=returns.index)
        features["return_1d"] = returns
        features["return_5d"] = returns.rolling(5).sum()

        if volatility is None:
            # Calculate 20-day rolling volatility
            features["volatility_20d"] = returns.rolling(20).std()
        else:
            features["volatility_20d"] = volatility

        # Drop NaN rows (from rolling calculations)
        features = features.dropna()

        logger.debug(f"Prepared {len(features)} samples with {len(self.feature_names)} features")
        return features

    def fit(self, returns: pd.Series, volatility: pd.Series = None) -> "MarketRegimeDetector":
        """
        Fit HMM to historical data.

        Args:
            returns: Daily returns series
            volatility: Pre-calculated volatility (optional)

        Returns:
            Self (fitted detector)
        """
        X = self._prepare_features(returns, volatility)

        logger.info(f"Fitting HMM on {len(X)} samples...")
        self.model.fit(X.values)
        self.is_fitted = True

        # Analyze fitted regimes
        regimes = self.model.predict(X.values)
        stats = self.get_regime_statistics(returns, regimes)

        logger.info("HMM training complete:")
        for regime_id, regime_stats in stats.items():
            logger.info(
                f"  Regime {regime_id}: "
                f"mean_return={regime_stats['mean_return']:.4f}, "
                f"volatility={regime_stats['volatility']:.4f}, "
                f"frequency={regime_stats['frequency']:.2%}"
            )

        return self

    def predict(self, returns: pd.Series, volatility: pd.Series = None) -> np.ndarray:
        """
        Predict regime sequence for historical data.

        Args:
            returns: Daily returns series
            volatility: Pre-calculated volatility (optional)

        Returns:
            Array of regime labels (0 or 1)
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        X = self._prepare_features(returns, volatility)
        regimes = self.model.predict(X.values)

        logger.debug(f"Predicted {len(regimes)} regime labels")
        return regimes

    def predict_current_regime(
        self, recent_returns: pd.Series, recent_volatility: pd.Series = None
    ) -> int:
        """
        Predict current market regime.

        Args:
            recent_returns: Recent returns series (at least 20 days for volatility)
            recent_volatility: Pre-calculated volatility (optional)

        Returns:
            Current regime state (0=bear/high_vol, 1=bull/low_vol)
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        X = self._prepare_features(recent_returns, recent_volatility)

        if len(X) == 0:
            raise ValueError("Insufficient data for regime prediction (need at least 20 days)")

        regime = self.model.predict(X.values)
        current_regime = regime[-1]  # Most recent regime

        logger.debug(f"Current regime: {current_regime}")
        return int(current_regime)

    def get_regime_statistics(
        self, returns: pd.Series, regimes: np.ndarray
    ) -> dict[int, dict[str, float]]:
        """
        Calculate statistics per regime.

        Args:
            returns: Returns series
            regimes: Regime labels array

        Returns:
            Dictionary of regime statistics
        """
        stats = {}

        for regime_id in range(self.n_states):
            mask = regimes == regime_id
            regime_returns = returns.iloc[: len(regimes)][mask]

            if len(regime_returns) > 0:
                mean_return = regime_returns.mean()
                volatility = regime_returns.std()
                sharpe = (mean_return / volatility * np.sqrt(252)) if volatility > 0 else 0.0

                stats[regime_id] = {
                    "mean_return": mean_return,
                    "volatility": volatility,
                    "sharpe": sharpe,
                    "frequency": mask.sum() / len(regimes),
                    "total_samples": mask.sum(),
                }
            else:
                stats[regime_id] = {
                    "mean_return": 0.0,
                    "volatility": 0.0,
                    "sharpe": 0.0,
                    "frequency": 0.0,
                    "total_samples": 0,
                }

        return stats

    def get_regime_transitions(self, regimes: np.ndarray) -> pd.DataFrame:
        """
        Analyze regime transition patterns.

        Args:
            regimes: Regime labels array

        Returns:
            Transition matrix as DataFrame
        """
        transitions = np.zeros((self.n_states, self.n_states))

        for i in range(len(regimes) - 1):
            from_regime = regimes[i]
            to_regime = regimes[i + 1]
            transitions[from_regime, to_regime] += 1

        # Normalize to probabilities
        row_sums = transitions.sum(axis=1, keepdims=True)
        transition_probs = np.divide(
            transitions, row_sums, where=row_sums != 0, out=np.zeros_like(transitions)
        )

        df = pd.DataFrame(
            transition_probs,
            index=[f"Regime {i}" for i in range(self.n_states)],
            columns=[f"→ Regime {i}" for i in range(self.n_states)],
        )

        logger.info("Regime transition probabilities:")
        logger.info(f"\n{df}")

        return df
