"""Shared utilities for strategy hyperparameter optimization."""

from __future__ import annotations

from typing import Any

from optuna.trial import Trial

from src.strategies import StrategyMetadata


def get_tunable_specs(metadata: StrategyMetadata) -> dict[str, dict[str, Any]]:
    """Return parameter specs that have tunable ranges."""
    tunable: dict[str, dict[str, Any]] = {}
    for name, spec in metadata.parameters.items():
        if isinstance(spec, dict) and "min" in spec and "max" in spec:
            tunable[name] = spec
    return tunable


def suggest_parameters(trial: Trial, specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Sample parameter values for tunable specs using Optuna trial."""
    params: dict[str, Any] = {}
    for name, spec in specs.items():
        param_type = spec.get("type")
        minimum = spec["min"]
        maximum = spec["max"]

        if param_type == "int":
            params[name] = trial.suggest_int(name, int(minimum), int(maximum))
        elif param_type == "float":
            step = spec.get("step")
            log = spec.get("log", False)
            if step is not None:
                params[name] = trial.suggest_float(
                    name, float(minimum), float(maximum), step=float(step)
                )
            else:
                params[name] = trial.suggest_float(
                    name, float(minimum), float(maximum), log=bool(log)
                )
        else:
            raise ValueError(f"Unsupported parameter type '{param_type}' for {name}")
    return params


def build_strategy_kwargs(
    metadata: StrategyMetadata,
    timeframe: str,
    sampled: dict[str, Any],
    *,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge sampled values with defaults and overrides to build constructor kwargs."""
    kwargs: dict[str, Any] = {}
    overrides = overrides or {}

    for name, spec in metadata.parameters.items():
        if name in overrides:
            kwargs[name] = overrides[name]
        elif name in sampled:
            kwargs[name] = sampled[name]
        elif name == "freq":
            kwargs[name] = timeframe
        elif "default" in spec:
            kwargs[name] = spec["default"]

    if "freq" not in kwargs:
        kwargs["freq"] = timeframe

    return kwargs


def validate_constraints(
    all_params: dict[str, Any], metadata_params: dict[str, dict[str, Any]]
) -> bool:
    """Validate relational constraints declared in metadata."""
    for name, spec in metadata_params.items():
        if not isinstance(spec, dict):
            continue

        if "less_than" in spec:
            other = spec["less_than"]
            if name in all_params and other in all_params:
                if not all_params[name] < all_params[other]:
                    return False

        if "greater_than" in spec:
            other = spec["greater_than"]
            if name in all_params and other in all_params:
                if not all_params[name] > all_params[other]:
                    return False

        if "less_than_equal" in spec:
            other = spec["less_than_equal"]
            if name in all_params and other in all_params:
                if not all_params[name] <= all_params[other]:
                    return False

        if "greater_than_equal" in spec:
            other = spec["greater_than_equal"]
            if name in all_params and other in all_params:
                if not all_params[name] >= all_params[other]:
                    return False

    return True
