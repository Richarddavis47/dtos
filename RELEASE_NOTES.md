# DTOS v0.9.9 - Market Intelligence v1

DTOS v0.9.9 adds explainable external market evidence to the unified intelligence platform while keeping DTOS intrinsic values independent.

## Highlights

- Registers FantasyCalc, KeepTradeCut, Sleeper ADP, and DynastyProcess through replaceable provider adapters.
- Produces a robust consensus with provider coverage, agreement, dispersion, confidence, and explicit missing-provider handling.
- Keeps Intrinsic Value and Market Value separate and identifies explainable undervaluation, overvaluation, fair value, and uncertainty.
- Stores provider snapshots through a persistent-capable history interface and calculates trends, momentum, volatility, and confidence drift.
- Isolates provider cache entries by execution context and clearly distinguishes live data, fresh cache hits, cached fallback, and unavailable data.
- Adds transparent provider status, freshness, cache age, confidence impact, latency, availability, and cache health.
- Enriches player Market Value and Trade Dossiers without changing the responsibility of Decision, Asset, Trade, or Front Office Intelligence.
- Integrates market evidence only through the Intelligence Orchestrator and preserves existing API contracts.

## Metadata

- Application: DTOS
- Version: 0.9.9
- Build: 909
- Codename: Market Intelligence v1

## Intentional boundaries

- V1 consumes cached provider payloads and adds no new external network dependency.
- No market value is inferred from DTOS intrinsic value when provider data is unavailable.
- Market opportunity labels are evidence patterns, not automatic trade instructions.
- Front Office market behavior remains unchanged until sufficient observable history supports it.
- Provider-specific authentication and scheduled collection remain future extension points.
