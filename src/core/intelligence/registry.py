"""Small provider registry for intelligence plug-ins."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


class IntelligenceRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, provider: Callable[..., Any]) -> None:
        if name in self._providers:
            raise ValueError(f"Intelligence provider {name!r} is already registered.")
        self._providers[name] = provider

    def provider(self, name: str) -> Callable[..., Any]:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise KeyError(f"Intelligence provider {name!r} is not registered.") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(self._providers)


intelligence_registry = IntelligenceRegistry()
