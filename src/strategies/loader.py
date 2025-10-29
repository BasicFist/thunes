"""Helpers to load strategy plugins dynamically."""

from __future__ import annotations

from collections.abc import Iterable
from importlib import import_module
from pathlib import Path


def ensure_strategies_loaded(extra_modules: Iterable[str] | None = None) -> None:
    """Import strategy modules so decorators register them."""

    backtest_dir = Path(__file__).resolve().parent.parent / "backtest"
    for path in backtest_dir.glob("*.py"):
        if path.name.startswith("__"):
            continue
        module_name = f"src.backtest.{path.stem}"
        import_module(module_name)

    default_plugins = [
        "src.strategies.nlp.sentiment_lm",
    ]

    for module_name in default_plugins:
        import_module(module_name)

    if extra_modules:
        for module_name in extra_modules:
            import_module(module_name)
