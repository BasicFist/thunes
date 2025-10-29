"""Sentiment-driven strategy using a Hugging Face sentiment pipeline."""

from __future__ import annotations

import pandas as pd
import vectorbt as vbt
from transformers import pipeline

from src.strategies import BaseStrategy, StrategyMetadata, register_strategy
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@register_strategy(aliases=("sentiment_lm",))
class HFsentimentStrategy(BaseStrategy):
    """Generate trading signals from HF sentiment scores."""

    metadata = StrategyMetadata(
        name="SENTIMENT_LM",
        description="Sentiment analysis using distilbert-base-uncased-finetuned-sst-2-english.",
        parameters={
            "model_id": {
                "type": "str",
                "default": "distilbert-base-uncased-finetuned-sst-2-english",
            },
            "lookback": {
                "type": "int",
                "default": 24,
                "min": 6,
                "max": 168,
            },
            "bullish_threshold": {
                "type": "float",
                "default": 0.65,
                "min": 0.5,
                "max": 0.95,
                "step": 0.05,
                "greater_than": "bearish_threshold",
            },
            "bearish_threshold": {
                "type": "float",
                "default": 0.35,
                "min": 0.05,
                "max": 0.5,
                "step": 0.05,
                "less_than": "bullish_threshold",
            },
            "freq": {"type": "str", "default": "1h"},
        },
    )

    def __init__(
        self,
        model_id: str = "distilbert-base-uncased-finetuned-sst-2-english",
        lookback: int = 24,
        bullish_threshold: float = 0.65,
        bearish_threshold: float = 0.35,
        freq: str = "1h",
    ) -> None:
        super().__init__(
            model_id=model_id,
            lookback=lookback,
            bullish_threshold=bullish_threshold,
            bearish_threshold=bearish_threshold,
            freq=freq,
        )
        self.model_id = model_id
        self.lookback = lookback
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold
        self.freq = freq

        try:
            self.pipeline = pipeline("sentiment-analysis", model=model_id, device="cpu")
            logger.info("Loaded sentiment model %s", model_id)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to load sentiment model %s: %s", model_id, exc)
            raise

    def _score_sentiment(self, closes: pd.Series) -> float:
        texts = [f"Price {price:.2f}" for price in closes.tail(self.lookback)]
        outputs = self.pipeline(texts, truncation=True)
        positive_scores = [item["score"] for item in outputs if item["label"].upper() == "POSITIVE"]
        if not positive_scores:
            return 0.0
        return float(sum(positive_scores) / len(positive_scores))

    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        entries = pd.Series(False, index=df.index)
        exits = pd.Series(False, index=df.index)

        score = self._score_sentiment(df["close"])
        if score >= self.bullish_threshold:
            entries.iloc[-1] = True
        elif score <= self.bearish_threshold:
            exits.iloc[-1] = True

        logger.info(
            "Sentiment score %.3f (entry=%s exit=%s)",
            score,
            entries.iloc[-1],
            exits.iloc[-1],
        )

        return entries, exits

    def backtest(
        self,
        df: pd.DataFrame,
        initial_capital: float = 10000.0,
        fees: float = 0.001,
        slippage: float = 0.0005,
    ) -> vbt.Portfolio:
        entries, exits = self.generate_signals(df)
        price = df["close"] * (1 + slippage)
        return vbt.Portfolio.from_signals(
            close=price,
            entries=entries,
            exits=exits,
            init_cash=initial_capital,
            fees=fees,
            freq=self.freq,
        )
