# Market Provider Guide

Market providers implement `MarketProvider._extract()` and return traceable value, confidence, observation time, and detail through the shared quote contract. Register an adapter with `MarketProviderRegistry`; do not change the Intelligence Orchestrator for each source.

A provider must be independent, cache-aware, deterministic for a given payload, explicit when unavailable, and free of hidden valuation inference. Normalize source values to the documented DTOS 0–100 market scale before consensus. Preserve source and observation timestamps.

Provider cache keys include league/Front Office namespace, provider version, provider, and asset. Offline mode never silently reuses online values. Explicit fallback must disclose `cached_fallback`, age, freshness, availability, and confidence penalty. Provider failures reduce coverage and confidence without blocking other providers.

Add tests for valid, malformed, missing, stale, recovering, and disagreeing responses. Never log credentials or raw authorization headers. Current v1 adapters consume cached FantasyCalc, KeepTradeCut, Sleeper ADP, and DynastyProcess fields and perform no new external network calls.
# Valuation provider abstraction (v1.7.0)

The valuation API presents DTOS, KTC, FantasyCalc, and DynastyProcess through one neutral contract: raw value, normalized value, rank, update time, confidence, availability, reason, and source version. Missing or unlicensed providers remain explicit. Provider absence never causes DTOS to invent market evidence.
