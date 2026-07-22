# Live Data Platform

## Purpose

The Live Data Platform is DTOS's single boundary for external information. Intelligence engines consume standardized contracts and never depend on provider-specific APIs, cache layouts, authentication, or licensing assumptions.

## Architecture

`src/core/data_platform/` contains immutable contracts, the provider SDK, dynamic registry, refresh scheduler, namespace-aware cache, attributed snapshot warehouse, robust aggregation, historical trends, quality checks, structured news interpretation, and provider health.

The dependency direction is:

```text
Application → Intelligence Orchestrator → Intelligence Engines → Data Platform → Providers
```

Provider adapters implement `DataProvider.fetch()` and return `DataEnvelope`. A provider can be registered, disabled, or replaced without changing business logic.

## Envelope contract

Every external value carries its key, category, value, source, provider, timestamp, freshness, confidence, cache state, retrieval mode, data quality, and limitations. Unavailable values use the same contract.

## Fallback chain

The platform tries live data, fresh cache, an attributed historical snapshot, an explicitly labeled deterministic DTOS estimate when supplied, and finally unavailable. Each transition changes `retrieval_mode`, confidence, and limitations. No fallback is silent.

## Consensus and trends

Consensus preserves individual source envelopes and uses confidence-weighted, outlier-resistant aggregation rather than a simple average. It exposes variance, agreement, coverage-based confidence, bullish/bearish sources, and missing providers.

Trends expose absolute and percentage change, momentum, volatility, direction, and 7-day, 30-day, 90-day, one-year, and lifetime windows.

## Refresh and storage

Provider metadata supplies in-season and offseason intervals. Scheduled planning and on-demand refresh are independent. Snapshots are de-duplicated by key, provider, category, and timestamp and written atomically to `DTOS_DATA_WAREHOUSE_FILE`.

## Licensing

Every provider declares Public API, User API Key Required, Licensed Commercial Data, Partner Integration, or Unsupported. Deployment configuration can disable providers independently. A disabled provider remains visible in health and never blocks cached DTOS operation.

## Provider catalog

Sleeper league/transaction transport and existing cached FantasyCalc, KeepTradeCut, Sleeper ADP, and DynastyProcess-compatible values are platform-managed. Other requested providers are registered with honest disabled or unavailable states until an approved API and licensing configuration exists. DTOS does not scrape unsupported sources.

## Extension guide

Add a provider by implementing `DataProvider`, declaring complete `ProviderMetadata`, registering it during platform construction, and adding contract tests for live, failure, fallback, quality, licensing, and deterministic behavior. No intelligence-engine changes should be required.
