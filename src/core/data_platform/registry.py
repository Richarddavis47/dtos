"""Dynamic, configuration-aware data provider registry."""
from __future__ import annotations

from src.core.data_platform.provider import DataProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, DataProvider] = {}

    def register(self, provider: DataProvider) -> None:
        if provider.metadata.name in self._providers:
            raise ValueError(f"Data provider {provider.metadata.name!r} is already registered.")
        self._providers[provider.metadata.name] = provider

    def provider(self, name: str) -> DataProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise KeyError(f"Data provider {name!r} is not registered.") from exc

    def providers(self, category: str | None = None, *, enabled_only: bool = False) -> tuple[DataProvider, ...]:
        return tuple(provider for provider in self._providers.values() if (category is None or provider.metadata.category == category) and (not enabled_only or provider.metadata.enabled))

    def names(self, category: str | None = None) -> tuple[str, ...]:
        return tuple(provider.metadata.name for provider in self.providers(category))

    def set_enabled(self, name: str, enabled: bool) -> None:
        provider = self.provider(name)
        object.__setattr__(provider.metadata, "enabled", enabled)
