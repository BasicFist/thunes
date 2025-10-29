"""Tests for optimization parameter utility helpers."""

from __future__ import annotations

from optuna.trial import FixedTrial

from src.backtest.strategy import SMAStrategy
from src.optimize.parameter_utils import (
    build_strategy_kwargs,
    get_tunable_specs,
    suggest_parameters,
    validate_constraints,
)
from src.strategies.loader import ensure_strategies_loaded

ensure_strategies_loaded()


def test_get_tunable_specs_contains_sma_windows():
    metadata = SMAStrategy.metadata
    specs = get_tunable_specs(metadata)
    assert "fast_window" in specs
    assert "slow_window" in specs
    assert specs["fast_window"]["min"] == 5
    assert specs["slow_window"]["max"] == 250


def test_suggest_parameters_with_fixed_trial():
    metadata = SMAStrategy.metadata
    specs = get_tunable_specs(metadata)
    trial = FixedTrial({"fast_window": 15, "slow_window": 60})
    params = suggest_parameters(trial, specs)
    assert params["fast_window"] == 15
    assert params["slow_window"] == 60


def test_build_strategy_kwargs_applies_defaults():
    metadata = SMAStrategy.metadata
    sampled = {"fast_window": 12, "slow_window": 48}
    kwargs = build_strategy_kwargs(metadata, timeframe="4h", sampled=sampled)
    assert kwargs["fast_window"] == 12
    assert kwargs["slow_window"] == 48
    assert kwargs["freq"] == "4h"


def test_validate_constraints_success_and_failure():
    metadata = SMAStrategy.metadata
    valid_params = {"fast_window": 20, "slow_window": 60, "freq": "1h"}
    assert validate_constraints(valid_params, metadata.parameters)

    invalid_params = {"fast_window": 80, "slow_window": 40, "freq": "1h"}
    assert not validate_constraints(invalid_params, metadata.parameters)
