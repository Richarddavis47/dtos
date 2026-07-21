"""Replaceable registry for external market adapters."""
from __future__ import annotations

from src.core.market_intelligence.providers.base import MarketProvider


class MarketProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, MarketProvider] = {}

    def register(self, provider: MarketProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"Market provider {provider.name!r} is already registered.")
        self._providers[provider.name] = provider

    def providers(self) -> tuple[MarketProvider, ...]:
        return tuple(self._providers.values())

    def names(self) -> tuple[str, ...]:
        return tuple(self._providers)


def default_market_registry() -> MarketProviderRegistry:
    from src.core.market_intelligence.providers.dynastyprocess import DynastyProcessProvider
    from src.core.market_intelligence.providers.fantasycalc import FantasyCalcProvider
    from src.core.market_intelligence.providers.keeptradecut import KeepTradeCutProvider
    from src.core.market_intelligence.providers.sleeper import SleeperAdpProvider

    registry = MarketProviderRegistry()
    for provider in (FantasyCalcProvider(), KeepTradeCutProvider(), SleeperAdpProvider(), DynastyProcessProvider()):
        registry.register(provider)
    return registry
