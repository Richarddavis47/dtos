# Market Intelligence v1

## Purpose

Market Intelligence measures observable dynasty-market opinion without replacing DTOS intrinsic evaluation. It supplies evidence to the Intelligence Orchestrator, which remains the only application-level recommendation boundary.

Intrinsic Value answers what DTOS believes an asset is worth from football, league, and Front Office context. Market Value answers what traceable providers currently report. A difference is a possible opportunity that still requires contextual Decision, Asset, Trade, and Front Office evidence.

## Architecture

```text
Cached provider payloads
        |
        v
Provider Registry -> Cache/Fallback -> Robust Consensus
                                          |
History Store -> Trend/Volatility --------+
                                          |
DTOS Intrinsic Value -> Value Gap --------+
                                          |
Evidence + Opportunities + Trade Impact
                                          |
Intelligence Orchestrator
```

`src/core/market_intelligence/` contains independent providers, aggregation, history, trends, evidence, models, cache, and orchestration. Application services never call this package directly.

## Providers and registry

FantasyCalc, KeepTradeCut, Sleeper ADP, and DynastyProcess adapters implement one `MarketProvider` contract and register with `MarketProviderRegistry`. Adapters read traceable cached inputs and return explicit unavailable quotes when no data exists. Adding a provider requires registering another adapter; the Intelligence Orchestrator does not change.

No provider value is inferred from DTOS intrinsic value. V1 performs no new external network calls, so existing Sleeper synchronization and cached operation remain unchanged.

## Consensus algorithm

The consensus engine:

1. Excludes unavailable and malformed quotes.
2. Finds the median provider value.
3. Weights each quote by provider confidence and its distance from that median.
4. Calculates dispersion and converts it into an agreement score.
5. Combines provider confidence, agreement, and provider coverage into Market Confidence.

This bounded weighting allows outliers to lower agreement and confidence without dominating the consensus. Missing providers remain listed in the public contract.

## Value-gap model

Intrinsic and market values remain independent. The engine reports their signed difference and percentage:

- `Undervalued` when intrinsic value exceeds consensus by at least 12%.
- `Overvalued` when consensus exceeds intrinsic value by at least 12%.
- `Fairly Valued` inside that boundary.
- `High Uncertainty` when consensus is missing or Market Confidence is below 35.

Opportunity labels such as Buy Low, Sell High, and Acquire Before Value Rises describe evidence patterns. They never force a transaction or override contextual recommendations.

## Trend engine and historical storage

`MarketHistoryStore` keeps timestamped provider snapshots and supports optional atomic JSON persistence. Trend calculations expose 7-day, 30-day, season, and career changes, plus direction, momentum, normalized volatility, and confidence drift. Insufficient history returns explicit unavailable periods rather than fabricated movement.

## Cache and offline contract

Provider entries are isolated by league/Front Office namespace, provider version, provider, and asset. Execution mode is explicit:

- `live`: a currently available provider quote.
- `cache_hit`: a fresh entry reused inside an online execution context.
- `cached_fallback`: an intentionally enabled snapshot used while its provider is unavailable; confidence is reduced.
- `unavailable`: no permitted provider value exists.

Ordinary offline execution cannot inherit online consensus. Cached fallback must be enabled explicitly and must satisfy the configured maximum age. Evidence and health output disclose provider status, retrieval mode, freshness, cache age, and confidence impact.

## Integration

Market Intelligence runs after existing domain providers, enriches player Market Value when consensus exists, attaches Market Impact to Trade Dossiers, contributes evidence to unified recommendations, and reports provider/cache health through `/api/platform/health`. `/api/intelligence` adds a backward-compatible `market` object.

Market evidence can affect timing, confidence, and counterarguments. It cannot replace Asset Intelligence values, decide a trade alone, or infer unsupported Front Office behavior.

## Extension points

Future work can add authenticated provider clients, scheduled snapshots, draft-pick provider mappings, database-backed history, provider-specific normalization, and richer market timing without changing application services or the orchestrator boundary.
