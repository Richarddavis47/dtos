# DTOS v1.4.0 — Live Data Platform & Market Integration

DTOS now has one transparent boundary for external data. The platform preserves each source's opinion, licensing state, provenance, quality, freshness, and failure state before intelligence engines consume it.

## Highlights

- Public provider SDK and dynamic provider registry.
- Explicit provider category, version, enablement, licensing tier, refresh capabilities, latency, cache, freshness, confidence, and health.
- Independently configurable scheduled and on-demand refresh contracts with season/offseason intervals.
- Durable, attributed snapshot warehouse and deterministic 7-day, 30-day, 90-day, one-year, and lifetime trends.
- Robust consensus that limits outlier influence and exposes variance, agreement, bullish sources, bearish sources, and missing providers.
- Deterministic fallback chain: live provider, fresh cache, historical snapshot, disclosed DTOS estimate, then unavailable.
- Quality states for missing, impossible, duplicate, stale, and disagreeing data.
- Structured news interpretation based only on observable supplied facts.
- Standardized Data Platform APIs and provider-health visibility on Settings.
- Market Intelligence and Sleeper HTTP transport now consume the platform boundary.

## Metadata

- Version: 1.4.0
- Build: 1400
- Codename: Live Data Platform & Market Integration

## Provider and licensing boundaries

- Cached FantasyCalc, KeepTradeCut, Sleeper ADP, and DynastyProcess-compatible values retain their existing behavior behind platform adapters.
- Sleeper league and transaction access uses the platform transport boundary.
- FantasyPros, Dynasty Daddy, Underdog, Rotowire, NBC Sports Edge, and news integrations remain disabled unless approved access and licensing configuration are available.
- Disabled and unavailable providers remain visible and never silently contribute values.

## Non-goals preserved

No championship probability, win probability, new trade algorithm, new Decision Engine logic, machine learning model, or unapproved scraping was introduced.
