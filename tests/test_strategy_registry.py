"""Tests for strategy plugin registry."""

from __future__ import annotations

import pytest

from src.strategies import BaseStrategy, StrategyMetadata, strategy_registry
from src.strategies.loader import ensure_strategies_loaded

ensure_strategies_loaded()


class DummyStrategy(BaseStrategy):
    """Minimal strategy for registry tests."""

    metadata = StrategyMetadata(
        name="dummy",
        description="Test strategy",
        parameters={"foo": {"type": "int", "default": 1}},
    )

    def generate_signals(self, df):
        raise NotImplementedError

    def backtest(self, df, initial_capital=10000.0, fees=0.001, slippage=0.0005):
        raise NotImplementedError


def _clear_dummy(registry):
    registry._registry.pop("dummy", None)
    registry._registry.pop("dummyalias", None)


def test_registry_register_and_retrieve(monkeypatch):
    registry = strategy_registry
    _clear_dummy(registry)

    registry.register(DummyStrategy, aliases=("DummyAlias",))

    cls = registry.get("dummy")
    assert cls is DummyStrategy

    cls_alias = registry.get("dummyalias")
    assert cls_alias is DummyStrategy


def test_registry_duplicate_registration(monkeypatch):
    registry = strategy_registry
    _clear_dummy(registry)
    registry.register(DummyStrategy)

    with pytest.raises(ValueError):
        registry.register(DummyStrategy)


def test_registry_create_instance(monkeypatch):
    registry = strategy_registry
    _clear_dummy(registry)
    registry.register(DummyStrategy)

    instance = registry.create("dummy", foo=2)
    assert isinstance(instance, DummyStrategy)
    assert instance.parameters["foo"] == 2


def test_registry_available(monkeypatch):
    registry = strategy_registry
    _clear_dummy(registry)
    registry.register(DummyStrategy, aliases=("DummyAlias",))
    available = registry.available()
    assert "dummy" in available
    assert "sentiment_lm" in registry.available()


def test_built_in_sentiment_strategy_loaded(monkeypatch):
    calls: list[list[str]] = []

    def fake_pipeline(*args, **kwargs):
        def _inner(texts, truncation=False):  # noqa: ARG001
            calls.append(texts)
            return [{"label": "POSITIVE", "score": 0.8} for _ in texts]

        return _inner

    monkeypatch.setattr("src.strategies.nlp.sentiment_lm.pipeline", fake_pipeline)

    strategy_cls = strategy_registry.get("sentiment_lm")
    strategy = strategy_cls(lookback=6)
    assert strategy.metadata.name == "SENTIMENT_LM"
    assert strategy.pipeline(["hello"])  # ensure pipeline substituted
    assert calls


def test_registry_missing_strategy(monkeypatch):
    registry = strategy_registry
    _clear_dummy(registry)

    with pytest.raises(KeyError):
        registry.get("unknown")


def test_register_missing_metadata(monkeypatch):
    class NoMetadataStrategy(BaseStrategy):  # type: ignore
        def generate_signals(self, df):
            raise NotImplementedError

        def backtest(self, df, initial_capital=10000.0, fees=0.001, slippage=0.0005):
            raise NotImplementedError

    registry = strategy_registry
    with pytest.raises(AttributeError):
        registry.register(NoMetadataStrategy)
