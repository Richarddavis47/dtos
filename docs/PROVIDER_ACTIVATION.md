# Provider Activation Guide

## Rules

Activate a provider only when DTOS has a documented public API or approved licensed integration. Never scrape an unsupported source, invent a value, or hide a fallback. Every activation must declare licensing, refresh support, attribution, rate limits, normalization, reliability, and failure behavior.

## Active access

Sleeper's official read-only API supplies league settings, players, rosters, picks, transactions, trades, matchups, standings, NFL state, and trending adds/drops. Player metadata is refreshed at most daily; trending data is attributed to Sleeper and follows published API guidance.

Existing cached FantasyCalc-, KeepTradeCut-, Sleeper ADP-, and DynastyProcess-compatible values are accepted only through normalized adapters when legitimately supplied. Cache ingestion is not represented as a live upstream request.

## Configuration-gated access

FantasyCalc usage must comply with attribution, caching, non-substitution, and commercial-use restrictions. FantasyPros and commercial news sources require approved credentials or licensing. Underdog, Dynasty Daddy, KeepTradeCut, and other sources remain disabled where no approved public contract exists.

Configure enablement with `DTOS_PROVIDER_<NORMALIZED_NAME>`. Enabling a provider does not bypass missing credentials, licensing, normalization, or quality gates.

## Adding an adapter

1. Confirm access and licensing.
2. Implement the Data Provider SDK contract.
3. Normalize identity and every field.
4. Add deterministic live, cached, historical, unavailable, schema-change, and rate-limit tests.
5. Document attribution and refresh limits.
6. Verify no provider-specific object reaches an intelligence engine.
