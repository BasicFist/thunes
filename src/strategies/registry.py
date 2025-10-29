"""Strategy registry for plugin discovery and lookup."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .base import BaseStrategy


@dataclass(slots=True)
class StrategyEntry:
    """Holds strategy class and optional aliases."""

    cls: type[BaseStrategy]
    aliases: tuple[str, ...] = ()


class StrategyRegistry:
    """Register and instantiate strategy plugins."""

    def __init__(self) -> None:
        self._registry: dict[str, StrategyEntry] = {}

    def register(
        self,
        cls: type[BaseStrategy],
        *,
        aliases: Iterable[str] | None = None,
    ) -> None:
        """Register a strategy class with id + aliases."""
        if not hasattr(cls, "metadata"):
            raise AttributeError(f"Strategy {cls.__name__} missing metadata definition.")
        entry = StrategyEntry(cls=cls, aliases=tuple(aliases or ()))
        identifiers = {cls.metadata.name.lower()}  # type: ignore[attr-defined]
        identifiers.update(alias.lower() for alias in entry.aliases)

        for identifier in identifiers:
            if identifier in self._registry:
                raise ValueError(f"Strategy '{identifier}' already registered.")
            self._registry[identifier] = entry

    def get(self, name: str) -> type[BaseStrategy]:
        """Return strategy class for identifier."""
        key = name.lower()
        if key not in self._registry:
            raise KeyError(f"Strategy '{name}' not found.")
        return self._registry[key].cls

    def available(self) -> list[str]:
        """List canonical registered strategy ids (lowercase)."""
        return sorted({entry.cls.metadata.name.lower() for entry in self._registry.values()})

    def create(self, name: str, **kwargs) -> BaseStrategy:
        """Instantiate strategy by id with kwargs."""
        strategy_cls = self.get(name)
        return strategy_cls(**kwargs)


strategy_registry = StrategyRegistry()


def register_strategy(
    *,
    aliases: Iterable[str] | None = None,
) -> Callable[[type[BaseStrategy]], type[BaseStrategy]]:
    """Decorator for registering strategy classes."""

    def decorator(cls: type[BaseStrategy]) -> type[BaseStrategy]:
        strategy_registry.register(cls, aliases=aliases)
        return cls

    return decorator
